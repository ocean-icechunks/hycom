"""The 2022 test year (#17, step 3): build one year at several 3z chunkings and time the reads.

One scan serves every chunking. For each d it builds a LOCAL repository under <out_dir>/d<d>,
writing a skeleton over the year and one region-write commit per month, the way production will.
It then reopens the repository read-only and times the reads in the plan's table. Results go to
<out_dir>/results-d<d>.json as each chunking finishes, so a slow d=10 never hides the others.

    python year_test.py <out_dir> [year=2022] [d,d,...=1,2,10]

Nothing is written outside <out_dir>. The one-month check (month_check.py) ran first; see the plan.
"""
import json
import pickle
import resource
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "hycom-tsis-gom-reanalysis"))

import numpy as np
import pandas as pd
import xarray as xr
import zarr
import icechunk
import h5py
import gom_virtual as gv
from obspec_utils.readers import BlockStoreReader

T = time.perf_counter


def rss_gb():
    return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2**20, 2)


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def build(out: Path, d: int, year, files, scans, grid, topo, src_attrs, gattrs) -> dict:
    R = {"d": d}
    repo = icechunk.Repository.create(icechunk.local_filesystem_storage(str(out)), gv.repository_config())
    repo.save_config()
    t = T()
    skeleton = xr.merge([gv.loaded_variables(year, files, grid, topo, scans),
                         gv.virtual_variables(year, files.iloc[:0], {}, d, src_attrs)])
    skeleton.attrs = gattrs
    s = repo.writable_session("main"); skeleton.vz.to_icechunk(s.store, group=gv.GROUP, mode="w")
    s.commit("skeleton: coordinates, flags, bathy, mask and empty science arrays")
    del skeleton
    R["skeleton_s"] = round(T() - t, 1)
    R["months"], refs = [], 0
    t_all = T()
    for month in pd.period_range(year[0], year[-1], freq="M"):
        where = np.flatnonzero((year >= month.start_time) & (year <= month.end_time))
        a, b = int(where[0]), int(where[-1]) + 1
        t = T()
        batch = gv.virtual_variables(year[a:b], files, scans, d, src_attrs)
        n = int(sum((batch[v].data.manifest._paths != "").sum() for v in batch))
        s = repo.writable_session("main")
        batch.vz.to_icechunk(s.store, group=gv.GROUP, region={"MT": slice(a, b)})
        s.commit(f"references for {month}: {n:,} chunks")
        del batch
        refs += n
        R["months"].append({"month": str(month), "refs": n, "s": round(T() - t, 1)})
        log(f"d={d} {month} {n:,} refs {T() - t:.1f}s rss {rss_gb()} GB")
    R["batches_s"] = round(T() - t_all, 1)
    R["refs"] = refs
    R["rss_after_build_gb"] = rss_gb()
    R["repo_mb"] = round(sum(f.stat().st_size for f in out.rglob("*") if f.is_file()) / 1e6, 1)
    R["manifest_mb"] = round(sum(f.stat().st_size for f in (out / "manifests").rglob("*") if f.is_file()) / 1e6, 1)
    return R


