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


def fetch():
    import openpyxl

    links = _workbook_links()
    if not links:
        raise ValueError("No CF 296 workbook links found on the CDSS page")
    print(f"[calfresh] workbook links: {links[:4]}")
    totals = {}
    for url in links[:2]:  # current and prior fiscal year
        wb = openpyxl.load_workbook(io.BytesIO(http_get(url)), read_only=True, data_only=True)
        for ws in wb.worksheets:
            rows = list(ws.iter_rows(values_only=True))
            hdr_i = next((i for i, r in enumerate(rows[:15]) if any("county" in str(c or "").lower() for c in r)), None)
            if hdr_i is None:
                continue
            hdr = [str(c or "").lower() for c in rows[hdr_i]]
            i_county = next(i for i, h in enumerate(hdr) if "county" in h)
            i_month = next((i for i, h in enumerate(hdr) if "month" in h or "date" in h), None)
            i_apps = next((i for i, h in enumerate(hdr) if "received" in h or "applications" in h), None)
            if i_month is None or i_apps is None:
                print(f"[calfresh] {ws.title}: header not recognized: {hdr[:12]}")
                continue
            for r in rows[hdr_i + 1:]:
                if str(r[i_county] or "").strip().lower() not in COUNTIES:
                    continue
                m, v = r[i_month], r[i_apps]
                if hasattr(m, "date"):
                    m = m.date()
                elif isinstance(m, str):
                    try:
                        m = dt.datetime.strptime(m.strip()[:8], "%b %Y").date()
                    except ValueError:
                        continue
                if not isinstance(m, dt.date) or not isinstance(v, (int, float)):
                    continue  # "*" means suppressed
                key = m.replace(day=1)
                totals[key] = totals.get(key, 0) + v
    if not totals:
        raise ValueError("CF 296 workbook layout not recognized; see log for headers")
    return {"calfresh_apps": sorted(totals.items())}
