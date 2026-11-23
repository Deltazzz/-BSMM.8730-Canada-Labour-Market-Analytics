"""Build the Power BI report with a native MySQL import partition."""
import hashlib
import json
from pathlib import Path

from database import HOST, PORT, DATABASE

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "powerbi"
REPORT = DEST / "Job Bank.Report"
MODEL = DEST / "Job Bank.SemanticModel"
DEF = REPORT / "definition"
SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/"
RS = "item/report/definition/"
# The source view exposes these labels and model types.
COLUMNS = [
    ('Snapshot ID', 'string'),
    ('First posted', 'string'),
    ('Month', 'string'),
    ('Source', 'string'),
    ('NOC', 'string'),
    ('Occupation', 'string'),
    ('Province', 'string'),
    ('Economic region', 'string'),
    ('Education', 'string'),
    ('Experience', 'string'),
    ('Employment type', 'string'),
    ('Employment term', 'string'),
    ('Telework flag', 'string'),
    ('Weekend flag', 'string'),
    ('Pay period', 'string'),
    ('Pay status', 'string'),
    ('Vacancies', 'int64'),
    ('Lower amount', 'double'),
    ('Upper amount', 'double'),
    ('Midpoint amount', 'double'),
]
MEASURES = {
    "Location records": ("COUNTROWS('Postings')", "#,0"),
    "Advertised openings": ("SUM('Postings'[Vacancies])", "#,0"),
    "Hourly records": ("CALCULATE(COUNT('Postings'[Midpoint amount]), KEEPFILTERS('Postings'[Pay period] = \"Hour\"))", "#,0"),
    "Median hourly lower": ("CALCULATE(MEDIAN('Postings'[Lower amount]), KEEPFILTERS('Postings'[Pay period] = \"Hour\"))", "$#,0.00"),
    "Median hourly upper": ("CALCULATE(MEDIAN('Postings'[Upper amount]), KEEPFILTERS('Postings'[Pay period] = \"Hour\"))", "$#,0.00"),
    "Median hourly midpoint": ("CALCULATE(MEDIAN('Postings'[Midpoint amount]), KEEPFILTERS('Postings'[Pay period] = \"Hour\"))", "$#,0.00"),
}

