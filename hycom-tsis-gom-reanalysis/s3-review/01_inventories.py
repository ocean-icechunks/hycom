"""Snapshot the HYCOM source listing and the S3 bucket listing, so they can be compared.

Run from this directory:  python 01_inventories.py
Writes out/hycom-listing.csv.gz and out/s3-listing.csv.gz.

HYCOM: the Apache directory listings on data.hycom.org, one request at a time with a pause,
as in ../audit/01_inventory.py (the THREDDS catalog is unusably slow). Sizes there are rounded
(74M, 2.4G), so they only catch gross differences. Exact sizes come from a 1-byte ranged GET,
which 03_compare.py does for the files that need it.

S3: the bucket is public and in us-west-2, so an anonymous ListObjectsV2 gives exact sizes.
Its ETags are multipart (the copy used multipart uploads), so they are not MD5s of the file
and cannot be compared with anything on the HYCOM side.
"""
import csv, gzip, re, time
import boto3, requests
from botocore import UNSIGNED
from botocore.config import Config

HYCOM = "https://data.hycom.org/datasets/GOMb0.01/reanalysis/data/"
BUCKET = "hycom-tsis-gom-reanalysis"
ROW = re.compile(r'<a href="([^"]+)">[^<]*</a>\s+(\d{4}-\d\d-\d\d \d\d:\d\d)\s+(\S+)')
DIRS = re.compile(r'<a href="(\d{4}/|daily_netcdf/)">')


def write(path, rows):
    with gzip.open(path, "wt", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)


def hycom_listing():
    # Discover the year directories rather than assume 2001-2024: the S3 copy has 2025 and
    # 2026, and HYCOM may add them.
    # Apache's listing links each directory twice (icon and name), hence dict.fromkeys.
    subs = list(dict.fromkeys(DIRS.findall(requests.get(HYCOM, timeout=300).text)))
    rows = []
    for sub in subs:
        subdirs = [sub]
        if sub == "daily_netcdf/":
            subdirs = [sub + y for y in dict.fromkeys(DIRS.findall(requests.get(HYCOM + sub, timeout=300).text))]
        for s in subdirs:
            html = requests.get(HYCOM + s, timeout=300).text
            n0 = len(rows)
            rows += [dict(key="data/" + s + n, modified=m, size=z) for n, m, z in ROW.findall(html)
                     if not n.endswith("/")]
            print("hycom", s, len(rows) - n0, flush=True)
            time.sleep(0.5)
    return rows


def s3_listing():
    s3 = boto3.client("s3", region_name="us-west-2", config=Config(signature_version=UNSIGNED))
    rows = []
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=BUCKET):
        rows += [dict(key=o["Key"], size=o["Size"], modified=o["LastModified"].isoformat(),
                      etag=o["ETag"].strip('"')) for o in page.get("Contents", [])]
    print("s3", len(rows), flush=True)
    return rows


if __name__ == "__main__":
    write("out/s3-listing.csv.gz", s3_listing())
    write("out/hycom-listing.csv.gz", hycom_listing())
