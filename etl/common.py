"""Shared helpers for source modules: HTTP, date bucketing and sample data.

Each module in etl/sources/ defines:
  KEY     env var the source needs, or None
  SERIES  list of series metadata dicts (see build.py for fields)
  fetch() -> {series_id: [(datetime.date, float), ...]} at the source's native frequency
"""

import csv
import datetime as dt
import io
import json
import math
import os
import random
import time
import urllib.parse
import urllib.request

USER_AGENT = "sfmfb-leadingindicators/1.0 (+https://www.sfmfoodbank.org)"


def http_get(url, params=None, headers=None, timeout=60, retries=2):
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params, doseq=True)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except Exception:
            if attempt == retries:
                raise
            time.sleep(2 ** (attempt + 1))


def get_json(url, **kw):
    return json.loads(http_get(url, **kw))


def get_csv(url, **kw):
    return list(csv.DictReader(io.StringIO(http_get(url, **kw).decode("utf-8-sig"))))


def env(name):
    value = os.environ.get(name, "").strip()
    return value or None


def parse_date(s):
    return dt.date.fromisoformat(str(s)[:10])


def week_start(d):
    """Monday of the ISO week containing d. All weekly data is keyed by this date."""
    return d - dt.timedelta(days=d.weekday())


def month_start(d):
    return d.replace(day=1)


def bucket(points, freq, how):
    """Aggregate (date, value) points to weekly or monthly buckets with sum, mean or last."""
    key = week_start if freq == "weekly" else month_start
    groups = {}
    for d, v in sorted(points):
        groups.setdefault(key(d), []).append(v)
    out = []
    for k in sorted(groups):
        vals = groups[k]
        agg = sum(vals) if how == "sum" else vals[-1] if how == "last" else sum(vals) / len(vals)
        out.append((k, agg))
    return out


def fill_zero_weeks(points, end):
    """For count series: weeks with no events are real zeros, not missing data."""
    if not points:
        return points
    have = dict(points)
    d, out = points[0][0], []
    while d <= end:
        out.append((d, have.get(d, 0.0)))
        d += dt.timedelta(days=7)
    return out


def sample_series(meta, today=None):
    """Deterministic, clearly-labelled placeholder data used until a source's key is set."""
    s = meta["sample"]
    today = today or dt.date.today()
    rng = random.Random(meta["id"])
    if meta["freq"] == "weekly":
        end = week_start(today) - dt.timedelta(days=7)
        dates = [end - dt.timedelta(weeks=i) for i in range(155, -1, -1)]
        per_year = 52
    else:
        first = month_start(today)
        dates = []
        y, m = first.year, first.month
        for _ in range(36):
            m -= 1
            if m == 0:
                y, m = y - 1, 12
            dates.append(dt.date(y, m, 1))
        dates.reverse()
        per_year = 12
    level, out = s["base"], []
    for i, d in enumerate(dates):
        level *= 1 + s.get("trend", 0) / per_year
        seasonal = s.get("season", 0) * math.sin(2 * math.pi * (d.timetuple().tm_yday / 365.25))
        shock = s["base"] * s.get("spike", 0) if i in (len(dates) - 50, len(dates) - 3) else 0
        v = max(0.0, level * (1 + seasonal) + rng.gauss(0, s["vol"] * s["base"]) + shock)
        out.append((d, round(v) if s.get("integer") else round(v, 3)))
    return out
