"""Zillow Observed Rent Index (ZORI) for the San Francisco metro. Public CSV, no key."""

import datetime as dt

from common import get_csv

KEY = None
URL = "https://files.zillowstatic.com/research/public_csvs/zori/Metro_zori_uc_sfrcondomfr_sm_month.csv"
METRO = "San Francisco, CA"

SERIES = [
    {"id": "rent_sf", "order": 2, "title": "Rents", "group": "Housing stress",
     "description": "Typical asking rent, all home types (Zillow ZORI, smoothed). Rising rents leave less for food.",
     "unit": "usd", "decimals": 0, "freq": "monthly", "agg": "last", "higher_is_worse": True, "weight": 0.5,
     "geo": "San Francisco metro", "source": "Zillow Research (ZORI)",
     "source_url": "https://www.zillow.com/research/data/",
     "sample": {"base": 3300, "vol": 0.004, "trend": 0.03}},
]


def fetch():
    rows = get_csv(URL)
    row = next(r for r in rows if r.get("RegionName") == METRO)
    pts = []
    for k, v in row.items():
        if len(k) == 10 and k[4] == "-" and v:
            pts.append((dt.date.fromisoformat(k).replace(day=1), float(v)))
    return {"rent_sf": pts}
