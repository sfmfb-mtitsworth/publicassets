"""USDA AMS My Market News (MARS API) wholesale food prices. Needs USDA_AMS_API_KEY.

Get a key: create an account at mymarketnews.ams.usda.gov, then generate an API key in
your profile. Auth is HTTP Basic with the key as username and an empty password.

Field names differ per report and were not verified against a live response yet. Each
series lists candidate price fields and row filters; the first live run logs the keys it
saw so the mapping can be tightened.
"""

import base64
import datetime as dt

from common import env, get_json, parse_date

KEY = "USDA_AMS_API_KEY"
BASE = "https://marsapi.ams.usda.gov/services/v1.2/reports"

SERIES = [
    {"id": "eggs_ca", "order": 1, "title": "Egg Prices", "group": "Food staple prices",
     "description": "Wholesale price of a dozen large shell eggs. A staple protein whose price swings fast.",
     "unit": "usd", "decimals": 2, "freq": "weekly", "agg": "mean", "higher_is_worse": True, "weight": 1,
     "geo": "California", "source": "USDA AMS, California Shell Egg report (2844)",
     "source_url": "https://mymarketnews.ams.usda.gov/viewReport/2844",
     "slug": 2844, "filters": {"egg_size": "large"}, "price_fields": ["wtd_avg", "weighted_average", "avg_price", "price_avg"],
     "scale": 0.01,  # cents per dozen -> dollars per dozen
     "sample": {"base": 3.4, "vol": 0.05, "season": 0.06, "spike": 0.35}},
    {"id": "chicken_us", "order": 2, "title": "Chicken Prices", "group": "Food staple prices",
     "description": "National composite wholesale whole broiler price, per pound. No California-only report exists.",
     "unit": "usd", "decimals": 2, "freq": "weekly", "agg": "mean", "higher_is_worse": True, "weight": 0.75,
     "geo": "United States", "source": "USDA AMS, Weekly National Chicken report (3646)",
     "source_url": "https://mymarketnews.ams.usda.gov/viewReport/3646",
     "slug": 3646, "filters": {"item": "composite"}, "price_fields": ["wtd_avg", "weighted_average", "avg_price"],
     "scale": 0.01,  # cents per pound -> dollars per pound
     "sample": {"base": 1.08, "vol": 0.02, "season": 0.04, "trend": 0.02}},
    {"id": "beef_us", "order": 3, "title": "Beef Prices", "group": "Food staple prices",
     "description": "Choice boxed beef cutout, per 100 lbs. Wholesale beef costs reach stores within weeks.",
     "unit": "usd", "decimals": 2, "freq": "weekly", "agg": "mean", "higher_is_worse": True, "weight": 0.75,
     "geo": "United States", "source": "USDA AMS, Daily Boxed Beef Cutout (2453)",
     "source_url": "https://mymarketnews.ams.usda.gov/viewReport/2453",
     "slug": 2453, "filters": {}, "price_fields": ["choice_600_900_current", "choice_600_900", "choice_cutout"],
     "scale": 1,
     "sample": {"base": 365, "vol": 0.012, "trend": 0.05}},
]


def _rows(slug, start, end):
    token = base64.b64encode(f"{env(KEY)}:".encode()).decode()
    rows = []
    while start <= end:  # MARS caps date ranges, so pull in 180-day chunks
        stop = min(end, start + dt.timedelta(days=179))
        q = f"report_begin_date={start:%m/%d/%Y}:{stop:%m/%d/%Y}"
        rows += get_json(f"{BASE}/{slug}", params={"q": q, "allSections": "true"},
                         headers={"Authorization": f"Basic {token}"}).get("results", [])
        start = stop + dt.timedelta(days=1)
    return rows


def _matches(row, filters):
    return all(want in str(row.get(k, "")).lower() for k, want in filters.items())


def fetch():
    end = dt.date.today()
    start = end - dt.timedelta(days=3 * 365)
    out = {}
    for s in SERIES:
        rows = _rows(s["slug"], start, end)
        if rows:
            print(f"[ams_food] {s['slug']} sample row keys: {sorted(rows[0])}")
        pts = []
        for r in rows:
            if not _matches(r, s["filters"]):
                continue
            field = next((f for f in s["price_fields"] if r.get(f) not in (None, "")), None)
            date = r.get("report_begin_date") or r.get("report_date")
            if field and date:
                try:
                    d = dt.datetime.strptime(date[:10], "%m/%d/%Y").date() if "/" in date else parse_date(date)
                    pts.append((d, float(str(r[field]).replace(",", "")) * s["scale"]))
                except ValueError:
                    continue
        if not pts:
            raise ValueError(f"Report {s['slug']}: no rows matched filters {s['filters']} with fields {s['price_fields']}")
        out[s["id"]] = pts
    return out
