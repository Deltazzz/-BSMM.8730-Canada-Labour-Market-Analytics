"""Keep the national survey series separate from posting-location facts."""
import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
VECTOR = 2062815
TERMS = "https://www.jobbank.gc.ca/termsofuse-seeker.xhtml"
TITLE = "Unemployment rate, Canada, age 15+, total gender, seasonally adjusted"

def statcan(months, download):
    vintage = json.loads((ROOT / "data/reference/statcan-14100287-2026-11-06.json").read_text())
    folder = ROOT / "data/raw/statcan"
    folder.mkdir(parents=True, exist_ok=True)
    url = ("https://www150.statcan.gc.ca/t1/wds/rest/getDataFromVectorByReferencePeriodRange"
           f"?vectorIds={VECTOR}&startRefPeriod={min(months)}-01&endReferencePeriod={max(months)}-01")
    path = folder / f"v{VECTOR}-{min(months)}-{max(months)}.json"
    def decode(raw):
        envelope = json.loads(raw)[0]
        series = envelope["object"]
        if envelope["status"] != "SUCCESS" or int(series["vectorId"]) != VECTOR:
            raise ValueError("Wrong Statistics Canada series")
        return {p["refPer"][:7]: Decimal(str(p["value"])) for p in series["vectorDataPoint"]
                if p["value"] is not None and p["refPer"][:7] in months and int(p["scalarFactorCode"]) == 0}
    detail = "cached JSON"
    if not path.exists() and download:
        try:
            with urlopen(url, timeout=20) as response:
                raw = response.read()
            decode(raw)
            path.write_bytes(raw)
            path.with_suffix(".retrieved").write_text(datetime.now(timezone.utc).isoformat())
        except (URLError, TimeoutError, ValueError, KeyError, IndexError) as exc:
            detail = f"WDS unavailable ({type(exc).__name__}); published-table fallback"
    if path.is_file():
        raw = path.read_bytes()
        values = decode(raw)
        retrieved = path.with_suffix(".retrieved")
        return values, url, (detail, hashlib.sha256(raw).hexdigest(), retrieved.read_text() if retrieved.exists() else "")
    raw = (ROOT / "data/reference/statcan-14100287-2026-11-06.json").read_bytes()
    return {m: Decimal(v) for m,v in vintage["observations"].items() if m in months}, vintage["source"], (
        detail if download else "published-table fallback", hashlib.sha256(raw).hexdigest(), "")

def load_context(cursor, observations, url):
    cursor.execute("SELECT COUNT(*) FROM StatCanSeries WHERE series_id=%s", (VECTOR,))
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO StatCanSeries VALUES(%s,%s,'Canada','percent','14-10-0287-01')", (VECTOR,TITLE))
    cursor.execute("DELETE FROM StatCanObservation WHERE series_id=%s", (VECTOR,))
    if observations:
        cursor.executemany("INSERT INTO StatCanObservation VALUES(%s,%s,%s,%s)",
                           [(VECTOR,m,v,url) for m,v in sorted(observations.items())])
