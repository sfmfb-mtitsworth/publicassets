"""Weekly FRED series via the public graph CSV (no key needed)."""

import datetime as dt

from common import get_csv, parse_date

KEY = None
URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"

SERIES = [
    {"id": "claims_ca", "order": 1, "title": "Unemployment Claims", "group": "Jobs & economy",
     "description": "New (initial) unemployment insurance claims filed in California each week, as reported by EDD to the U.S. Department of Labor. Not seasonally adjusted.",
     "unit": "count", "decimals": 0, "freq": "weekly", "agg": "last", "chart": "bar", "higher_is_worse": True, "weight": 1.5,
     "geo": "California", "source": "CA EDD via U.S. DOL (FRED: CAICLAIMS)",
     "source_url": "https://fred.stlouisfed.org/series/CAICLAIMS", "fred_id": "CAICLAIMS",
     "sample": {"base": 42000, "vol": 0.08, "season": 0.1, "spike": 0.5, "integer": True}},
    {"id": "wei", "order": 3, "title": "Weekly Economic Index", "group": "Jobs & economy",
     "description": "The New York Fed's weekly read on national economic growth, scaled to annual GDP growth. A falling index signals a slowing economy.",
     "unit": "pct", "decimals": 2, "freq": "weekly", "agg": "last", "chart": "line", "higher_is_worse": False, "weight": 1,
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
