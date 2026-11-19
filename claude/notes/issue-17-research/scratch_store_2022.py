"""The 2022 scratch store on Source Cooperative (#17, step 4), and its remote read test.

    python scratch_store_2022.py build <scans.pkl> [d=1]   # write s3://ocean-icechunks/test-repo/hycom/hycom-tsis-gom-reanalysis
    python scratch_store_2022.py read [d=1]                # open it anonymously from the public URL and time the reads

`build` reuses the 2022 scan from year_test.py, writes a skeleton and one commit per month, the
same as the local test, and checks the Source Cooperative token before every batch. `read` is
what a reader does: anonymous HTTPS for the repository, anonymous HTTPS for the source bytes.
Each prints one JSON line of results at the end.
"""
import gc
import json
import pickle
import resource
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "hycom-tsis-gom-reanalysis"))
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
import xarray as xr
import zarr
import icechunk
import h5py
import gom_virtual as gv
from obspec_utils.readers import BlockStoreReader

BUCKET = "ocean-icechunks"
PREFIX = "test-repo/hycom/hycom-tsis-gom-reanalysis"
PUBLIC = f"https://data.source.coop/{BUCKET}/{PREFIX}"
T = time.perf_counter


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def rss_gb():
    return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2**20, 2)


def build(scan_file: str, d: int):
    from icechunk_utils import open_source_icechunk_repo
    zarr.config.set({"async.concurrency": 128})
    R = {"d": d, "url": PUBLIC}
    scans, _ = pickle.loads(Path(scan_file).read_bytes())
    store = gv.source_store()
    year = gv.hourly_axis(pd.Timestamp("2022-01-01"), pd.Timestamp("2022-12-31 23:00"))
    files, _ = gv.select_files(gv.list_keys(store, [2022]))
    files = files[files.time.isin(year)]
    assert set(files.key) == set(scans), "scan does not match the current listing; re-scan"
    k2 = files[files.kind == "2d"].key.iloc[0]; k3 = files[files.kind == "3z"].key.iloc[0]
    grid = gv.read_grid(store, k2, k3); topo = gv.read_topo(store, grid)
    src_attrs = {**scans[k2]["attrs"], **scans[k3]["attrs"]}

    def repo_now(config):
        repo, _s, _c, left = open_source_icechunk_repo(BUCKET, PREFIX, config=config,
                                                       min_minutes_left=30, verbose=False)
        assert repo is not None, "Source Cooperative token too close to expiry; run source-coop login"
        return repo

    repo = repo_now(gv.repository_config())
    repo.save_config()                       # so an anonymous reader finds the virtual container
    # #21: build through a handle with no chunk-reference cache; the saved config keeps the default
    repo = repo_now(gv.build_config_override())
    t = T()
    skeleton = xr.merge([gv.loaded_variables(year, files, grid, topo, scans),
                         gv.virtual_variables(year, files.iloc[:0], {}, d, src_attrs)])
    skeleton.attrs = gv.global_attrs(scans[k2]["global_attrs"])
    s = repo.writable_session("main"); skeleton.vz.to_icechunk(s.store, group=gv.GROUP, mode="w")
    s.commit("skeleton: coordinates, flags, bathy, mask and empty science arrays (2022 scratch copy)")
    del skeleton
    gc.collect()                             # #21: `.vz` leaves the Dataset in a reference cycle
    R["skeleton_s"] = round(T() - t, 1); log(f"skeleton {R['skeleton_s']}s")
    R["months"] = []
    for month in pd.period_range(year[0], year[-1], freq="M"):
        where = np.flatnonzero((year >= month.start_time) & (year <= month.end_time))
        a, b = int(where[0]), int(where[-1]) + 1
        t = T()
        repo = repo_now(gv.build_config_override())   # fresh credentials per batch (they renew themselves)
        batch = gv.virtual_variables(year[a:b], files, scans, d, src_attrs)
        n = int(sum((batch[v].data.manifest._paths != "").sum() for v in batch))
        s = repo.writable_session("main")
        batch.vz.to_icechunk(s.store, group=gv.GROUP, region={"MT": slice(a, b)})
        s.commit(f"references for {month}: {n:,} chunks")
        del batch, s
        gc.collect()                         # #21: frees the batch; `del` alone does not
        R["months"].append({"month": str(month), "refs": n, "s": round(T() - t, 1)})
        log(f"{month} {n:,} refs {T() - t:.1f}s rss {rss_gb()} GB")
    R["refs"] = sum(m["refs"] for m in R["months"])
    R["batches_s"] = round(sum(m["s"] for m in R["months"]), 1)
    R["rss_peak_gb"] = rss_gb()
    print(json.dumps(R, indent=1))


