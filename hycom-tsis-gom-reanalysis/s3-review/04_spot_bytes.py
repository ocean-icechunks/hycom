"""Compare actual data bytes, S3 vs data.hycom.org, for files where a match matters most.

Size and header offsets (02_sample_layouts.py) cannot tell a regenerated file from the old one
if the layout is unchanged, and the S3 ETags are multipart, so for each file here hash the same
three 1 MiB ranges (start, middle, end) on both sides. Default list: the five 2002 3z files
HYCOM regenerated on 2026-11-10 (keeping the old ones as *_CORRUPTED), plus the old
*_CORRUPTED versions read from HYCOM, to show whether S3 holds the new or the old bytes.
"""
import hashlib, sys, time
import requests

S3 = "https://hycom-tsis-gom-reanalysis.s3.us-west-2.amazonaws.com/data/"
HYCOM = "https://data.hycom.org/datasets/GOMb0.01/reanalysis/data/"
KEYS = sys.argv[1:] or [f"2002/010_archv.2002_{x}_3z.nc" for x in ("046_12", "046_16", "051_06", "051_07", "051_09")]


def sample(url, size):
    out = []
    for start in (0, size // 2, size - 2**20):
        r = requests.get(url, headers={"Range": f"bytes={start}-{start + 2**20 - 1}"}, timeout=120)
        r.raise_for_status(); out.append(hashlib.md5(r.content).hexdigest()[:8]); time.sleep(0.2)
    return out


for k in KEYS:
    size = int(requests.get(S3 + k, headers={"Range": "bytes=0-0"}).headers["content-range"].split("/")[1])
    a, b = sample(S3 + k, size), sample(HYCOM + k, size)
    c = sample(HYCOM + k + "_CORRUPTED", size)
    print(f"{k}  s3={a}  hycom={b}  hycom_CORRUPTED={c}  s3==hycom:{a == b}  s3==corrupted:{a == c}", flush=True)
