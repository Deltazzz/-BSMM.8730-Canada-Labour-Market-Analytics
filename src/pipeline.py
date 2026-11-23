"""Acquire pinned Job Bank releases, validate their grain and rebuild MySQL and CSV outputs."""
import argparse
import calendar
import csv
import hashlib
import re
from decimal import Decimal

from database import connect, create_schema, reload
import unicodedata
from collections import Counter
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.request import urlopen
from shutil import copyfileobj

ROOT = Path(__file__).resolve().parents[1]
RAW, CLEAN, RESULTS = (ROOT / k for k in ("data/raw", "data/clean", "results"))
CATALOGUE = "https://open.canada.ca/data/dataset/ea639e28-c0fc-48bf-b5dd-b8899bd43072"
RELEASES = [
    ("2026-08", "aug", "07546deb-70f5-4638-b34b-7c4321264972", "f2ad4cfa3eb5fd9fb9b1aaf846f8dfdb4f83f4fca221db4b819702053242a75f"),
    ("2026-09", "sept", "03523cbf-a005-40ee-81ad-aca5bb74cf03", "0952ffeea10eb20e9b794c1e695140cfb93529e58a88b0382d9d7b88f5eb548c"),
    ("2026-10", "oct", "271cca4e-ddd6-44b1-a6a1-c105f6a2afa2", "07751bcfd66148a419f96d354a2c595d2b7898d893c1b2604adfd47b0b42244f")
]
ALIAS = {"wic_job_location_snapshot_id": "snapshot_id", "noc21_code": "noc", "noc21_code_name": "occupation",
         "province_territory": "province", "education_los": "education", "experience_level": "experience",
         "employment_term_telework": "telework"}
DATES = {"first_posting_date", "employment_term_start_date", "employment_term_end_date"}
NUMBERS = {"hours_minimum", "hours_maximum", "salary_minimum", "salary_maximum"}
MISSING = {"", "na", "*no data"}
DERIVED = ["release_month", "source_record", "posting_month", "channel", "pay_status", "pay_midpoint", "hourly_review"]
DETAIL = {
    "snapshot_id": "Publisher's job-location snapshot identifier. A distinct ad or employer identifier is unavailable.",
    "job_title": "Standardized job title as supplied.", "original_job_title": "Original title supplied by the source.",
    "noc": "Five-character 2021 National Occupational Classification unit-group code. Preserve leading zeros.",
    "occupation": "English label for the NOC 2021 code.", "noc_2016_code": "Earlier NOC 2016 code, retained as text.",
    "noc_2016_code_name": "NOC 2016 occupation label.", "external_indicator": "Source indicator. 0 direct, 1 external.",
    "first_posting_date": "First posting date in the release. Determines the analysis month.",
    "vacancy_count": "Number of advertised openings attached to the location record.",
    "official_language": "Language category recorded on the posting.", "education": "Advertised education requirement.",
    "experience": "Advertised experience category. Explicit no experience is a known requirement.",
    "government_type": "Government employer category.", "placement_agency": "Placement agency indicator.",
    "naics": "Industry description supplied in the NAICS field.", "province": "Province or territory of the listed location.",
    "city": "Listed city.", "work_location_postal_code": "Postal code of the job location.",
    "economic_region": "Publisher's economic region label. Group with province.",
    "various_location": "Multiple-location flag as supplied.", "employment_type": "Full-time or part-time category.",
    "employment_term": "Duration category such as permanent, seasonal, casual or contract.",
    "employment_term_start_date": "Expected employment start date.", "employment_term_end_date": "Expected employment end date.",
    "telework": "Telework flag on the release. Unknown and explicit No are kept separate.",
    "salary_condition_detail": "Publisher's pay description retained for review.",
    "salary_per": "Period for the advertised pay range. Compare amounts within a period.",
    "salary_minimum": "Lower advertised pay amount, in dollars per stated pay period.",
    "salary_maximum": "Upper advertised pay amount, in dollars per stated pay period.",
    "condition_vision_care": "Vision care indicator as recorded.", "commission_per": "Basis for commission (e.g. per sale).",
    "commission_type": "Commission type, such as amount or percentage.", "hours_per": "Period for the reported work hours.",
    "hours_minimum": "Minimum work hours in the stated hours period.", "hours_maximum": "Maximum work hours in that period.",
    "work_hours": "Publisher's work-hours flag.", "work_hours_from_time": "Reported starting clock time.",
    "work_hours_to_time": "Reported ending clock time.", "release_month": "Month in the catalogue resource title.",
    "source_record": "One-based logical data record within the raw release, excluding the header.",
    "posting_month": "Year and month derived from the parsed first posting date.",
    "channel": "Direct or External, derived from External Indicator.",
    "pay_status": "Comparable when both bounds are positive, ordered and tied to a known unit.",
    "pay_midpoint": "Arithmetic mean of the two bounds on comparable records, in the original unit.",
    "hourly_review": "1 when a comparable hourly range starts below $5 or ends above $500. Sensitivity screen only."
}

