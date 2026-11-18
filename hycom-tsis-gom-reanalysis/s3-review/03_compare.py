"""Compare the S3 copy with HYCOM's listing today, and HYCOM today with the September audit.

Reads out/s3-listing.csv.gz, out/hycom-listing.csv.gz (01_inventories.py) and
../audit/out/inventory.csv.gz (HYCOM as of 2026-09-25). Prints a report to stdout; run as
  python 03_compare.py | tee out/compare.txt
Writes out/s3-vs-hycom.csv.gz (one row per key on either side, with a status).

HYCOM's listed sizes are rounded ("74M", "2.4G"), so a size mismatch here means the rounded
values disagree. The exact size of every S3 file whose size is unusual is fetched from
HYCOM with a 1-byte ranged GET, one request at a time.
"""
import re, time
import pandas as pd
import requests

HYCOM = "https://data.hycom.org/datasets/GOMb0.01/reanalysis/"
pd.set_option("display.width", 200)

s3 = pd.read_csv("out/s3-listing.csv.gz")
hy = pd.read_csv("out/hycom-listing.csv.gz", dtype=str)
sep = pd.read_csv("../audit/out/inventory.csv.gz", dtype=str)
sep["key"] = "data/" + sep.dir + "/" + sep.name

s3 = s3[s3.key.str.startswith("data/")]
HOURLY = r"^data/\d{4}/(\d{3})_archv\.(\d{4})_(\d{3})_(\d\d)_(2d|3z)\.nc$"


def tag(df):
    m = df.key.str.extract(HOURLY); m.columns = ["exp", "yr", "doy", "hr", "kind"]
    df = pd.concat([df.reset_index(drop=True), m], axis=1)
    df["t"] = pd.to_datetime(df.yr + df.doy, format="%Y%j", errors="coerce") + pd.to_timedelta(df.hr.astype(float), "h")
    df["daily"] = df.key.str.startswith("data/daily_netcdf/")
    return df


def rounded(n):
    """Apache's rounding of a byte count, e.g. 77566331 -> '74M', 2592206800 -> '2.4G'."""
    for unit, p in (("G", 3), ("M", 2), ("K", 1)):
        v = n / 1024 ** p
        if v >= 1:
            return f"{v:.1f}{unit}" if v < 9.95 else f"{round(v)}{unit}"
    return str(n)


j = s3.merge(hy, on="key", how="outer", suffixes=("_s3", "_hy"), indicator=True)
j = tag(j)
j["status"] = j["_merge"].map({"both": "both", "left_only": "s3 only", "right_only": "hycom only"})
both = j["_merge"] == "both"
j.loc[both, "size_match"] = [rounded(int(a)) == b for a, b in zip(j.loc[both, "size_s3"], j.loc[both, "size_hy"])]
# HYCOM's listing time is local (US Eastern, it seems); compare at day resolution only.
j["hy_mod"] = pd.to_datetime(j.modified_hy)
j["s3_mod"] = pd.to_datetime(j.modified_s3).dt.tz_localize(None)
j["hycom_changed_after_copy"] = both & (j.hy_mod > j.s3_mod + pd.Timedelta("1D"))

print("== S3 vs HYCOM today, by key")
print(j.groupby(["daily", "status"]).size().to_string(), "\n")
print("rounded sizes disagree on", int((j.size_match == False).sum()), "of", int(both.sum()), "shared keys")  # noqa: E712
print(j[j.size_match == False][["key", "size_s3", "size_hy"]].head(40).to_string(), "\n")  # noqa: E712
print("HYCOM modified more than a day after the S3 copy:", int(j.hycom_changed_after_copy.sum()))
print(j[j.hycom_changed_after_copy][["key", "s3_mod", "hy_mod"]].head(20).to_string(), "\n")

hourly = j[j.exp.notna()]
print("== hourly files by experiment and status")
print(hourly.groupby(["exp", "kind", "status"]).agg(n=("key", "size"), first=("t", "min"), last=("t", "max")).to_string(), "\n")

s3only = j[(j.status == "s3 only")]
print("== S3-only keys that are not experiment 028:")
print(s3only[s3only.exp != "028"][["key", "size_s3"]].to_string(), "\n")

hyonly = j[(j.status == "hycom only") & j.exp.notna()]
print("== HYCOM-only hourly keys: not yet copied, or left out on purpose")
small = hyonly[~hyonly.size_hy.str.endswith(("G", "M"))]
print("tiny (empty 3z) files on HYCOM not on S3:", len(small))
odd_names = j[j.exp.isna() & ~j.daily]
print("non-standard names, either side:"); print(odd_names[["key", "status", "size_s3", "size_hy"]].to_string(), "\n")

print("== HYCOM today vs the September audit (hourly + daily)")
hs = hy.merge(sep[["key", "modified", "size"]], on="key", how="outer", suffixes=("", "_sep"), indicator=True)
print(hs["_merge"].map({"both": "both", "left_only": "new since Sept", "right_only": "gone since Sept"}).value_counts().to_string())
print("gone since Sept:"); print(hs[hs["_merge"] == "right_only"][["key", "size_sep", "modified_sep"]].to_string())
chg = hs[(hs["_merge"] == "both") & (hs.modified != hs.modified_sep)]
print("modified since Sept:", len(chg))
if len(chg):
    c = tag(chg[["key", "modified", "size", "size_sep"]].copy())
    c["mod_day"] = c.modified.str[:10]
    print(c.groupby(["mod_day", "exp", "kind"]).agg(n=("key", "size"), first=("t", "min"), last=("t", "max")).to_string())
    print("of which copied to S3 before HYCOM changed them:",
          int(j[j.key.isin(chg.key)].hycom_changed_after_copy.sum()))
print()

print("== exact sizes on HYCOM for S3 files with unusual sizes")
h3 = hourly[hourly.status != "hycom only"].copy()
h3["size_s3"] = h3.size_s3.astype("int64")
usual = h3.groupby("kind").size_s3.value_counts().loc[lambda s: s > 10]
odd = h3[[(k, s) not in usual.index for k, s in zip(h3.kind, h3.size_s3)]]
for _, r in odd.iterrows():
    resp = requests.get(HYCOM + r.key, headers={"Range": "bytes=0-0"}, timeout=60)
    exact = resp.headers.get("content-range", "").split("/")[-1] if resp.status_code == 206 else f"HTTP {resp.status_code}"
    print(f"{r.key:48s} s3={r.size_s3:>11d} hycom={exact}")
    time.sleep(0.3)

j.drop(columns=["_merge"]).to_csv("out/s3-vs-hycom.csv.gz", index=False)
