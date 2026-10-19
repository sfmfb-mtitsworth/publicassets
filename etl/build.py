"""Run every source, keep history, score anomalies and render the dashboard.

Usage: python etl/build.py [--only source_name ...]

For each source module:
  - key missing      -> sample data (status "sample"), clearly labelled on the page
  - fetch succeeds   -> merged into data/series/<id>.json history (status "live")
  - fetch fails      -> last stored history is kept (status "stale") with the error
Outputs data/dashboard.json and artifacts/dashboard.html.

Series metadata fields:
  id, title, description, group, unit ("usd", "count", "index", "pct"), decimals,
  freq ("weekly" | "monthly"), agg ("mean" | "sum" | "last"),
  higher_is_worse (bool), weight (composite weight), geo, source, source_url,
  lag_weeks (optional: recent weeks to drop while the source is still filling them in),
  fill_zeros (optional, weekly sums: False when a missing week means "not published yet", not zero),
  cadence (optional: shown after the title; defaults to "Weekly" or "Monthly" from freq),
  sample {base, vol, trend?, season?, spike?, integer?}
"""

import datetime as dt
import importlib
import json
import math
import re
import pathlib
import pkgutil
import sys
import traceback

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "etl"))

import common  # noqa: E402
import sources  # noqa: E402

HISTORY = ROOT / "data" / "series"
SECRET_ENV = ["EIA_API_KEY", "USDA_AMS_API_KEY", "BLS_API_KEY", "SOCRATA_APP_TOKEN", "GOOGLE_TRENDS_API_KEY"]
BASELINE = {"weekly": (52, 12), "monthly": (24, 8)}  # (trailing periods, minimum periods)
GROUPS = ["Fuel prices", "Food staple prices", "Jobs & economy", "Housing stress"]
PLACEHOLDER = "/*__DASHBOARD_DATA__*/null"


def scrub(msg):
    """Errors are committed to a public repo, and some APIs echo the key back. Remove any secret values."""
    if not msg:
        return msg
    for name in SECRET_ENV:
        value = common.env(name)
        if value:
            msg = msg.replace(value, "***")
    return re.sub(r"(?i)(key[:= ]+)[A-Za-z0-9_-]{12,}", r"\1***", msg)


def now_iso():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def load_history(sid):
    path = HISTORY / f"{sid}.json"
    return json.loads(path.read_text()) if path.exists() else None


def save_history(sid, record):
    HISTORY.mkdir(parents=True, exist_ok=True)
    (HISTORY / f"{sid}.json").write_text(json.dumps(record, indent=1) + "\n")


def run_source(mod):
    """Return {series_id: record} for one source module."""
    name = mod.__name__.split(".")[-1]
    out = {}
    if common.env("LI_FORCE_SAMPLE") or (mod.KEY and not common.env(mod.KEY)):
        for meta in mod.SERIES:
            pts = common.sample_series(meta)
            out[meta["id"]] = {"status": "sample", "fetched_at": None, "error": None,
                               "points": [[d.isoformat(), v] for d, v in pts]}
        print(f"[{name}] {mod.KEY or 'LI_FORCE_SAMPLE'} not set, using sample data")
        return out
    try:
        fetched = mod.fetch()
        error = None
    except Exception as e:  # keep going; one broken source must not block the dashboard
        print(scrub(traceback.format_exc()))
        fetched, error = {}, scrub(f"{type(e).__name__}: {e}")[:300]
    series_errors = fetched.pop("_errors", {})  # a source may report failures per series
    for meta in mod.SERIES:
        sid = meta["id"]
        prev = load_history(sid)
        prev_pts = {} if not prev or prev["status"] == "sample" else dict(map(tuple, prev["points"]))
        new = fetched.get(sid)
        if new:
            bucketed = common.bucket(new, meta["freq"], meta["agg"])
            if meta["freq"] == "weekly" and meta["agg"] == "sum":
                # Counts: drop the current partial week, plus recent weeks a source is still filling in.
                last = common.week_start(dt.date.today()) - dt.timedelta(weeks=1 + meta.get("lag_weeks", 0))
                bucketed = [(d, v) for d, v in bucketed if d <= last]
                if meta.get("fill_zeros", True):  # counts of events: a week with none is a real zero
                    bucketed = common.fill_zero_weeks(bucketed, last)
                prev_pts = {d: v for d, v in prev_pts.items() if d <= last.isoformat()}
            merged = {**prev_pts, **{d.isoformat(): round(v, 4) for d, v in bucketed}}
            record = {"status": "live", "fetched_at": now_iso(), "error": None,
                      "points": sorted([d, v] for d, v in merged.items())}
            save_history(sid, record)
            print(f"[{name}] {sid}: {len(bucketed)} periods fetched, {len(merged)} in history")
        else:
            msg = scrub(series_errors.get(sid)) or error or "Source returned no data"
            record = {"status": "stale" if prev_pts else "error", "error": msg,
                      "fetched_at": prev and prev.get("fetched_at"),
                      "points": sorted([d, v] for d, v in prev_pts.items())}
            print(f"[{name}] {sid}: {msg}")
        out[sid] = record
    return out