def reads(out: Path, d: int, store, check_key: str, check_time) -> dict:
    R = {}
    t = T()
    repo = icechunk.Repository.open(icechunk.local_filesystem_storage(str(out)),
                                    authorize_virtual_chunk_access=gv.reader_authorization())
    ds = xr.open_zarr(repo.readonly_session("main").store, group=gv.GROUP, consolidated=False, chunks=None)
    R["open_s"] = round(T() - t, 2)
    row, col = 600, 1000                                   # the audit's test point
    inside, across = (slice(400, 600), slice(600, 800)), (slice(300, 500), slice(450, 650))
    tests = {
        "water_temp map, 1 depth, 1 hour": lambda: ds.water_temp.isel(MT=2000, Depth=0).values,
        "salinity profile, 40 depths, 1 hour": lambda: ds.salinity.isel(MT=2000, Latitude=row, Longitude=col).values,
        "water_temp point, 1 depth, year": lambda: ds.water_temp.isel(Depth=0, Latitude=row, Longitude=col).values,
        "water_temp 200x200 box in 1 tile, year": lambda: ds.water_temp.isel(Depth=0, Latitude=inside[0], Longitude=inside[1]).values,
        "water_temp 200x200 box over 4 tiles, year": lambda: ds.water_temp.isel(Depth=0, Latitude=across[0], Longitude=across[1]).values,
    }
    if d == 1:                       # 2d is whole maps at every d; time it once
        tests["ssh point, year"] = lambda: ds.ssh.isel(Latitude=row, Longitude=col).values
    R["reads_s"], R["reads_nan"], R["read_retries"] = {}, {}, []
    for name, f in tests.items():
        # S3 now and then answers one of thousands of ranged GETs with a 500 InternalError ("Please
        # try again"), and Icechunk hands it straight to the reader (seen 2026-11-19, 35,040-chunk
        # read). Retry the whole read and record it, so the timing is honest about it.
        for attempt in range(1, 4):
            t = T()
            try:
                v = f(); break
            except Exception as e:  # noqa: BLE001
                R["read_retries"].append({"read": name, "attempt": attempt, "after_s": round(T() - t, 1),
                                          "error": f"{type(e).__name__}: {str(e)[:200]}"})
                log(f"d={d} read {name}: attempt {attempt} failed after {T() - t:.1f}s: {type(e).__name__}")
                if attempt == 3:
                    raise
        R["reads_s"][name] = round(T() - t, 1); R["reads_nan"][name] = int(np.isnan(v).sum())
        log(f"d={d} read {name}: {R['reads_s'][name]}s")
    with h5py.File(BlockStoreReader(store, "data/" + check_key)) as f:
        want = f["water_temp"][0, 0, row, col]
    R["value_check"] = bool(ds.water_temp.sel(MT=check_time).isel(Depth=0, Latitude=row, Longitude=col).values == want)
    R["cell_methods_3z_counts"] = {int(k): int(v) for k, v in zip(*np.unique(ds.cell_methods_3z.values, return_counts=True))}
    R["cell_methods_2d_counts"] = {int(k): int(v) for k, v in zip(*np.unique(ds.cell_methods_2d.values, return_counts=True))}
    R["experiment_counts"] = {int(k): int(v) for k, v in zip(*np.unique(ds.experiment.values, return_counts=True))}
    R["rss_after_reads_gb"] = rss_gb()
    return R


def main():
    out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    yr = int(sys.argv[2]) if len(sys.argv) > 2 else 2022
    ds_list = [int(x) for x in (sys.argv[3] if len(sys.argv) > 3 else "1,2,10").split(",")]
    zarr.config.set({"async.concurrency": 128})
    store = gv.source_store()
    year = gv.hourly_axis(pd.Timestamp(f"{yr}-01-01"), pd.Timestamp(f"{yr}-12-31 23:00"))
    files, _ = gv.select_files(gv.list_keys(store, [yr]))
    files = files[files.time.isin(year)]

    scan_file = out / "scans.pkl"
    if scan_file.exists():
        scans, report = pickle.loads(scan_file.read_bytes())
        log(f"scan reused from {scan_file}")
    else:
        t = T(); scans, report = gv.scan_files(files, "h5py", workers=16)
        scan = {"files": len(files), "scan_s": round(T() - t, 1), "files_per_s": round(len(files) / (T() - t), 1),
                "errors": report.dropna(subset=["error"])[["key", "error"]].values.tolist(),
                "fingerprints": report.fingerprint.value_counts(dropna=False).to_dict(),
                "cell_methods": pd.Series([s["cell_methods"] for s in scans.values()]).value_counts(dropna=False).to_dict(),
                "coords_md5": pd.DataFrame([s["coords_md5"] for s in scans.values()]).astype(str).value_counts().reset_index().values.tolist()}
        (out / "results-scan.json").write_text(json.dumps(scan, indent=1, default=str))
        scan_file.write_bytes(pickle.dumps((scans, report)))
        log(f"scanned {len(files)} files in {scan['scan_s']}s ({scan['files_per_s']}/s), errors {len(scan['errors'])}")

    k2 = files[files.kind == "2d"].key.iloc[0]; k3 = files[files.kind == "3z"].key.iloc[0]
    grid = gv.read_grid(store, k2, k3); topo = gv.read_topo(store, grid)
    src_attrs = {**scans[k2]["attrs"], **scans[k3]["attrs"]}
    gattrs = gv.global_attrs(scans[k2]["global_attrs"])
    check_time = pd.Timestamp(f"{yr}-07-01 12:00")
    check_key = files[(files.kind == "3z") & (files.time == check_time)].key.iloc[0]

    for d in ds_list:
        if (out / f"results-d{d}.json").exists():
            log(f"d={d} already done"); continue
        t = T()
        built = out / f"build-d{d}.json"
        if built.exists():           # built before, reads failed: reuse the build
            R = json.loads(built.read_text()); log(f"d={d} build reused")
        else:
            R = build(out / f"d{d}", d, year, files, scans, grid, topo, src_attrs, gattrs)
            built.write_text(json.dumps(R, indent=1))
        R.update(reads(out / f"d{d}", d, store, check_key, check_time))
        R["total_s"] = round(T() - t, 1)
        (out / f"results-d{d}.json").write_text(json.dumps(R, indent=1))
        log(f"d={d} done in {R['total_s']}s")


if __name__ == "__main__":
    main()