def csvout(path, columns, rows):
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(columns)
        w.writerows(rows)

def slug(s):
    key = re.sub(r"[^a-z0-9]+", "_", s.strip().lower()).strip("_")
    return ALIAS.get(key, key)

def dtype(k):
    if k in {"source_record", "vacancy_count", "hourly_review"}:
        return "INT UNSIGNED"
    if k in NUMBERS or k == "pay_midpoint":
        return "DECIMAL(18,6)"
    if k in DATES:
        return "DATE"
    if k in {"release_month", "posting_month"}:
        return "CHAR(7)"
    if k == "noc":
        return "CHAR(5)"
    if k == "snapshot_id":
        return "VARCHAR(40)"
    if k in {"job_title", "original_job_title", "salary_condition_detail"}:
        return "TEXT"
    if k in {"occupation", "education", "noc_2016_code_name", "naics", "economic_region", "city"}:
        return "VARCHAR(255)"
    return "VARCHAR(80)"

def normalize(value):
    value = unicodedata.normalize("NFC", value).strip()
    return None if value.casefold() in MISSING else value

def description(k):
    if k.startswith("salary_condition_") and k not in DETAIL:
        return "Recorded pay or benefit indicator for " + k.removeprefix("salary_condition_").replace("_", " ") + "."
    if k.startswith("employment_term_") and k not in DETAIL:
        return "Recorded work schedule indicator for " + k.removeprefix("employment_term_").replace("_", " ") + "."
    return DETAIL[k]

def acquire(download):
    RAW.mkdir(parents=True, exist_ok=True)
    items = []
    for period, short, rid, sha in RELEASES:
        name = f"job-bank-open-data-all-job-postings-en-{short}2026.csv"
        url = f"{CATALOGUE}/resource/{rid}/download/{name}"
        path = RAW / name
        if not path.exists() and download:
            with TemporaryDirectory(dir=RAW) as td:
                pending = Path(td) / name
                with urlopen(url, timeout=120) as src, pending.open("wb") as dst:
                    copyfileobj(src, dst)
                if hashlib.sha256(pending.read_bytes()).hexdigest() != sha:
                    raise ValueError(f"Publisher bytes differ from the pinned release: {name}")
                pending.replace(path)
        if not path.is_file():
            raise FileNotFoundError(f"Missing {path}. Run python src/pipeline.py --download")
        if hashlib.sha256(path.read_bytes()).hexdigest() != sha:
            raise ValueError(f"Unexpected SHA-256: {name}")
        items.append((period, path, url, sha))
    return items

