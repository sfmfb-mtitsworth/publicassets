"""CalFresh applications received in San Francisco and Marin (CDSS CF 296). No key.

CDSS publishes CF 296 as Excel workbooks linked from its data tables page. This finds
the newest workbook link and reads applications received per county per month. The
workbook layout is checked on each run and the run fails loudly if it changes.
"""

import datetime as dt
import io
import re
import urllib.parse

from common import http_get

KEY = None
PAGE = "https://cdss.ca.gov/inforesources/research-and-data/calfresh-data-tables/cf296"
COUNTIES = {"san francisco", "marin"}

SERIES = [
    {"id": "calfresh_apps", "order": 2, "title": "CalFresh Applications", "group": "Need & housing",
     "description": "CalFresh (SNAP) applications received in San Francisco and Marin counties each month. A direct read on how many households are seeking food help.",
     "unit": "count", "decimals": 0, "freq": "monthly", "agg": "sum", "chart": "bar", "higher_is_worse": True, "weight": 1.5,
     "geo": "San Francisco + Marin", "source": "CA Dept. of Social Services, CF 296",
     "source_url": PAGE,
     "sample": {"base": 4200, "vol": 0.06, "trend": 0.04, "spike": 0.25, "integer": True}},
]


def _workbook_links():
    html = http_get(PAGE).decode("utf-8", "replace")
    links = re.findall(r'href="([^"]+\.xlsx?)"', html, re.I)
    links = ["https://cdss.ca.gov" + l if l.startswith("/") else l for l in links]
    return [urllib.parse.quote(l, safe=":/?=&%") for l in dict.fromkeys(links)]


def _num(v):
    try:
        return float(str(v).replace(",", "").strip())
    except ValueError:
        return None  # "*" marks counts under 11, suppressed by CDSS


def _month(v):
    if hasattr(v, "date"):
        return v.date().replace(day=1)
    try:
        return dt.date.fromisoformat(str(v)[:10]).replace(day=1)
    except ValueError:
        return None


def fetch():
    """Each workbook has a "Data_External" sheet: one row per county per month, with
    columns Date, County Name, Report Month and "Cell 1" = applications received."""
    import openpyxl

    links = _workbook_links()
    if not links:
        raise ValueError("No CF 296 workbook links found on the CDSS page")
    totals = {}
    for url in links[:4]:  # current fiscal year plus three prior years
        wb = openpyxl.load_workbook(io.BytesIO(http_get(url)), read_only=True, data_only=True)
        for ws in wb.worksheets:
            rows = ws.iter_rows(values_only=True)
            hdr = None
            for r in rows:
                cells = [str(c or "").strip().lower() for c in r]
                if "county name" in cells and "cell 1" in cells:
                    hdr = cells
                    break
            if hdr is None:
                continue
            i_county, i_apps = hdr.index("county name"), hdr.index("cell 1")
            i_month = hdr.index("report month") if "report month" in hdr else hdr.index("date")
            for r in rows:
                if str(r[i_county] or "").strip().lower() not in COUNTIES:
                    continue
                m, v = _month(r[i_month]), _num(r[i_apps])
                if m and v is not None:
                    totals.setdefault(m, {})[str(r[i_county]).strip().lower()] = v
    if not totals:
        raise ValueError(f"No CF 296 rows found for {sorted(COUNTIES)} in {links[:4]}")
    # Only keep months where every county reported, so a missing county never looks like a drop.
    return {"calfresh_apps": sorted((m, sum(c.values())) for m, c in totals.items() if len(c) == len(COUNTIES))}
