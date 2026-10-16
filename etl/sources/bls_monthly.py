"""Monthly BLS series: SF area CPI and SF + Marin unemployment rate. No key needed.

BLS_API_KEY (optional, free at data.bls.gov/registrationEngine) raises the daily request
limit; without it the v2 API allows 25 requests a day, and this uses one.

Both lag: BLS publishes CPI about two weeks after the reference month (the SF area only in
even months), and county unemployment about five weeks after.
"""

import datetime as dt
import json
import urllib.request

from common import USER_AGENT, env

KEY = None
URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
CAVEAT = "Monthly, lagged"

CPI = {"cpi_sf": "CUURS49BSA0", "cpi_food_sf": "CUURS49BSAF11"}
# LAUS county series: 04 = unemployed persons, 06 = labor force.
LAUS = {"San Francisco": "06075", "Marin": "06041"}

SERIES = [
    {"id": "cpi_sf", "order": 1, "title": "Inflation (CPI)", "group": "Monthly indicators", "caveat": CAVEAT,
     "description": "12-month change in consumer prices, SF-Oakland-Hayward area. Published every other month, about two weeks after the month ends.",
     "unit": "pct", "decimals": 1, "freq": "monthly", "agg": "last", "higher_is_worse": True, "weight": 1,
     "geo": "SF-Oakland-Hayward", "source": "BLS CPI-U",
     "source_url": "https://www.bls.gov/regions/west/consumerpriceindex_sanfrancisco.htm",
     "sample": {"base": 3.0, "vol": 0.08}},
    {"id": "cpi_food_sf", "order": 2, "title": "Food Inflation (CPI)", "group": "Monthly indicators", "caveat": CAVEAT,
     "description": "12-month change in grocery (food at home) prices, SF-Oakland-Hayward area. Published every other month, about two weeks after the month ends.",
     "unit": "pct", "decimals": 1, "freq": "monthly", "agg": "last", "higher_is_worse": True, "weight": 1,
     "geo": "SF-Oakland-Hayward", "source": "BLS CPI-U, food at home",
     "source_url": "https://www.bls.gov/regions/west/consumerpriceindex_sanfrancisco.htm",
     "sample": {"base": 2.5, "vol": 0.12}},
    {"id": "unemp_sfmarin", "order": 3, "title": "Unemployment Rate", "group": "Monthly indicators", "caveat": CAVEAT,
     "description": "Share of the labor force out of work in San Francisco and Marin combined, not seasonally adjusted. Published about five weeks after the month ends.",
     "unit": "pct", "decimals": 1, "freq": "monthly", "agg": "last", "higher_is_worse": True, "weight": 1.5,
     "geo": "San Francisco + Marin", "source": "BLS LAUS",
     "source_url": "https://www.bls.gov/lau/",
     "sample": {"base": 4.0, "vol": 0.04, "season": 0.05}},
]


def _laus_id(fips, measure):
    return f"LAUCN{fips}00000000{measure}"


def fetch():
    year = dt.date.today().year
    ids = list(CPI.values()) + [_laus_id(f, m) for f in LAUS.values() for m in ("04", "06")]
    body = {"seriesid": ids, "startyear": str(year - 4), "endyear": str(year)}
    if env("BLS_API_KEY"):
        body["registrationkey"] = env("BLS_API_KEY")
    req = urllib.request.Request(URL, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as r:
        payload = json.load(r)
    if payload.get("status") != "REQUEST_SUCCEEDED":
        raise RuntimeError(f"BLS: {payload.get('message')}")
    vals = {}
    for s in payload["Results"]["series"]:
        for o in s["data"]:
            if o["period"].startswith("M") and o["period"] != "M13" and o["value"] not in ("-", ""):
                vals.setdefault(s["seriesID"], {})[dt.date(int(o["year"]), int(o["period"][1:]), 1)] = float(o["value"])
    out = {}
    for sid, bls_id in CPI.items():
        idx = vals.get(bls_id, {})
        out[sid] = [(m, round((v / idx[m.replace(year=m.year - 1)] - 1) * 100, 2))
                    for m, v in sorted(idx.items()) if m.replace(year=m.year - 1) in idx]
    unemployed = [vals.get(_laus_id(f, "04"), {}) for f in LAUS.values()]
    labor = [vals.get(_laus_id(f, "06"), {}) for f in LAUS.values()]
    months = set.intersection(*(set(d) for d in unemployed + labor)) if unemployed else set()
    out["unemp_sfmarin"] = [(m, round(100 * sum(u[m] for u in unemployed) / sum(l[m] for l in labor), 2))
                            for m in sorted(months)]
    return out
