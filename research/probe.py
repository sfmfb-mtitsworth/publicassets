"""One-off probe: find EDD's weekly UI claims XLSX files and show their layout for SF and Marin."""
import io, re, sys, urllib.parse
sys.path.insert(0, "etl")
from common import http_get
import openpyxl

UA = {"User-Agent": "Mozilla/5.0 (compatible; sfmfb-leadingindicators)"}
pages = ["https://edd.ca.gov/en/newsroom/facts-and-stats/dashboard/", "https://edd.ca.gov/Newsroom/facts-and-stats/dashboard.htm",
         "https://edd.ca.gov/en/about_edd/Quick_Statistics_Information_by_County"]
links = set()
for pg in pages:
    try:
        html = http_get(pg, headers=UA, retries=1).decode("utf-8", "replace")
        found = re.findall(r'href="([^"]+\.(?:xlsx?|csv))"', html, re.I)
        print(f"== {pg}: {len(found)} spreadsheet links")
        for l in found:
            u = urllib.parse.urljoin(pg, l); links.add(u); print("   ", u)
    except Exception as e:
        print(f"== {pg}: {e}")
for u in sorted(links):
    try:
        wb = openpyxl.load_workbook(io.BytesIO(http_get(u, headers=UA, retries=1)), read_only=True, data_only=True)
    except Exception as e:
        print(f"\n## {u}: {e}"); continue
    for ws in wb.worksheets:
        rows = list(ws.iter_rows(max_row=200000, values_only=True))
        hits = [i for i, r in enumerate(rows) if any(str(c).strip().lower() in ("san francisco", "marin", "san francisco county", "marin county") for c in r if c is not None)]
        if not hits:
            continue
        print(f"\n## {u} | sheet {ws.title!r} | {len(rows)} rows | {len(hits)} SF/Marin rows")
        hdr = next((i for i, r in enumerate(rows[:15]) if sum(c is not None for c in r) >= 3), 0)
        for i in range(max(0, hdr - 2), hdr + 3):
            print(f"   r{i}: {[str(c)[:30] for c in rows[i][:16] if c is not None]}")
        for i in hits[:3] + hits[-3:]:
            print(f"   r{i}: {[str(c)[:22] for c in rows[i][:16] if c is not None]}")
