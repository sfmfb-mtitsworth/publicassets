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
LMR_BASE = "https://mpr.datamart.ams.usda.gov/services/v1.1/reports"  # Livestock Mandatory Reporting, no key
LAYOUT_KEYS = ["primal", "item", "class", "color", "egg_type", "environment", "purchase_type", "delivery", "grade", "region"]

SERIES = [
    {"id": "eggs_ca", "order": 1, "title": "Egg Prices", "group": "Food staple prices",
     "description": "Wholesale price of a dozen large shell eggs. A staple protein whose price swings fast.",
     "unit": "usd", "decimals": 2, "freq": "weekly", "agg": "mean", "higher_is_worse": True, "weight": 1,
     "geo": "California", "source": "USDA AMS, California Shell Egg report (2844)",
     "source_url": "https://mymarketnews.ams.usda.gov/viewReport/2844",
     "slug": 2844, "price_fields": ["avg_price"],
     # California Benchmark price for large white eggs (all California eggs are cage-free).
     "filters": {"_section": "Report Detail Simple", "purchase_type": "Benchmark", "class": "Large", "color": "White"},
     "scale": 0.01,  # cents per dozen -> dollars per dozen
     "sample": {"base": 3.4, "vol": 0.05, "season": 0.06, "spike": 0.35}},
    {"id": "chicken_us", "order": 2, "title": "Chicken Prices", "group": "Food staple prices",  # id kept for history continuity; now Western region
     "description": "Wholesale price of whole broilers (without giblets) in the Western region, per pound. No California-only chicken price is published.",
     "unit": "usd", "decimals": 2, "freq": "weekly", "agg": "mean", "higher_is_worse": True, "weight": 0.75,
     "geo": "Western U.S.", "source": "USDA AMS, Weekly National Chicken report (3646), Western region",
     "source_url": "https://mymarketnews.ams.usda.gov/viewReport/3646",
     "slug": 3646, "filters": {"_section": "Report Detail", "primal": "Whole", "item": "WOG", "region": "Western"}, "price_fields": ["wtd_avg_price"],
     "scale": 0.01,  # cents per pound -> dollars per pound
     "sample": {"base": 1.08, "vol": 0.02, "season": 0.04, "trend": 0.02}},
    {"id": "beef_us", "order": 3, "title": "Beef Prices", "group": "Food staple prices",
     "description": "Choice boxed beef cutout, per 100 lbs. Wholesale beef costs reach stores within weeks.",
     "unit": "usd", "decimals": 2, "freq": "weekly", "agg": "mean", "higher_is_worse": True, "weight": 0.75,
     "geo": "United States", "source": "USDA AMS, Daily Boxed Beef Cutout (2453)",
     "source_url": "https://mymarketnews.ams.usda.gov/viewReport/2453",
     "slug": 2453, "lmr": True, "filters": {}, "price_fields": ["choice_600_900_current", "choice_600_900", "choice_cutout"],
     "scale": 1,
     "sample": {"base": 365, "vol": 0.012, "trend": 0.05}},
]


def _rows(slug, start, end, lmr=False):
    token = base64.b64encode(f"{env(KEY)}:".encode()).decode()
    base, headers = (LMR_BASE, {}) if lmr else (BASE, {"Authorization": f"Basic {token}"})
    rows = []
    while start <= end:  # MARS caps date ranges, so pull in 180-day chunks
        stop = min(end, start + dt.timedelta(days=179))
        field = "report_date" if lmr else "report_begin_date"
        resp = get_json(f"{base}/{slug}", params={"q": f"{field}={start:%m/%d/%Y}:{stop:%m/%d/%Y}", "allSections": "true"},
                        headers=headers)
        got = _extract(resp)
        if not got and not rows:
            print(f"[ams_food] {slug} empty response shape: {str(resp)[:400]}")
        rows += got
        start = stop + dt.timedelta(days=1)
    return rows


def _extract(resp):
    """allSections=true returns a list of sections, each with its own results."""
    if isinstance(resp, dict):
        return [dict(r, _section=resp.get("reportSection")) for r in resp.get("results", [])]
    rows = []
    for sec in resp:
        if isinstance(sec, dict) and "results" in sec:
            rows += [dict(r, _section=sec.get("reportSection")) for r in sec["results"]]
        elif isinstance(sec, dict):
            rows.append(sec)
    return rows


def _log_layout(slug, rows):
    seen = {}
    for r in rows:
        seen.setdefault(r.get("_section"), r)
    for sec, r in seen.items():
        sample = {k: str(v)[:40] for k, v in r.items() if v not in (None, "")}
        print(f"[ams_food] {slug} section {sec!r}: {sample}")
        in_sec = [x for x in rows if x.get("_section") == sec]
        for k in LAYOUT_KEYS:
            vals = sorted({str(x[k]) for x in in_sec if x.get(k) not in (None, "")})
            if 1 < len(vals) <= 60:
                print(f"[ams_food] {slug} {sec!r} {k}: {vals}")


def _matches(row, filters):
    return all(str(row.get(k, "")).strip().lower() == want.lower() for k, want in filters.items())


def fetch():
    end = dt.date.today()
    start = end - dt.timedelta(days=3 * 365)
    out, errors = {}, {}
    for s in SERIES:
        try:
            out[s["id"]] = _series(s, start, end)
        except Exception as e:  # one report failing must not blank the others
            errors[s["id"]] = f"{type(e).__name__}: {e}"
            print(f"[ams_food] {s['id']} failed: {type(e).__name__}")
    return {**out, "_errors": errors}


def _series(s, start, end):
    rows = _rows(s["slug"], start, end, s.get("lmr", False))
    _log_layout(s["slug"], rows)
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
    return pts
