"""Reconcile the frozen raw files, SQL, release tables and the MySQL view consumed by Power BI."""
import argparse
import csv
import json
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path
from statistics import median
from urllib.request import urlopen

from database import connect, HOST, PORT, DATABASE
from powerbi import FILTERS, PAGES, DETAIL, key
from pipeline import ROOT, CLEAN, RESULTS, acquire

def require(test, message):
    if not test:
        raise ValueError(message)

def rows(path):
    with path.open(encoding="utf-8",newline="") as f:
        yield from csv.DictReader(f)

def load_report():
    proj = ROOT/"powerbi"
    files = [p for p in sorted(proj.rglob("*")) if p.is_file() and not {".pbi","StaticResources"} & set(p.parts) and p.suffix in (".json",".pbip",".pbism",".pbir")]
    definitions = [(p,json.loads(p.read_text(encoding="utf-8"))) for p in files]
    model = json.loads((proj/"Job Bank.SemanticModel"/"model.bim").read_text(encoding="utf-8"))
    table = model["model"]["tables"][0]
    cols = {(t["name"],c["name"]) for t in model["model"]["tables"] for c in t["columns"]}
    measures = {c["name"] for c in table["measures"]}
    for p,d in definitions:
        if "visual" in d:
            for group in d["visual"].get("query",{}).get("queryState",{}).values():
                for ref in group["projections"]:
                    typ,definition=next(iter(ref["field"].items()))
                    entity = definition["Expression"]["SourceRef"]["Entity"]
                    require(definition["Property"] in measures if typ=="Measure" else (entity,definition["Property"]) in cols,f"Broken binding in {p}")
            pos=d["position"]
            require(pos["x"]>=0 and pos["y"]>=0 and pos["x"]+pos["width"]<=1280 and pos["y"]+pos["height"]<=720,f"Off-canvas visual {p}")
    code = table["partitions"][0]["source"]["expression"]
    source = "\n".join(code)
    require('MySQL.Database(' in source and f'"{HOST}:{PORT}"' in source and f'Schema="{DATABASE}"' in source
            and 'Item="powerbi_postings"' in source, "Power BI source differs from the configured MySQL view")
    require(table["partitions"][0]["mode"] == "import", "Unexpected Power BI partition mode")
    order = next(d for p,d in definitions if p.name=="pages.json")
    require(order["pageOrder"] == [key(n) for n in PAGES+[DETAIL]], "Unexpected D4.2 navigation order")
    expected = {
        "Demand Over Time":{"lineChart", "clusteredBarChart","card"},
        "Geographic Distribution":{"shapeMap","clusteredBarChart"},
        "Qualifications":{"barChart","clusteredBarChart","tableEx"},
        "Compensation":{"card","clusteredBarChart","tableEx"},
        "Work Conditions":{"donutChart","clusteredColumnChart","barChart"}}
    for name,types in expected.items():
        visuals=[d["visual"] for p,d in definitions if "visual" in d and p.parents[2].name==key(name)]
        present={v["visualType"] for v in visuals}
        require(types | {"actionButton","textbox"} <= present, "Missing D4.2 visual on "+name)
        destinations = {link["properties"]["navigationSection"]["expr"]["Literal"]["Value"].strip("'")
                        for v in visuals for link in v.get("visualContainerObjects", {}).get("visualLink", [])
                        if "navigationSection" in link["properties"]}
        require(destinations == {key(target) for target in PAGES}, "Missing page link on "+name)
        synced={v["syncGroup"]["groupName"] for v in visuals if v["visualType"]=="slicer"}
        require(synced=={"D42 "+n for n,_ in FILTERS},"Unsynced filters on "+name)
    return [c["sourceColumn"] for c in table["columns"] if "sourceColumn" in c], definitions


