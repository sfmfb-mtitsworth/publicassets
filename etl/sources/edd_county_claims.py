"""Weekly initial UI claims for San Francisco + Marin from EDD's dashboard workbook. No key.

EDD publishes "ada-county-and-statewide-demographics--industry-data-<date>.xlsx" on its
Unemployment Benefits Data page; the file name changes with each weekly update, so the
current link is read from the page every run. Sheet "County_Claims" has one row per
week ending (Saturday), county and claim type.
"""

import datetime as dt
import io
import re
import urllib.parse

from common import http_get

KEY = None
PAGES = ["https://edd.ca.gov/en/newsroom/facts-and-stats/dashboard/",
         "https://edd.ca.gov/Newsroom/facts-and-stats/dashboard.htm"]
COUNTIES = {"san francisco", "marin"}
UA = {"User-Agent": "Mozilla/5.0 (compatible; sfmfb-leadingindicators)"}

SERIES = [
    {"id": "claims_sfmarin", "order": 1, "title": "Unemployment Claims", "group": "Jobs & economy",
     "description": "New unemployment insurance claims filed each week by residents of San Francisco and Marin, from EDD's weekly county data.",
     "unit": "count", "decimals": 0, "freq": "weekly", "agg": "sum", "fill_zeros": False,
     "higher_is_worse": True, "weight": 1.5,
     "geo": "San Francisco + Marin", "source": "California EDD, weekly claims by county",
     "source_url": PAGES[0],
     "sample": {"base": 950, "vol": 0.08, "season": 0.1, "spike": 0.5, "integer": True}},
]


def _workbook_url():
    for page in PAGES:
        try:
            html = http_get(page, headers=UA).decode("utf-8", "replace")
        except Exception:
            continue
        links = re.findall(r'href="([^"]*ada-county-and-statewide[^"]*\.xlsx)"', html, re.I)
        if links:
            return urllib.parse.urljoin(page, links[0])
    raise ValueError("EDD county claims workbook link not found on the dashboard page")


def fetch():
    import openpyxl

    url = _workbook_url()
    print(f"[edd_county_claims] {url}")
    wb = openpyxl.load_workbook(io.BytesIO(http_get(url, headers=UA)), read_only=True, data_only=True)
    ws = wb["County_Claims"]
    rows = ws.iter_rows(values_only=True)
    for r in rows:  # skip title rows
        cells = [str(c or "").strip().lower() for c in r]
        if "week ending" in cells and "county" in cells:
            i_week, i_county = cells.index("week ending"), cells.index("county")
            i_claims = next(i for i, c in enumerate(cells) if "claims" in c and "type" not in c)
            i_type = next(i for i, c in enumerate(cells) if "type" in c)
            break
    else:
        raise ValueError("County_Claims header row not found")
    weeks = {}
    for r in rows:
        if str(r[i_county] or "").strip().lower() not in COUNTIES or str(r[i_type] or "").strip() != "UI Claims":
            continue
        try:
            n = float(r[i_claims])
        except (TypeError, ValueError):
            continue  # "No Data"
        d = r[i_week].date() if hasattr(r[i_week], "date") else dt.date.fromisoformat(str(r[i_week])[:10])
        weeks.setdefault(d, {})[str(r[i_county]).strip().lower()] = n
    # Only weeks where both counties reported, so a missing county never reads as a drop.
    return {"claims_sfmarin": [(d, sum(c.values())) for d, c in sorted(weeks.items()) if len(c) == len(COUNTIES)]}
