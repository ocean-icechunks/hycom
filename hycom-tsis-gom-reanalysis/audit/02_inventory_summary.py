"""Summarise out/inventory.csv.gz: experiments, time coverage, duplicates, gaps, odd files, edits.
Offline. Writes out/inventory-summary.txt and out/problem-files.csv."""
import re, sys, pandas as pd

out = open("out/inventory-summary.txt", "w")
def p(*a):
    print(*a); print(*a, file=out)

df = pd.read_csv("out/inventory.csv.gz", dtype=str)
daily = df[df.dir == "daily_netcdf"]; df = df[df.dir != "daily_netcdf"]
p(f"hourly files listed: {len(df)}; daily_netcdf year dirs: {len(daily)}")
m = df.name.str.extract(r"^(\d+)_archv\.(\d{4})_(\d{3})_(\d\d)_(2d|3z)\.nc$"); m.columns = ["exp", "yr", "doy", "hr", "kind"]
odd = df[m.exp.isna()]
p(f"\nfiles not matching NNN_archv.YYYY_DDD_HH_{{2d,3z}}.nc: {len(odd)}"); p(odd.to_string(index=False))
df = pd.concat([df, m], axis=1).dropna(subset=["exp"]).copy()
df["t"] = pd.to_datetime(df.yr + df.doy, format="%Y%j") + pd.to_timedelta(df.hr.astype(int), "h")
df["mod"] = pd.to_datetime(df.modified)
p("\nper experiment (sizes as listed, rounded):")
p(df.groupby(["exp", "kind"]).agg(files=("t", "size"), first=("t", "min"), last=("t", "max"),
                                  sizes=("size", lambda s: dict(s.value_counts()))).to_string())
tiny = df[df["size"].isin(["49K", "239"])]
p(f"\ntiny 3z files (zero time steps inside; see report F5): {len(tiny)}"); p(tiny[["dir", "name", "modified", "size"]].to_string(index=False))
good = df[~df.index.isin(tiny.index)]
for k in ["2d", "3z"]:
    d = good[good.kind == k]
    dup = d[d.t.duplicated(keep=False)]
    p(f"\n{k}: {len(d)} usable files, {d.t.nunique()} distinct hours, {dup.t.nunique()} hours with two files "
      f"({', '.join(sorted(dup.exp.unique()))}: {dup.t.min()} .. {dup.t.max()})")
    full = pd.date_range("2001-01-01", d.t.max(), freq="h"); miss = pd.Series(full.difference(d.t))
    runs = miss.groupby((miss.diff() != pd.Timedelta("1h")).cumsum()).agg(["min", "max", "size"])
    p(f"{k}: hours from 2001-01-01 00Z to {d.t.max()} with no usable file: {len(miss)}"); p(runs.to_string(index=False))
p("\nfiles modified in 2026 (HYCOM is still editing the archive):")
r = df[df["mod"] >= "2026-01-01"]
p(r.groupby([r["mod"].dt.date, "exp", "kind"]).agg(files=("t", "size"), first=("t", "min"), last=("t", "max")).to_string())
p("\nfiles by month last modified:")
p(df.groupby([df["mod"].dt.to_period("M"), "kind"]).size().unstack(fill_value=0).to_string())
pd.concat([odd.assign(problem="unexpected name"), tiny.assign(problem="zero time steps"),
           df[df.duplicated(["t", "kind"], keep=False)].assign(problem="026/027 overlap")])[["dir", "name", "modified", "size", "problem"]] \
  .to_csv("out/problem-files.csv", index=False)
