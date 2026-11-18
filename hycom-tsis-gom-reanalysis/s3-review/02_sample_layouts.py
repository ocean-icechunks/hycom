"""Read the HDF5 layout of a sample of S3 files and compare each with (a) the 2009 reference
file the September audit used and (b) the same file on data.hycom.org today.

Sample: first, middle, last and one random file of each experiment and kind on S3; every file
whose size is not one of the usual sizes for its kind (suspected truncated copies); a few
daily-mean files. One file at a time, so HYCOM sees at most one connection from us.

Writes out/sample-layouts.tsv (one row per file).
"""
import hashlib, json, sys, time
import pandas as pd

sys.path.insert(0, "../audit")
from common import PREFIX as HYCOM, layout  # noqa: E402

S3 = "https://hycom-tsis-gom-reanalysis.s3.us-west-2.amazonaws.com/"
REF = {k: f"data/2009/010_archv.2009_084_09_{k}.nc" for k in ("2d", "3z")}

s3 = pd.read_csv("out/s3-listing.csv.gz")
m = s3.key.str.extract(r"^data/\d{4}/(\d{3})_archv\.(\d{4})_(\d{3})_(\d\d)_(2d|3z)\.nc$")
m.columns = ["exp", "yr", "doy", "hr", "kind"]
h = pd.concat([s3, m], axis=1).dropna(subset=["exp"])
h["t"] = pd.to_datetime(h.yr + h.doy, format="%Y%j") + pd.to_timedelta(h.hr.astype(int), "h")

# The usual sizes are the ones held by more than 10 files of a kind; anything else is checked.
common_sizes = h.groupby("kind")["size"].value_counts().loc[lambda s: s > 10]
usual = {k: set(common_sizes.loc[k].index) for k in ("2d", "3z")}
odd = h[[s not in usual[k] for s, k in zip(h["size"], h.kind)]]

pick = list(REF.values())
for _, g in h[~h.key.isin(odd.key)].groupby(["exp", "kind"]):
    g = g.sort_values("t")
    pick += [g.iloc[0].key, g.iloc[len(g) // 2].key, g.iloc[-1].key, g.sample(1, random_state=1).iloc[0].key]
pick += list(odd.key)
daily = s3[s3.key.str.startswith("data/daily_netcdf/")].key
pick += [k for k in daily if any(s in k for s in ("2010_001", "2024_200", "2025_200", "2026_100"))]
pick = list(dict.fromkeys(pick))


def digest(x):
    return hashlib.md5(json.dumps(x, default=str).encode()).hexdigest()[:8]


def summary(url):
    try:
        x = layout(url)
    except Exception as e:  # truncated files and missing sources land here
        return dict(error=f"{type(e).__name__}: {str(e)[:80]}")
    dv = {k: v for k, v in x["vars"].items() if len(v["shape"]) > 2}
    return dict(size=x["size"], offs=digest({k: v["offs"] for k, v in x["vars"].items()}),
                schema=digest({k: [v["shape"], v["chunks"], v["comp"], v["fill"]] for k, v in x["vars"].items()}),
                exp_attr=x["gattrs"].get("experiment"),
                chunks=" ".join(f"{k}{list(v['chunks'])}" for k, v in dv.items()))


rows = []
for key in pick:
    a = summary(S3 + key)
    b = summary(HYCOM + key.removeprefix("data/"))
    r = dict(key=key, **{f"s3_{k}": v for k, v in a.items()}, **{f"hycom_{k}": v for k, v in b.items()})
    rows.append(r)
    print(json.dumps(r), flush=True)
    time.sleep(0.3)

df = pd.DataFrame(rows)
ref = df.set_index("key")
for k, p in REF.items():
    sel = df.key.str.endswith(f"_{k}.nc")
    df.loc[sel, "schema_as_ref"] = df.loc[sel, "s3_schema"] == ref.loc[p, "s3_schema"]
df["same_as_hycom"] = (df.s3_size == df.hycom_size) & (df.s3_offs == df.hycom_offs)
df.to_csv("out/sample-layouts.tsv", sep="\t", index=False)
