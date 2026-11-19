"""Memory growth across monthly region writes (ocean-icechunks/hycom#21).

Builds N months of 2022 at d depths per 3z chunk into a LOCAL repository, the way year_test.py
does (skeleton over the whole year, then one region write + commit per month), and records memory
after every step. Each hypothesis in #21 is a switch:

    python mem_experiment.py <work_dir> <run_name> [--months 6] [--d 1]
        [--gc]                 H1  gc.collect() after each batch (its return value is logged)
        [--del-session]        H2  del the session (and its store) right after each commit
        [--reopen-every N]     H2  reopen the Repository object every N months
        [--cache-refs K]       H3  CachingConfig(num_chunk_refs=K); icechunk 2.3.1 default 15,000,000
        [--split-hours H]      H4  manifest split along MT (gom_virtual default 730)
        [--malloc-trim]        H5  glibc malloc_trim(0) after each batch
        [--fresh-process]      control: one month per fresh interpreter (same repository)
        [--tracemalloc]        Python-heap current/peak per batch (slows the run)

Memory is read from /proc/self: "rss" is current RSS (statm), "hwm" is the peak RSS since the
last reset. The script resets the peak (/proc/self/clear_refs, "5") at the start of each batch, so
"hwm" is the peak *within that batch*; "maxrss" is ru_maxrss, the whole-process peak that
year_test.py logged. Results go to <work_dir>/<run_name>.json, one row per batch.

Inputs: <work_dir>/../year2022/scans.pkl (the 2022 scan, reused so nothing is re-scanned), and the
grid and topo, read once from the public source bucket and cached in <work_dir>/grid_topo.pkl.
Nothing is written outside <work_dir>.
"""
import argparse
import ctypes
import gc
import json
import os
import pickle
import resource
import subprocess
import sys
import time
import tracemalloc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "hycom-tsis-gom-reanalysis"))

import numpy as np
import pandas as pd
import xarray as xr
import zarr
import icechunk
import gom_virtual as gv

T = time.perf_counter
PAGE = os.sysconf("SC_PAGE_SIZE")
GB = 2**30


def rss():
    return int(open("/proc/self/statm").read().split()[1]) * PAGE / GB


def hwm():
    for line in open("/proc/self/status"):
        if line.startswith("VmHWM:"):
            return int(line.split()[1]) * 1024 / GB


def reset_hwm():
    try:
        Path("/proc/self/clear_refs").write_text("5")
    except OSError:
        pass


def maxrss():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2**20


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def inputs(work: Path):
    """files, scans, grid, topo, src_attrs, gattrs for 2022, with no scan of S3."""
    scans, _ = pickle.loads((work.parent / "year2022" / "scans.pkl").read_bytes())
    rows = []
    for key in scans:
        m = gv.KEY_RE.match(key)
        rows.append(dict(key=key, size=0, modified=None, time=gv.time_of(m["year"], m["day"], m["hour"]),
                         kind=m["kind"], experiment=int(m["exp"])))
    files = pd.DataFrame(rows).sort_values(["time", "kind"]).reset_index(drop=True)
    k2 = files[files.kind == "2d"].key.iloc[0]; k3 = files[files.kind == "3z"].key.iloc[0]
    cache = work / "grid_topo.pkl"
    if cache.exists():
        grid, topo = pickle.loads(cache.read_bytes())
    else:
        store = gv.source_store()
        grid = gv.read_grid(store, k2, k3); topo = gv.read_topo(store, grid)
        cache.write_bytes(pickle.dumps((grid, topo)))
    src_attrs = {**scans[k2]["attrs"], **scans[k3]["attrs"]}
    return files, scans, grid, topo, src_attrs, gv.global_attrs(scans[k2]["global_attrs"])


def config(a):
    c = gv.repository_config(a.split_hours)
    if a.cache_refs is not None:
        c.caching = icechunk.CachingConfig(num_chunk_refs=a.cache_refs)
    return c


def open_repo(path: Path, a):
    return icechunk.Repository.open(icechunk.local_filesystem_storage(str(path)), config(a))


def one_month(repo, i, year, files, scans, a, R):
    month = pd.period_range(year[0], year[-1], freq="M")[i]
    where = np.flatnonzero((year >= month.start_time) & (year <= month.end_time))
    lo, hi = int(where[0]), int(where[-1]) + 1
    row = {"month": str(month), "rss_start": rss()}
    reset_hwm()
    if a.tracemalloc:
        tracemalloc.reset_peak()
    t = T()
    batch = gv.virtual_variables(year[lo:hi], files, scans, a.d, R["src_attrs"])
    row["refs"] = int(sum((batch[v].data.manifest._paths != "").sum() for v in batch))
    row["rss_batch_built"] = rss()
    s = repo.writable_session("main")
    batch.vz.to_icechunk(s.store, group=gv.GROUP, region={"MT": slice(lo, hi)})
    row["rss_written"] = rss()
    s.commit(f"references for {month}: {row['refs']:,} chunks")
    row["rss_committed"] = rss()
    del batch
    if a.del_session:
        del s
    row["rss_after_del"] = rss()
    if a.gc:
        row["gc_found"] = gc.collect()
        row["rss_after_gc"] = rss()
    if a.malloc_trim:
        row["malloc_trim"] = ctypes.CDLL("libc.so.6").malloc_trim(0)
        row["rss_after_trim"] = rss()
    if a.tracemalloc:
        cur, peak = tracemalloc.get_traced_memory()
        row["py_heap_gb"], row["py_heap_peak_gb"] = cur / GB, peak / GB
    row["hwm_batch"], row["maxrss"], row["rss_end"], row["s"] = hwm(), maxrss(), rss(), T() - t
    row = {k: (round(v, 3) if isinstance(v, float) else v) for k, v in row.items()}
    log(a.run, row["month"], f"{row['refs']:,} refs", f"rss_end {row['rss_end']:.2f}",
        f"batch peak {row['hwm_batch']:.2f}", f"maxrss {row['maxrss']:.2f}", f"{row['s']:.1f}s",
        f"gc {row.get('gc_found', '-')}")
    return row