def score(points, freq):
    """Add z-score vs the trailing baseline (excluding the current period) to each point."""
    window, minimum = BASELINE[freq]
    vals = [v for _, v in points]
    scored = []
    for i, (d, v) in enumerate(points):
        base = vals[max(0, i - window):i]
        z = None
        if len(base) >= minimum:
            mean = sum(base) / len(base)
            sd = math.sqrt(sum((x - mean) ** 2 for x in base) / (len(base) - 1))
            z = round((v - mean) / sd, 2) if sd > 0 else 0.0
        scored.append([d, v, z])
    return scored


def level(adverse_z):
    if adverse_z is None:
        return 0
    return 3 if adverse_z >= 3 else 2 if adverse_z >= 2 else 1 if adverse_z >= 1 else 0


def stats(points, freq):
    vals = [p[1] for p in points]
    if not vals:
        return None
    n_recent, n_year = (4, 52) if freq == "weekly" else (3, 12)
    return {"latest": vals[-1], "latest_date": points[-1][0],
            "recent_avg": sum(vals[-n_recent:]) / len(vals[-n_recent:]),
            "year_avg": sum(vals[-n_year:]) / len(vals[-n_year:]),
            "recent_n": min(n_recent, len(vals)), "year_n": min(n_year, len(vals))}


def composite(series, weeks=156):
    """Weighted mean of adverse z-scores per week. Monthly series carry forward up to 62 days."""
    end = common.week_start(dt.date.today()) - dt.timedelta(weeks=1)  # last complete week
    rows = []
    for i in range(weeks - 1, -1, -1):
        wk = end - dt.timedelta(weeks=i)
        total = wsum = 0.0
        for s in series:
            if not s["points"]:
                continue
            z = None
            for p in reversed(s["points"]):
                dd, zz = dt.date.fromisoformat(p[0]), p[2]
                if dd <= wk:
                    if (wk - dd).days <= (6 if s["freq"] == "weekly" else 62) and zz is not None:
                        z = zz
                    break
            if z is None:
                continue
            adverse = z if s["higher_is_worse"] else -z
            total += s["weight"] * max(-4.0, min(4.0, adverse))
            wsum += s["weight"]
        if wsum:
            v = round(total / wsum, 2)
            rows.append([wk.isoformat(), v, level(v * 2)])  # composite averages out, so double for level
    return rows


def main(only=None):
    mods = [importlib.import_module(f"sources.{m.name}") for m in pkgutil.iter_modules(sources.__path__)]
    series = []
    for mod in mods:
        if only and mod.__name__.split(".")[-1] not in only:
            continue
        records = run_source(mod)
        for meta in mod.SERIES:
            rec = records[meta["id"]]
            pts = score(rec["points"], meta["freq"])
            for p in pts:
                p.append(level(None if p[2] is None else p[2] if meta["higher_is_worse"] else -p[2]))
            series.append({**{k: v for k, v in meta.items() if k != "sample"},
                           "status": rec["status"], "error": rec["error"], "fetched_at": rec["fetched_at"],
                           "key": mod.KEY, "points": pts, "stats": stats(pts, meta["freq"])})
    series.sort(key=lambda s: (GROUPS.index(s["group"]), s.get("order", 99)))
    data = {"generated_at": now_iso(), "groups": GROUPS, "series": series, "composite": composite(series)}
    (ROOT / "data" / "dashboard.json").write_text(json.dumps(data, indent=1) + "\n")
    template = (ROOT / "templates" / "dashboard.html").read_text()
    payload = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    (ROOT / "artifacts").mkdir(exist_ok=True)
    (ROOT / "artifacts" / "dashboard.html").write_text(template.replace(PLACEHOLDER, payload))
    counts = {k: sum(s["status"] == k for s in series) for k in ("live", "sample", "stale", "error")}
    print(f"Built dashboard: {counts}")


if __name__ == "__main__":
    args = sys.argv[1:]
    main(args[args.index("--only") + 1:] if "--only" in args else None)
