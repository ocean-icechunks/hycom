"""Inventory the archive from data.hycom.org's directory listings: 25 requests, one at a time.

The THREDDS catalog XML (tds.hycom.org/thredds/catalog/...) was tried first and abandoned:
a year's catalog took minutes to generate. The Apache listing takes ~6 s per year.
Sizes in the listing are rounded (74M, 2.4G); modification times are to the minute.
"""
import csv, gzip, re, time, requests
from common import PREFIX

ROW = re.compile(r'<a href="([^"]+)">[^<]*</a>\s+(\d{4}-\d\d-\d\d \d\d:\d\d)\s+(\S+)')
rows = []
for sub in [f"{y}/" for y in range(2001, 2025)] + ["daily_netcdf/"]:
    html = requests.get(PREFIX + sub, timeout=300).text
    rows += [dict(dir=sub.rstrip("/"), name=n, modified=m, size=s) for n, m, s in ROW.findall(html)]
    print(sub, sum(r["dir"] == sub.rstrip("/") for r in rows), flush=True)
    time.sleep(0.5)
with gzip.open("out/inventory.csv.gz", "wt", newline="") as f:
    w = csv.DictWriter(f, fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)
print("total", len(rows))
