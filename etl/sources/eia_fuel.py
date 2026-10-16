"""EIA weekly retail fuel prices (API v2). Needs EIA_API_KEY (free: eia.gov/opendata/register.php)."""

import datetime as dt

from common import env, get_json, parse_date

KEY = "EIA_API_KEY"
URL = "https://api.eia.gov/v2/petroleum/pri/gnd/data/"

SERIES = [
    {"id": "gas_sf", "order": 1, "title": "Gas Prices", "group": "Prices",
     "description": "Regular gasoline, average retail price. Fuel costs squeeze household budgets within weeks.",
     "unit": "usd", "decimals": 2, "freq": "weekly", "agg": "mean", "higher_is_worse": True, "weight": 1,
     "geo": "San Francisco", "source": "U.S. Energy Information Administration",
     "source_url": "https://www.eia.gov/petroleum/gasdiesel/", "eia_series": "EMM_EPMR_PTE_Y05SF_DPG",
     "sample": {"base": 5.0, "vol": 0.015, "trend": 0.02, "season": 0.03, "spike": 0.06}},
    {"id": "diesel_ca", "order": 2, "title": "Diesel Prices", "group": "Prices",
     "description": "On-highway diesel, average retail price. Diesel drives food transport costs, ours included.",
     "unit": "usd", "decimals": 2, "freq": "weekly", "agg": "mean", "higher_is_worse": True, "weight": 1,
     "geo": "California", "source": "U.S. Energy Information Administration",
     "source_url": "https://www.eia.gov/petroleum/gasdiesel/", "eia_series": "EMD_EPD2D_PTE_SCA_DPG",
     "sample": {"base": 6.1, "vol": 0.015, "trend": 0.01, "season": 0.02, "spike": 0.05}},
]


def fetch():
    start = (dt.date.today() - dt.timedelta(days=4 * 365)).isoformat()
    params = {"api_key": env(KEY), "frequency": "weekly", "data[0]": "value", "start": start,
              "facets[series][]": [s["eia_series"] for s in SERIES], "length": 5000}
    rows = get_json(URL, params=params)["response"]["data"]
    by_series = {s["eia_series"]: s["id"] for s in SERIES}
    out = {}
    for r in rows:
        if r.get("value") in (None, ""):
            continue
        out.setdefault(by_series[r["series"]], []).append((parse_date(r["period"]), float(r["value"])))
    return out