def write(path, obj):
    path.parent.mkdir(exist_ok=True,parents=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n",encoding="utf-8")

def filedef(path, schema, **obj):
    write(path, {"$schema":SCHEMA+schema+"/schema.json", **obj})

def key(s):
    return hashlib.sha256(s.encode()).hexdigest()[:20]

def make_model():
    def m_string(value):
        return '"' + value.replace('#', '#(#)').replace('"', '""') + '"'
    server = m_string(f"{HOST}:{PORT}")
    database = m_string(DATABASE)
    m = [
        "let",
        f"    Source = MySQL.Database({server}, {database}, [ReturnSingleDatabase=true]),",
        f'    Postings = Source{{[Schema={database}, Item="powerbi_postings"]}}[Data]',
        "in",
        "    Postings",
    ]
    table = {"name":"Postings","columns":[{"name":label,"dataType":ty,"sourceColumn":label,"summarizeBy":"none"}
                                        for label,ty in COLUMNS],
             "measures":[{"name":name,"expression":expr,"formatString":fmt} for name,(expr,fmt) in MEASURES.items()],
             "partitions":[{"name":"Postings","mode":"import","source":{"type":"m","expression":m}}]}
    write(MODEL/"model.bim",{"name":"Job Bank","compatibilityLevel":1600,"model":{
        "culture":"en-CA","sourceQueryCulture":"en-CA","defaultPowerBIDataSourceVersion":"powerBI_V3","tables":[table]}})
    filedef(MODEL/"definition.pbism","item/semanticModel/definitionProperties/1.0.0",version="1.0",settings={})

def literal(s):
    return {"expr":{"Literal":{"Value":s}}}

def field(name):
    if name not in MEASURES and name not in [c[0] for c in COLUMNS]:
        raise KeyError(name)
    return {"Measure" if name in MEASURES else "Column":{"Expression":{"SourceRef":{"Entity":"Postings"}},"Property":name}}

def project(name):
    return {"field":field(name),"queryRef":"Postings."+name,"nativeQueryRef":name}

def visual(page, title, typ, roles, pos, sort=None):
    vid = key(page.name + title)
    container = {"title":[{"properties":{"show":literal("true"),"text":literal("'"+title.replace("'","''")+"'")}}]}
    state = {role:{"projections":[project(n) for n in refs]} for role, refs in roles.items()}
    vis = {"visualType":typ,"query":{"queryState":state},"visualContainerObjects":container}
    if sort:
        vis["query"]["sortDefinition"] = {"sort":[{"field":field(sort[0]),"direction":sort[1]}]}
    if typ == "slicer":
        vis["objects"]={"data":[{"properties":{"mode":literal("'Dropdown'")}}]}
    x,y,w,h = pos
    filedef(page/"visuals"/vid/"visual.json",RS+"visualContainer/2.1.0",name=vid,
            position={"x":x,"y":y,"z":y*10+x,"width":w,"height":h,"tabOrder":y*10+x},visual=vis)

def make_report():
    filedef(DEST/"Job Bank.pbip","pbip/pbipProperties/1.0.0",version="1.0",artifacts=[{"report":{"path":REPORT.name}}],
            settings={"enableAutoRecovery":True})
    filedef(REPORT/"definition.pbir","item/report/definitionProperties/2.0.0",version="4.0",datasetReference={"byPath":{"path":"../"+MODEL.name}})
    filedef(DEF/"version.json",RS+"versionMetadata/1.0.0",version="2.0.0")
    theme={"name":"CY24SU10","type":"SharedResources","reportVersionAtImport":{"visual":"2.1.0","report":"3.0.0","page":"2.0.0"}}
    filedef(DEF/"report.json",RS+"report/3.0.0",themeCollection={"baseTheme":theme})
    specs=[
        ("Demand and geography",["Month","Source","Province"],[
            ("Records by first posting month","clusteredColumnChart",{"Category":["Month"],"Series":["Source"],"Y":["Location records"]},(14,100,614,290),("Month","Ascending")),
            ("Records by listed province or territory","barChart",{"Category":["Province"],"Y":["Location records"]},(645,100,620,290),("Location records","Descending")),
            ("Occupations — right-click to explore","tableEx",{"Values":["Occupation","NOC","Location records","Advertised openings"]},(14,405,614,300),("Location records","Descending")),
            ("Economic regions","tableEx",{"Values":["Province","Economic region","Location records","Advertised openings"]},(645,405,620,300),("Location records","Descending"))]),
        ("Pay and qualifications",["Month","Province","Occupation","Source"],[
            ("Hourly pay by occupation and province","tableEx",{"Values":["Occupation","Province","Hourly records","Median hourly lower","Median hourly upper","Median hourly midpoint"]},(14,100,1250,265),("Hourly records","Descending")),
            ("Education in listed records","barChart",{"Category":["Education"],"Y":["Location records"]},(14,387,608,315),("Location records","Descending")),
            ("Experience in listed records","barChart",{"Category":["Experience"],"Y":["Location records"]},(640,387,624,315),("Location records","Descending"))]),
        ("Work arrangements",["Month","Province","Occupation","Source"],[
            ("Employment type","barChart",{"Category":["Employment type"],"Y":["Location records"]},(14,100,605,282),("Location records","Descending")),
            ("Employment duration","barChart",{"Category":["Employment term"],"Y":["Location records"]},(642,100,622,282),("Location records","Descending")),
            ("Telework flag by source","tableEx",{"Values":["Source","Telework flag","Location records"]},(14,398,605,304),None),
            ("Weekend work by source","tableEx",{"Values":["Source","Weekend flag","Location records"]},(642,398,622,304),None)]),
        ("Occupation detail",["Month","Province","Source"],[
            ("Selected occupation by month","tableEx",{"Values":["Occupation","Month","Location records","Advertised openings","Hourly records","Median hourly midpoint"]},(14,100,1250,265),("Month","Ascending")),
            ("Education and experience together","tableEx",{"Values":["Education","Experience","Location records"]},(14,382,620,320),("Location records","Descending")),
            ("Listed locations","tableEx",{"Values":["Province","Economic region","Location records"]},(648,382,616,320),("Location records","Descending"))])]
    pages=[]
    for title,slicers,visuals in specs:
        pid=key(title)
        pages.append(pid)
        page=DEF/"pages"/pid
        extra={}
        if title=="Occupation detail":
            ref="Filter"+hashlib.sha256(title.encode()).hexdigest()[:24]
            extra={"visibility":"HiddenInViewMode","filterConfig":{"filters":[{"name":ref,"field":field("Occupation"),"type":"Categorical","howCreated":"Drillthrough"}]},
                   "pageBinding":{"name":"Pod","type":"Drillthrough","parameters":[{"name":"Param_"+ref,"boundFilter":ref,"fieldExpr":field("Occupation")}]}}
        filedef(page/"page.json",RS+"page/2.0.0",name=pid,displayName=title,displayOption="FitToPage",height=720,width=1280,**extra)
        for i,name in enumerate(slicers):
            width=(1090 if title=="Occupation detail" else 1250)//len(slicers)
            visual(page,name,"slicer",{"Values":[name]},(14+i*width,8,width-12,80))
        for t,typ,roles,pos,sort in visuals:
            visual(page,t,typ,roles,pos,sort)
        if title=="Occupation detail":
            vid=key("Return from occupation detail")
            button={"visualType":"actionButton","objects":{"text":[{"properties":{"show":literal("true")}},
                    {"selector":{"id":"default"},"properties":{"text":literal("'Back to results'")}}]},
                    "visualContainerObjects":{"visualLink":[{"properties":{"show":literal("true"),"type":literal("'Back'")}}]}}
            filedef(page/"visuals"/vid/"visual.json",RS+"visualContainer/2.1.0",name=vid,
                    position={"x":1110,"y":16,"width":145,"height":52,"z":2000,"tabOrder":2000},visual=button)
    filedef(DEF/"pages/pages.json",RS+"pagesMetadata/1.0.0",pageOrder=pages,activePageName=pages[0])

if __name__=="__main__":
    make_model()
    make_report()
    print("Wrote Power BI project with direct MySQL refresh.")