def read(d: int):
    zarr.config.set({"async.concurrency": 128})
    R = {"d": d, "url": PUBLIC}
    t = T()
    repo = icechunk.Repository.open(icechunk.http_storage(PUBLIC))
    R["repo_open_s"] = round(T() - t, 2)
    auth = {p: icechunk.credentials.HttpAccess for p in repo.config.virtual_chunk_containers}
    R["containers"] = list(repo.config.virtual_chunk_containers)
    t = T()
    ds = xr.open_zarr(repo.reopen(authorize_virtual_chunk_access=auth).readonly_session("main").store,
                      group=gv.GROUP, consolidated=False, chunks=None)
    R["open_zarr_s"] = round(T() - t, 2)
    R["commits"] = sum(1 for _ in repo.ancestry(branch="main"))
    row, col = 600, 1000
    inside, across = (slice(400, 600), slice(600, 800)), (slice(300, 500), slice(450, 650))
    tests = {   # first read of each kind is cold: its manifests come from Source Cooperative
        "water_temp map, 1 depth, 1 hour (cold)": lambda: ds.water_temp.isel(MT=2000, Depth=0).values,
        "water_temp map, 1 depth, 1 hour (warm)": lambda: ds.water_temp.isel(MT=2001, Depth=0).values,
        "water_temp map, 1 depth, other month (cold)": lambda: ds.water_temp.isel(MT=7000, Depth=0).values,
        "salinity profile, 40 depths, 1 hour": lambda: ds.salinity.isel(MT=2000, Latitude=row, Longitude=col).values,
        "ssh map, 1 hour (cold)": lambda: ds.ssh.isel(MT=4000).values,
        "water_temp point, 1 depth, year": lambda: ds.water_temp.isel(Depth=0, Latitude=row, Longitude=col).values,
        "water_temp 200x200 box in 1 tile, year": lambda: ds.water_temp.isel(Depth=0, Latitude=inside[0], Longitude=inside[1]).values,
        "water_temp 200x200 box over 4 tiles, year": lambda: ds.water_temp.isel(Depth=0, Latitude=across[0], Longitude=across[1]).values,
    }
    R["reads_s"], R["retries"] = {}, []
    for name, f in tests.items():
        for attempt in range(1, 4):         # S3 now and then returns a 500 on one GET (see the plan)
            t = T()
            try:
                v = f(); break
            except Exception as e:  # noqa: BLE001
                R["retries"].append({"read": name, "attempt": attempt, "error": f"{type(e).__name__}: {str(e)[:160]}"})
                if attempt == 3:
                    raise
        R["reads_s"][name] = round(T() - t, 2)
        log(f"read {name}: {R['reads_s'][name]}s")
    store = gv.source_store()
    key = "2022/023_archv.2022_182_12_3z.nc"
    with h5py.File(BlockStoreReader(store, "data/" + key)) as f:
        want = f["water_temp"][0, 0, row, col]
    R["value_check"] = bool(ds.water_temp.sel(MT=pd.Timestamp("2022-07-01 12:00")).isel(Depth=0, Latitude=row, Longitude=col).values == want)
    R["rss_peak_gb"] = rss_gb()
    print(json.dumps(R, indent=1))


if __name__ == "__main__":
    if sys.argv[1] == "build":
        build(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 1)
    else:
        read(int(sys.argv[2]) if len(sys.argv) > 2 else 1)
