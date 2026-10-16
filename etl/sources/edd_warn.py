"""EDD WARN layoff notices for Bay Area counties. Public xlsx, no key. Needs openpyxl.

EDD's xlsx covers the current fiscal year only (July 1 to date). Earlier years come from
data/backfill/warn_bay_records.csv, transcribed from EDD's prior-year WARN PDFs
(FY 2024-25 and FY 2025-26; parsed totals matched EDD's own summary rows exactly).
Records from both are merged and de-duplicated before weekly totals are taken.
"""

import csv
import io
import pathlib

from common import http_get, parse_date

KEY = None
URL = "https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx"
BACKFILL = pathlib.Path(__file__).resolve().parents[2] / "data" / "backfill" / "warn_bay_records.csv"
COUNTIES = {"San Francisco", "Marin", "Alameda", "Contra Costa", "San Mateo", "Santa Clara",
            "Solano", "Napa", "Sonoma"}

SERIES = [
    {"id": "warn_bay", "order": 2, "title": "WARN Layoff Notices", "group": "Jobs & economy",
     "description": "Workers covered by WARN layoff notices from Bay Area employers. Filed 60 days ahead, so it leads job losses.",
     "unit": "count", "decimals": 0, "freq": "weekly", "agg": "sum", "higher_is_worse": True, "weight": 1,
     "geo": "Bay Area (9 counties)", "source": "California EDD WARN report",
     "source_url": "https://edd.ca.gov/en/jobs_and_training/Layoff_Services_WARN",
     "sample": {"base": 400, "vol": 0.7, "spike": 2.5, "integer": True}},
]


def _norm(s):
    return " ".join(str(s or "").lower().replace("\n", " ").split())


def fetch():
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(http_get(URL)), read_only=True, data_only=True)
    ws = next((wb[n] for n in wb.sheetnames if "detail" in n.lower()), wb.worksheets[0])
    rows = ws.iter_rows(values_only=True)
    header = None
    for row in rows:  # skip title rows until the header row
        if any(_norm(c) == "notice date" for c in row):
            header = [_norm(c) for c in row]
            break
    if header is None:
        raise ValueError(f"No 'Notice Date' header found in sheet {ws.title}")
    i_date = header.index("notice date")
    i_recv = header.index("received date") if "received date" in header else i_date
    i_company = next((i for i, h in enumerate(header) if h.startswith("company")), None)
    i_county = next(i for i, h in enumerate(header) if h.startswith("county"))
    i_emp = next(i for i, h in enumerate(header) if "employees" in h)
    records = set()
    for row in rows:
        county = str(row[i_county] or "").replace(" County", "").strip()
        if county not in COUNTIES or row[i_date] is None:
            continue
        try:
            records.add((_day(row[i_date]), _day(row[i_recv]), _norm(row[i_company] if i_company is not None else ""),
                         county, int(float(row[i_emp] or 0))))
        except (TypeError, ValueError):
            continue
    with open(BACKFILL, newline="") as fh:
        for r in csv.DictReader(fh):
            records.add((parse_date(r["notice_date"]), parse_date(r["received_date"]), _norm(r["company"]),
                         r["county"], int(r["employees"])))
    return {"warn_bay": [(notice, float(emp)) for notice, _, _, _, emp in records]}


def _day(v):
    return v.date() if hasattr(v, "date") else parse_date(v)
