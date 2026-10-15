"""EDD WARN layoff notices for Bay Area counties. Public xlsx, no key. Needs openpyxl.

The xlsx covers the current fiscal year only (July 1 to date), so history builds up
in data/series/warn_bay.json from run to run.
"""

import io

from common import http_get, parse_date

KEY = None
URL = "https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx"
COUNTIES = {"San Francisco", "Marin", "Alameda", "Contra Costa", "San Mateo", "Santa Clara",
            "Solano", "Napa", "Sonoma"}

SERIES = [
    {"id": "warn_bay", "order": 2, "title": "WARN Layoff Notices", "group": "Jobs & economy",
     "description": "Workers covered by WARN layoff and closure notices filed by Bay Area employers, by week the notice was dated. Employers must file 60 days ahead, so this leads job losses.",
     "unit": "count", "decimals": 0, "freq": "weekly", "agg": "sum", "chart": "bar", "higher_is_worse": True, "weight": 1,
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
    i_county = next(i for i, h in enumerate(header) if h.startswith("county"))
    i_emp = next(i for i, h in enumerate(header) if "employees" in h)
    pts = []
    for row in rows:
        county = str(row[i_county] or "").replace(" County", "").strip()
        if county not in COUNTIES or row[i_date] is None:
            continue
        d = row[i_date]
        d = d.date() if hasattr(d, "date") else parse_date(d)
        try:
            pts.append((d, float(row[i_emp] or 0)))
        except (TypeError, ValueError):
            continue
    return {"warn_bay": pts}
