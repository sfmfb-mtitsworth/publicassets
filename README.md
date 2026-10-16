# Leading Indicators

Weekly leading indicators of food insecurity for the SF-Marin Food Bank. GitHub Actions
pulls each source, scores anomalies and renders `artifacts/dashboard.html`. A Claude
Routine publishes that file to the leadership dashboard artifact.

## Indicators

| Group | Indicator | Geography | Source | Secret |
|---|---|---|---|---|
| Prices | Gas prices | San Francisco | EIA weekly retail | `EIA_API_KEY` |
| Prices | Diesel prices | California | EIA weekly retail | `EIA_API_KEY` |
| Prices | Egg prices | California | USDA AMS report 2844 | `USDA_AMS_API_KEY` |
| Prices | Chicken prices | U.S. | USDA AMS report 3646 | `USDA_AMS_API_KEY` |
| Prices | Beef prices | U.S. | USDA AMS report 2453 | `USDA_AMS_API_KEY` |
| Jobs & economy | Unemployment claims | California | DOL/EDD via FRED `CAICLAIMS` | none |
| Jobs & economy | WARN layoff notices | Bay Area | EDD WARN xlsx | none |
| Jobs & economy | Weekly Economic Index | U.S. | NY Fed via FRED `WEI` | none |
| Housing stress | Eviction notices | San Francisco | DataSF `5cei-gny5` | optional `SOCRATA_APP_TOKEN` |
| Housing stress | Rents | SF metro | Zillow ZORI (monthly) | none |
| Google Searches | Searches for "food bank" | SF Bay Area | Google Trends API (alpha) | `GOOGLE_TRENDS_API_KEY` |

A source whose secret is missing shows **sample data**, labelled on the dashboard. Add the
secret under Settings > Secrets and variables > Actions and the next run switches it to live.

## How it works

- `etl/sources/<name>.py`: one module per source. Each declares `KEY`, `SERIES` metadata and `fetch()`.
- `etl/build.py`: runs every source, merges results into `data/series/<id>.json` (history
  accumulates, which matters for WARN since EDD only publishes the current fiscal year),
  scores anomalies and writes `data/dashboard.json` and `artifacts/dashboard.html`.
- A failed source keeps its last good data and is flagged on the dashboard; it never blocks the others.

**Anomaly levels:** each period's z-score against the trailing 52 weeks (24 months for monthly
data), signed so higher always means more pressure on households. Level 1/2/3 = 1/2/3+ SD.
**General Indicator:** weighted mean of those signed z-scores per week (weights in each module).

## Run locally

```
pip install -r requirements.txt
LI_FORCE_SAMPLE=1 python etl/build.py   # all sample data, no network
python etl/build.py                     # live where keys are set in the environment
```

## Adding an indicator

Copy a module in `etl/sources/`, fill in `SERIES` (see the field list at the top of
`etl/build.py`) and `fetch()`, and add any secret to `.github/workflows/etl.yml`.
