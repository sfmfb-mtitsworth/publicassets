"""San Francisco eviction notices filed with the Rent Board (DataSF). Optional SOCRATA_APP_TOKEN."""

import datetime as dt

from common import env, get_json, parse_date

KEY = None  # works without a token; SOCRATA_APP_TOKEN only raises rate limits
URL = "https://data.sfgov.org/resource/5cei-gny5.json"

SERIES = [
    {"id": "evictions_sf", "order": 3, "title": "Eviction Notices", "group": "Need & housing",
     "description": "Eviction notices filed with the San Francisco Rent Board each week. Housing instability often comes right before food insecurity. The last two weeks are left off while filings are still being posted.",
     "unit": "count", "decimals": 0, "freq": "weekly", "agg": "sum", "chart": "bar", "higher_is_worse": True, "weight": 1, "lag_weeks": 2,
     "geo": "San Francisco", "source": "SF Rent Board via DataSF",
     "source_url": "https://data.sfgov.org/Housing-and-Buildings/Eviction-Notices/5cei-gny5",
     "sample": {"base": 45, "vol": 0.25, "spike": 0.9, "integer": True}},
]


def fetch():
    start = (dt.date.today() - dt.timedelta(days=3 * 365)).isoformat()
    headers = {"X-App-Token": env("SOCRATA_APP_TOKEN")} if env("SOCRATA_APP_TOKEN") else None
    rows = get_json(URL, params={"$select": "file_date", "$where": f"file_date >= '{start}T00:00:00'",
                                 "$order": "file_date ASC", "$limit": 50000}, headers=headers)
    return {"evictions_sf": [(parse_date(r["file_date"]), 1.0) for r in rows if r.get("file_date")]}
