"""Read the HDF5 layout of a sample of files, one at a time, and compare each with a 2009 reference.

Sample: first, middle, last and one random usable file of each experiment and kind; the first
file of each 2026 edit batch; one zero-length 3z file; four daily-mean files.
Writes out/sample-layouts.txt (one line per file) and out/layout-diffs.txt.
"""
import hashlib, json, time, pandas as pd
from common import PREFIX, layout

df = pd.read_csv("out/inventory.csv.gz", dtype=str)
df = df[df.dir != "daily_netcdf"]
m = df.name.str.extract(r"^(\d+)_archv\.(\d{4})_(\d{3})_(\d\d)_(2d|3z)\.nc$"); m.columns = ["exp", "yr", "doy", "hr", "kind"]
df = pd.concat([df, m], axis=1).dropna(subset=["exp"])
df["t"] = pd.to_datetime(df.yr + df.doy, format="%Y%j") + pd.to_timedelta(df.hr.astype(int), "h")
df["mod"] = pd.to_datetime(df.modified)
good = df[~df["size"].isin(["49K", "239"])]
pick = []
for _, g in good.groupby(["exp", "kind"]):
    g = g.sort_values("t"); pick += [g.iloc[0], g.iloc[len(g) // 2], g.iloc[-1], g.sample(1, random_state=1).iloc[0]]
rec = good[good["mod"] >= "2026-01-01"]
for _, g in rec.groupby([rec["mod"].dt.date, "kind"]):
    pick.append(g.iloc[0])
paths = ["2009/010_archv.2009_084_09_2d.nc", "2009/010_archv.2009_084_09_3z.nc"] + [f"{r.dir}/{r['name']}" for r in pick] + [
    "2002/010_archv.2002_347_01_3z.nc",
    "daily_netcdf/2010/gomb1_daily_2010_001_2d.nc", "daily_netcdf/2010/gomb1_daily_2010_001_3z.nc",
    "daily_netcdf/2024/gomb1_daily_2024_200_2d.nc", "daily_netcdf/2024/gomb1_daily_2024_200_3z.nc"]

def h(x): return hashlib.md5(json.dumps(x, default=str).encode()).hexdigest()[:8]
L = {}
with open("out/sample-layouts.txt", "w") as out:
    print("path | exact size | offsets hash | schema hash (shape, chunks, codec, fill) | experiment attr | data-variable chunks", file=out)
    for p in paths:
        L[p] = x = layout(PREFIX + p)
        dv = {k: v for k, v in x["vars"].items() if len(v["shape"]) > 2}
        line = (f"{p:48s} {x['size']:>11d} offs={h({k: v['offs'] for k, v in x['vars'].items()})} "
                f"schema={h({k: [v['shape'], v['chunks'], v['comp'], v['fill']] for k, v in x['vars'].items()})} "
                f"exp={x['gattrs'].get('experiment')} " + " ".join(f"{k}{list(v['chunks'])}" for k, v in dv.items()))
        print(line, flush=True); print(line, file=out)
        time.sleep(0.3)

with open("out/layout-diffs.txt", "w") as out:
    for p, x in L.items():
        ref = L["2009/010_archv.2009_084_09_%s.nc" % ("3z" if "3z" in p else "2d")]
        if x is ref: continue
        lines = []
        for k in sorted(set(ref["vars"]) | set(x["vars"])):
            a, b = ref["vars"].get(k), x["vars"].get(k)
            if a is None or b is None: lines.append(f"  {k}: only in one file"); continue
            lines += [f"  {k}.{f}: {a[f]} -> {b[f]}" for f in ["shape", "chunks", "comp", "fill"] if a[f] != b[f]]
            lines += [f"  {k}@{t}: {a['attrs'].get(t)} -> {b['attrs'].get(t)}" for t in sorted(set(a["attrs"]) | set(b["attrs"]))
                      if not t.startswith("_Netcdf4") and t != "valid_range" and a["attrs"].get(t) != b["attrs"].get(t)]
        lines += [f"  global@{t}: {ref['gattrs'].get(t)!r:.120} -> {x['gattrs'].get(t)!r:.300}" for t in sorted(set(ref["gattrs"]) | set(x["gattrs"]))
                  if ref["gattrs"].get(t) != x["gattrs"].get(t)]
        if lines: print(f"== {p}\n" + "\n".join(lines), file=out)