def main():
    p = argparse.ArgumentParser()
    p.add_argument("work"); p.add_argument("run")
    p.add_argument("--months", type=int, default=6); p.add_argument("--d", type=int, default=1)
    p.add_argument("--gc", action="store_true"); p.add_argument("--del-session", action="store_true")
    p.add_argument("--reopen-every", type=int, default=0)
    p.add_argument("--cache-refs", type=int, default=None)
    p.add_argument("--split-hours", type=int, default=730)
    p.add_argument("--malloc-trim", action="store_true")
    p.add_argument("--fresh-process", action="store_true")
    p.add_argument("--tracemalloc", action="store_true")
    # The recommended form of H3: create and save the default config, then build through a handle
    # opened with gv.build_config_override(), so the zero cache is never persisted for readers.
    p.add_argument("--build-override", action="store_true")
    p.add_argument("--only-month", type=int, default=None, help=argparse.SUPPRESS)  # child of --fresh-process
    a = p.parse_args()
    work = Path(a.work); work.mkdir(parents=True, exist_ok=True)
    path = work / "repos" / a.run
    zarr.config.set({"async.concurrency": 128})
    if a.tracemalloc:
        tracemalloc.start()
    year = gv.hourly_axis(pd.Timestamp("2022-01-01"), pd.Timestamp("2022-12-31 23:00"))
    files, scans, grid, topo, src_attrs, gattrs = inputs(work)
    R = {"src_attrs": src_attrs}

    if a.only_month is not None:     # child: one month, then print its row
        row = one_month(open_repo(path, a), a.only_month, year, files, scans, a, R)
        print("ROW " + json.dumps(row), flush=True)
        return

    out = {"args": vars(a), "rss_after_inputs": round(rss(), 3), "months": []}
    log(a.run, f"inputs loaded, rss {rss():.2f} GB")
    repo = icechunk.Repository.create(icechunk.local_filesystem_storage(str(path)), config(a))
    if a.build_override:
        repo.save_config()
        repo = icechunk.Repository.open(icechunk.local_filesystem_storage(str(path)), gv.build_config_override())
        out["build_handle_num_chunk_refs"] = repo.config.caching.num_chunk_refs
        out["persisted_caching"] = str(icechunk.Repository.open(
            icechunk.local_filesystem_storage(str(path))).config.caching)
    skeleton = xr.merge([gv.loaded_variables(year, files, grid, topo, scans),
                         gv.virtual_variables(year, files.iloc[:0], {}, a.d, src_attrs)])
    skeleton.attrs = gattrs
    s = repo.writable_session("main"); skeleton.vz.to_icechunk(s.store, group=gv.GROUP, mode="w")
    s.commit("skeleton"); del skeleton, s
    out["rss_after_skeleton"] = round(rss(), 3); out["maxrss_after_skeleton"] = round(maxrss(), 3)
    log(a.run, f"skeleton done, rss {rss():.2f} GB, maxrss {maxrss():.2f} GB")

    for i in range(a.months):
        if a.fresh_process:
            cmd = [sys.executable, __file__, a.work, a.run, "--d", str(a.d),
                   "--split-hours", str(a.split_hours), "--only-month", str(i)]
            if a.cache_refs is not None:
                cmd += ["--cache-refs", str(a.cache_refs)]
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            row = json.loads([ln for ln in res.stdout.splitlines() if ln.startswith("ROW ")][-1][4:])
            print(res.stdout.strip().splitlines()[0], flush=True)
        else:
            if a.reopen_every and i and i % a.reopen_every == 0:
                del repo
                gc.collect()
                repo = open_repo(path, a)
            row = one_month(repo, i, year, files, scans, a, R)
        out["months"].append(row)
        (work / f"{a.run}.json").write_text(json.dumps(out, indent=1))
    out["manifest_mb"] = round(sum(f.stat().st_size for f in (path / "manifests").rglob("*") if f.is_file()) / 1e6, 1)
    out["n_manifests"] = sum(1 for f in (path / "manifests").rglob("*") if f.is_file())
    out["refs"] = sum(r["refs"] for r in out["months"])
    out["bytes_per_ref"] = round(out["manifest_mb"] * 1e6 / out["refs"], 2)
    (work / f"{a.run}.json").write_text(json.dumps(out, indent=1))
    log(a.run, f"done: manifests {out['manifest_mb']} MB in {out['n_manifests']} files, "
               f"{out['bytes_per_ref']} B/ref, final rss {rss():.2f} GB")


if __name__ == "__main__":
    main()