def validate_schemas(definitions):
    from jsonschema import Draft7Validator
    from referencing import Registry, Resource
    from referencing.jsonschema import DRAFT7
    from urllib.parse import urlsplit
    @lru_cache(maxsize=None)
    def fetch(uri):
        if urlsplit(uri).hostname != "developer.microsoft.com":
            raise ValueError(f"Unexpected schema host {uri}")
        with urlopen(uri, timeout=45) as f:
            return Resource.from_contents(json.load(f), default_specification=DRAFT7)
    registry=Registry(retrieve=fetch)
    for p,obj in definitions:
        schema=fetch(obj["$schema"])
        Draft7Validator(schema.contents, registry=registry.with_resource(obj["$schema"],schema)).validate(obj)
    print(f"Validated {len(definitions)} Power BI definition files against Microsoft JSON schemas.")

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--schemas",action="store_true",help="Also fetch Microsoft schemas. Requires jsonschema>=4.22.")
    opts=ap.parse_args()
    fields,definitions=load_report()
    ids=set()
    counts=Counter()
    openings=Counter()
    raw_hourly=defaultdict(list)
    ecount=Counter()
    for month,path,_,_ in acquire(False):
        with path.open(encoding="utf-16",newline="") as f:
            for r in csv.DictReader(f,delimiter="\t"):
                key=r["WIC Job Location Snapshot ID"]
                require(key and key not in ids,"Duplicate ID")
                ids.add(key)
                require(r["First Posting Date"][:7].replace("/","-")==month,"Wrong posting month")
                counts[month]+=1
                openings[month]+=int(r["Vacancy Count"])
                ecount[month]+=int(r["External Indicator"])
                if r["Salary Per"]=="Hour" and r["Salary Minimum"]!="NA" and r["Salary Maximum"]!="NA":
                    lo,hi=map(float,[r["Salary Minimum"],r["Salary Maximum"]])
                    if 0<lo<=hi:
                        raw_hourly[month].append((lo+hi)/2)
    checkids=set()
    for r in rows(CLEAN/"postings.csv"):
        require(r["snapshot_id"] not in checkids,"Duplicate cleaned ID")
        checkids.add(r["snapshot_id"])
    require(ids==checkids,"Raw and cleaned CSV identifiers differ")
    b_ids=set()
    b_counts=Counter()
    b_open=Counter()
    b_hour=defaultdict(list)
    with connect("reader") as db, db.cursor(dictionary=True) as cursor:
        cursor.execute("SELECT * FROM powerbi_postings")
        require(list(cursor.column_names) == fields, "MySQL and model column bindings differ")
        for r in cursor:
            require(r["Snapshot ID"] not in b_ids,"Duplicate MySQL view ID")
            b_ids.add(r["Snapshot ID"])
            b_counts[r["Month"]]+=1
            b_open[r["Month"]]+=int(r["Vacancies"])
            if r["Pay period"]=="Hour" and r["Midpoint amount"]:
                b_hour[r["Month"]].append(float(r["Midpoint amount"]))
    require((ids,counts,openings)==(b_ids,b_counts,b_open),"MySQL report view differs from raw data")
    monthly=list(rows(RESULTS/"monthly.csv"))
    require(set(counts)=={r["posting_month"] for r in monthly},"Missing month in output")
    for r in monthly:
        m=r["posting_month"]
        require((counts[m],openings[m],ecount[m])==tuple(int(r[k]) for k in ["records","advertised_openings","external"]),"Monthly measures differ")
    for r in rows(RESULTS/"pay.csv"):
        if r["scope"]=="Canada" and r["salary_per"]=="Hour":
            m=r["posting_month"]
            require(len(raw_hourly[m])==int(r["comparable_records"]) and median(raw_hourly[m])==float(r["median_midpoint"])==median(b_hour[m]),"Hourly pay mismatch")
    for name in ("occupations","provinces","geography"):
        sums=Counter()
        for r in rows(RESULTS/(name+".csv")):
            sums[r["posting_month"]]+=int(r["records"])
        require(sums==counts,name+" totals differ")
    print(f"Reconciled {len(ids):,} identifiers, monthly counts/openings, geography, occupations and hourly midpoints. Checked native visual bindings and bounds.")
    if opts.schemas:
        validate_schemas(definitions)

if __name__=="__main__":
    main()