def prepare(files, tmp):
    profiles, coverage, sources = [], [], []
    ids, base = set(), None
    with (tmp / "postings.csv").open("w", encoding="utf-8", newline="") as out:
        writer = csv.writer(out, lineterminator="\n")
        for period, path, url, sha in files:
            with path.open(encoding="utf-16", newline="") as f:
                reader = csv.reader(f, delimiter="\t", strict=True)
                original = next(reader)
                keys = [slug(k) for k in original]
                if base is None:
                    base = keys
                    if len(set(keys)) != 65:
                        raise ValueError("Expected 65 distinct source fields")
                    columns = keys + DERIVED
                    writer.writerow(columns)
                    fieldrows = [(s, k, dtype(k), description(k)) for s, k in zip(original, keys)]
                    fieldrows += [("Derived", k, dtype(k), description(k)) for k in DERIVED]
                    csvout(tmp / "data_dictionary.csv", ["source_header", "clean_field", "mysql_type", "definition"], fieldrows)
                if keys != base:
                    raise ValueError(f"Unexpected schema or field order in {path.name}")
                missing, days = Counter(), Counter()
                seen, last = set(), 0
                for i, raw in enumerate(reader, 1):
                    if len(raw) != len(keys):
                        raise ValueError(f"{path.name}, logical record {i}: wrong width")
                    row = {k: normalize(v) for k, v in zip(keys, raw)}
                    for k, v in row.items():
                        if v is None:
                            missing[k] += 1
                        elif k in DATES:
                            row[k] = date.fromisoformat(v.replace("/", "-")).isoformat()
                        elif k in NUMBERS:
                            row[k] = Decimal(v)
                    id_ = row["snapshot_id"]
                    if not id_ or id_ in ids or id_ in seen:
                        raise ValueError(f"Missing or repeated snapshot ID: {path.name}, record {i}")
                    seen.add(id_)
                    posted = row["first_posting_date"]
                    if posted is None or posted[:7] != period:
                        raise ValueError(f"Unexpected first posting date in {path.name}, record {i}")
                    days[posted] += 1
                    if row["noc"] and not re.fullmatch(r"\d{5}", row["noc"]):
                        raise ValueError(f"Invalid NOC 2021 code: {row['noc']}")
                    row["vacancy_count"] = int(row["vacancy_count"])
                    if row["vacancy_count"] < 1:
                        raise ValueError(f"Invalid vacancy count at {period} record {i}")
                    lo, hi, unit = row["salary_minimum"], row["salary_maximum"], row["salary_per"]
                    if not unit or lo is None or hi is None:
                        status = "Missing unit or bound"
                    elif lo <= 0 or hi < lo:
                        status = "Invalid bounds"
                    else:
                        status = "Comparable"
                    midpoint = (lo + hi) / 2 if status == "Comparable" else None
                    review = int(lo < 5 or hi > 500) if midpoint is not None and unit == "Hour" else None
                    channel = {"0": "Direct", "1": "External"}[row["external_indicator"]]
                    record = [row[k] for k in keys] + [period, i, posted[:7], channel, status, midpoint, review]
                    writer.writerow(record)
                    last = i
                ndays = calendar.monthrange(*map(int, period.split("-")))[1]
                if len(days) != ndays:
                    raise ValueError(f"Dates absent in {period}")
                coverage.append((period, last, len(keys), min(days), max(days), len(days), len(seen), last-len(seen),len(ids & seen)))
                profiles.extend((period, k, last, missing[k], last-missing[k]) for k in keys)
                ids.update(seen)
                sources.append((period, path.name, url, sha, path.stat().st_size))
    csvout(tmp / "coverage.csv", ["release_month","records","fields","first_date","last_date","distinct_dates","distinct_ids","duplicate_ids_within","ids_in_earlier_releases"], coverage)
    csvout(tmp / "field_coverage.csv", ["release_month","field","records","missing","known"], profiles)
    csvout(tmp / "sources.csv", ["release_month","filename","url","sha256","bytes"], sources)

    return columns, len(ids)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true", help="Download missing pinned government releases")
    args = parser.parse_args()
    files = acquire(args.download)
    CLEAN.mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(exist_ok=True)
    with TemporaryDirectory(dir=ROOT) as td:
        tmp = Path(td)
        columns, expected = prepare(files, tmp)
        with connect() as db, db.cursor(buffered=True) as cursor:
            cursor.execute("SELECT GET_LOCK(CONCAT(DATABASE(), '.jobbank_load'), 0)")
            if cursor.fetchone() != (1,):
                raise RuntimeError("Another MySQL load is active")
            create_schema(cursor, columns, dtype, ROOT / "src/analysis.sql")
            db.commit()
            db.start_transaction()
            reload(cursor, tmp, columns)
            cursor.execute("SELECT COUNT(*), COUNT(DISTINCT snapshot_id) FROM postings")
            if cursor.fetchone() != (expected, expected):
                raise ValueError("MySQL count or identifiers differ from the clean data")
            cursor.execute("SELECT TABLE_NAME FROM information_schema.VIEWS WHERE TABLE_SCHEMA=DATABASE() ORDER BY TABLE_NAME")
            views = [r[0] for r in cursor if r[0].startswith("out_")]
            for view in views:
                cursor.execute(f"SELECT * FROM `{view}`")
                csvout(tmp / (view[4:] + ".csv"), cursor.column_names, cursor)
            db.commit()
        for p in tmp.iterdir():
            p.replace((CLEAN if p.name in {"postings.csv","data_dictionary.csv"} else RESULTS) / p.name)
    print("Rebuilt cleaned records, MySQL database, audit and analysis tables.")

if __name__ == "__main__":
    main()
