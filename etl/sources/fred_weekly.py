"""Weekly FRED series via the public graph CSV (no key needed)."""

import datetime as dt

from common import get_csv, parse_date

KEY = None
URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"

SERIES = [
    {"id": "wei", "order": 3, "title": "Economic Index", "group": "Jobs & economy",
     "description": "NY Fed weekly read on national growth, scaled to annual GDP growth. A falling index means a slowing economy.",
     "unit": "pct", "decimals": 2, "freq": "weekly", "agg": "last", "higher_is_worse": False, "weight": 1,
     "geo": "United States", "source": "Federal Reserve Bank of New York (FRED: WEI)",
     "source_url": "https://fred.stlouisfed.org/series/WEI", "fred_id": "WEI",
     "sample": {"base": 2.2, "vol": 0.12, "spike": -0.8}},
]


def fetch():
    start = (dt.date.today() - dt.timedelta(days=4 * 365)).isoformat()
    out = {}
    for s in SERIES:
        rows = get_csv(URL, params={"id": s["fred_id"], "cosd": start})
        date_col = next(iter(rows[0]))  # "observation_date" now, "DATE" in older files
        pts = []
        for r in rows:
            v = r.get(s["fred_id"], "").strip()
            if v and v != ".":
                pts.append((parse_date(r[date_col]), float(v)))
        out[s["id"]] = pts
    return out
