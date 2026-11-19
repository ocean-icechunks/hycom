"""One-month check before the 2022 test year (#17, step 3): January 2022 at d depths per 3z chunk.

Builds the way the 2022 test will: a skeleton over all of 2022, then one month as one region-write
batch, in a LOCAL repository under <out_dir>. Measures time and peak memory at each stage, then
reopens read-only and times the reads in the plan's table, restricted to the month.

    python month_check.py <out_dir> [d=1] [month=2022-01]

Prints one JSON line of results at the end. Nothing is written outside <out_dir>.
"""
import json
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


def rss_gb():
    """Peak resident set of this process so far (Linux reports KiB)."""
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2**20


def main():
    out = Path(sys.argv[1]); d = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    month = pd.Period(sys.argv[3] if len(sys.argv) > 3 else "2022-01", "M")
    zarr.config.set({"async.concurrency": 128})
    R, T = {"d": d, "month": str(month)}, time.perf_counter
    store = gv.source_store()

    t = T(); files, skipped = gv.select_files(gv.list_keys(store, [month.year]))
    R["list_s"] = round(T() - t, 1)
    year = gv.hourly_axis(pd.Timestamp(f"{month.year}-01-01"), pd.Timestamp(f"{month.year}-12-31 23:00"))
    mtimes = year[(year >= month.start_time) & (year <= month.end_time)]
    mfiles = files[files.time.isin(mtimes)]
    R["files"] = len(mfiles)

    t = T(); scans, report = gv.scan_files(mfiles, "h5py", workers=16)
    R["scan_s"] = round(T() - t, 1); R["scan_files_per_s"] = round(len(mfiles) / R["scan_s"], 1)
    R["scan_errors"] = report.error.dropna().tolist()
    R["fingerprints"] = report.fingerprint.value_counts(dropna=False).to_dict()
    R["cell_methods"] = pd.Series([s["cell_methods"] for s in scans.values()]).value_counts(dropna=False).to_dict()
    R["rss_after_scan_gb"] = round(rss_gb(), 2)

    k2 = mfiles[mfiles.kind == "2d"].key.iloc[0]; k3 = mfiles[mfiles.kind == "3z"].key.iloc[0]
    grid = gv.read_grid(store, k2, k3); topo = gv.read_topo(store, grid)
    src_attrs = {**scans[k2]["attrs"], **scans[k3]["attrs"]}

    repo = icechunk.Repository.create(icechunk.local_filesystem_storage(str(out)), gv.repository_config())
    repo.save_config()
    t = T()
    # The skeleton spans the whole year. Its loaded flags use only this month's scans, which is fine
    # for a check: the other months read as "no source file".
    skeleton = xr.merge([gv.loaded_variables(year, mfiles, grid, topo, scans),
                         gv.virtual_variables(year, mfiles.iloc[:0], {}, d, src_attrs)])
    skeleton.attrs = gv.global_attrs(scans[k2]["global_attrs"])
    R["skeleton_build_s"] = round(T() - t, 1); R["rss_after_skeleton_build_gb"] = round(rss_gb(), 2)
    t = T(); s = repo.writable_session("main"); skeleton.vz.to_icechunk(s.store, group=gv.GROUP, mode="w")
    s.commit("skeleton"); R["skeleton_write_s"] = round(T() - t, 1)
    del skeleton
    R["rss_after_skeleton_gb"] = round(rss_gb(), 2)

    a, b = year.get_loc(mtimes[0]), year.get_loc(mtimes[-1]) + 1
    t = T(); batch = gv.virtual_variables(year[a:b], mfiles, scans, d, src_attrs)
    R["refs"] = int(sum((batch[v].data.manifest._paths != "").sum() for v in batch))
    R["batch_build_s"] = round(T() - t, 1)
    t = T(); s = repo.writable_session("main")
    batch.vz.to_icechunk(s.store, group=gv.GROUP, region={"MT": slice(a, b)})
    s.commit(f"references for {month}"); R["batch_write_commit_s"] = round(T() - t, 1)
    R["rss_after_batch_gb"] = round(rss_gb(), 2)
    del batch
    R["repo_mb"] = round(sum(f.stat().st_size for f in out.rglob("*") if f.is_file()) / 1e6, 1)
    R["manifest_mb"] = round(sum(f.stat().st_size for f in (out / "manifests").rglob("*") if f.is_file()) / 1e6, 1)

    # Fresh read-only session, as a reader would.
    t = T()
    rrepo = icechunk.Repository.open(icechunk.local_filesystem_storage(str(out)),
                                     authorize_virtual_chunk_access=gv.reader_authorization())
    ds = xr.open_zarr(rrepo.readonly_session("main").store, group=gv.GROUP, consolidated=False, chunks=None)
    R["open_s"] = round(T() - t, 2)
    m = ds.sel(MT=slice(mtimes[0], mtimes[-1]))
    row, col = 600, 1000
    inside, across = (slice(400, 600), slice(600, 800)), (slice(300, 500), slice(450, 650))
    reads = {
        "water_temp map, 1 depth, 1 hour": lambda: m.water_temp.isel(MT=100, Depth=0).values,
        "salinity profile, 40 depths, 1 hour": lambda: m.salinity.isel(MT=100, Latitude=row, Longitude=col).values,
        "water_temp point, 1 depth, month": lambda: m.water_temp.isel(Depth=0, Latitude=row, Longitude=col).values,
        "water_temp 200x200 box in 1 tile, month": lambda: m.water_temp.isel(Depth=0, Latitude=inside[0], Longitude=inside[1]).values,
        "water_temp 200x200 box over 4 tiles, month": lambda: m.water_temp.isel(Depth=0, Latitude=across[0], Longitude=across[1]).values,
        "ssh point, month": lambda: m.ssh.isel(Latitude=row, Longitude=col).values,
    }
    R["reads_s"] = {}
    for name, f in reads.items():
        t = T(); v = f(); R["reads_s"][name] = round(T() - t, 2)
        R.setdefault("reads_nan", {})[name] = int(np.isnan(v).sum())
    # One value check against h5py, the first hour of the month.
    with h5py.File(BlockStoreReader(store, "data/" + k3)) as f:
        want = f["water_temp"][0, 0, row, col]
    R["value_check"] = bool(m.water_temp.isel(MT=0, Depth=0, Latitude=row, Longitude=col).values == want)
    R["rss_peak_gb"] = round(rss_gb(), 2)
    print(json.dumps(R, indent=1))


if __name__ == "__main__":
    main()
