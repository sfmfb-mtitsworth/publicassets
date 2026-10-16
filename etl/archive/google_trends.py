"""ARCHIVED for v1.1: not loaded by build.py (only etl/sources/ is). Move back to etl/sources/ to enable.

Google Trends searches for "food bank" in the San Francisco Bay Area. Needs GOOGLE_TRENDS_API_KEY.

Uses the Google Trends API (alpha). The request shape below follows early public notes
on v1alpha and must be checked against the alpha documentation that came with the key.
"""

import datetime as dt
import json
import time
import urllib.request

from common import USER_AGENT, env

KEY = "GOOGLE_TRENDS_API_KEY"
BASE = "https://searchtrends.googleapis.com/v1alpha"
TERM = "food bank"
GEO = "US-CA-807"  # San Francisco-Oakland-San Jose DMA; fall back to US-CA if the API rejects DMAs

SERIES = [
    {"id": "searches_bay", "order": 1, "title": "Searches for \"food bank\"", "group": "Google Searches",
     "description": "Relative search interest in \"food bank\" (0 to 100). Searches rise when more people look for help.",
     "unit": "index", "decimals": 0, "freq": "weekly", "agg": "mean", "higher_is_worse": True, "weight": 1.5,
     "geo": "SF-Oakland-San Jose metro", "source": "Google Trends",
     "source_url": "https://trends.google.com/trends/explore?geo=US-CA-807&q=food%20bank",
     "sample": {"base": 40, "vol": 0.12, "season": 0.15, "spike": 1.2, "integer": True}},
]


def _call(method, url, body=None):
    req = urllib.request.Request(f"{url}{'&' if '?' in url else '?'}key={env(KEY)}", method=method,
                                 data=json.dumps(body).encode() if body else None,
                                 headers={"Content-Type": "application/json", "User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def fetch():
    end = dt.datetime.now(dt.timezone.utc)
    start = end - dt.timedelta(days=3 * 365)
    body = {"spec": {"expression": {"terms": [TERM]}, "geo": {"code": GEO},
                     "timeRange": {"start": {"seconds": int(start.timestamp())}, "end": {"seconds": int(end.timestamp())}},
                     "timeResolution": "WEEK"}}
    op = _call("POST", f"{BASE}/timeSeries:fetch", body)
    for _ in range(30):  # long-running operation
        if op.get("done", True):
            break
        time.sleep(2)
        op = _call("GET", f"{BASE}/{op['name']}")
    result = op.get("response", op)
    print(f"[google_trends] response keys: {sorted(result)}")
    points = result.get("points") or result.get("timeSeries", [{}])[0].get("points", [])
    pts = []
    for p in points:
        t = p.get("time") or p.get("startTime") or p.get("date")
        v = p.get("value", p.get("interest"))
        if t is not None and v is not None:
            pts.append((dt.date.fromisoformat(str(t)[:10]), float(v)))
    return {"searches_bay": pts}
