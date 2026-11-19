"""Gap filling after the build, with a gate (ocean-icechunks/hycom#22). Tests 1-7 of the issue.

    python gapfill_test.py local  <out_dir>   # tests 1-5: local stores A (2022), B (2002), C (2005)
    python gapfill_test.py bulk   <out_dir>   # test 6: bulk fill of store A, Jan 8 - Feb 28 2022
    python gapfill_test.py remote build|fill|read   # test 7: s3://ocean-icechunks/test-repo/hycom/gapfill-test/

Each writes <out_dir>/results-<step>.json (remote: printed) and logs to stdout. Nothing is written
outside <out_dir> except by `remote build|fill`, which writes only under test-repo/hycom/gapfill-test/.
The stores, the deliberate gaps and what each check means are in claude/notes/gapfill-22.md.
"""
import datetime as dt
import gc
import json
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

T = time.perf_counter
D = 1                                             # Eli's choice for the test store (plan, step 4)
FILLBITS = gv.FILL.view("u4")
BOX = (slice(300, 500), slice(450, 650))          # 200 x 200 over four 3z tiles (the plan's box)
SRC = None
RETRIES = []                                      # every read retried, kept in the results


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def rss_gb():
    return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2**20, 2)


def src():
    global SRC
    SRC = SRC or gv.source_store()
    return SRC


def key_for(t, kind, exp):
    return f"{t.year}/{exp:03d}_archv.{t.year}_{t.day_of_year:03d}_{t.hour:02d}_{kind}.nc"


def files_for(times, exp, leave_out=()):
    """The layout A files for `times` (from the S3 listing), minus (time, kind) pairs left out."""
    listing = gv.list_keys(src(), sorted({t.year for t in times}))
    files, _ = gv.select_files(listing, times[0], times[-1])
    files = files[files.time.isin(times)]
    drop = files.apply(lambda r: (r.time, r.kind) in set(leave_out), axis=1)
    assert (files[~drop].experiment == exp).all()
    return files[~drop].reset_index(drop=True), files[drop].reset_index(drop=True)


# ------------------------------------------------------------------ building a test store

def build(storage, times, files, scans, refs_until=None, extra_rows=None, open_storage=None):
    """Skeleton over `times`, then one region write of `files` (as the build does). `extra_rows`
    are rows referenced on purpose at another hour (store B's simulated wrong reference)."""
    repo = icechunk.Repository.create(storage, gv.repository_config())
    repo.save_config()
    repo = icechunk.Repository.open(open_storage() if open_storage else storage, gv.build_config_override())
    k2 = files[files.kind == "2d"].key.iloc[0]
    k3 = files[files.kind == "3z"].key.iloc[0]
    grid = gv.read_grid(src(), k2, k3)
    topo = gv.read_topo(src(), grid)
    src_attrs = {**scans[k2]["attrs"], **scans[k3]["attrs"]}
    allf = pd.concat([files, extra_rows]) if extra_rows is not None else files
    sk = xr.merge([gv.loaded_variables(times, allf, grid, topo, scans),
                   gv.virtual_variables(times, files.iloc[:0], {}, D, src_attrs)])
    sk.attrs = gv.global_attrs(scans[k2]["global_attrs"])
    s = repo.writable_session("main")
    sk.vz.to_icechunk(s.store, group=gv.GROUP, mode="w")
    s.commit("skeleton")
    del sk
    gc.collect()
    b = refs_until or len(times)
    batch = gv.virtual_variables(times[:b], allf, scans, D, src_attrs)
    s = repo.writable_session("main")
    batch.vz.to_icechunk(s.store, group=gv.GROUP, region={"MT": slice(0, b)})
    sid = s.commit(f"references for {times[0]} to {times[b - 1]} (with deliberate gaps)")
    del batch
    gc.collect()
    return repo, sid


def reader(storage, snapshot=None):
    repo = icechunk.Repository.open(storage, authorize_virtual_chunk_access=gv.reader_authorization())
    s = repo.readonly_session(snapshot_id=snapshot) if snapshot else repo.readonly_session("main")
    return xr.open_zarr(s.store, group=gv.GROUP, consolidated=False, chunks=None, mask_and_scale=False,
                        decode_times=False)


def retry(f, tries=4):
    # S3 now and then answers one ranged GET with a 500, or a 503 when many GETs hit one object
    # (seen 2026-11-19 in this test); neither is a fault of the store
    for i in range(tries):
        try:
            return f()
        except Exception as e:  # noqa: BLE001
            msg = str(e)
            if i == tries - 1 or not any(s in msg for s in ("500", "503", "InternalError", "Service Unavailable")):
                raise
            RETRIES.append(f"{type(e).__name__}: {' '.join(msg.split()[-12:])}")
            log(f"retry {i + 1} after {RETRIES[-1]}")
            time.sleep(2 * (i + 1))


# ------------------------------------------------------------------ checks

def compare_hour(ds, i, key, kind):
    """Raw store values (mask_and_scale=False) against raw h5py, bit for bit, at hour i."""
    out = {}
    with h5py.File(BlockStoreReader(src(), "data/" + key)) as f:
        if kind == "2d":
            for v in gv.VARS_2D:
                out[f"{v} map"] = bool(np.array_equal(retry(lambda: ds[v].isel(MT=i).values).view("u4"),
                                                      f[v][0].view("u4")))
        else:
            out["water_temp map depth 0"] = bool(np.array_equal(
                retry(lambda: ds.water_temp.isel(MT=i, Depth=0).values).view("u4"), f["water_temp"][0, 0].view("u4")))
            out["salinity profile"] = bool(np.array_equal(
                retry(lambda: ds.salinity.isel(MT=i, Latitude=600, Longitude=1000).values).view("u4"),
                f["salinity"][0, :, 600, 1000].view("u4")))
            for v in gv.VARS_3Z:
                for z in (0, 17, 39):
                    out[f"{v} box depth {z}"] = bool(np.array_equal(
                        retry(lambda: ds[v].isel(MT=i, Depth=z, Latitude=BOX[0], Longitude=BOX[1]).values).view("u4"),
                        f[v][0, z, BOX[0], BOX[1]].view("u4")))
    return out


def is_gap(ds, i, kind):
    """A gap reads as the fill value everywhere (no reference)."""
    v = ds.ssh.isel(MT=i, Latitude=BOX[0], Longitude=BOX[1]) if kind == "2d" else \
        ds.water_temp.isel(MT=i, Depth=0, Latitude=BOX[0], Longitude=BOX[1])
    return bool((v.values.view("u4") == FILLBITS).all())


def point_series(ds):
    """Every hour at one sea point, both kinds: compared before and after a fill."""
    return {"ssh": retry(lambda: ds.ssh.isel(Latitude=600, Longitude=1000).values).view("u4"),
            "water_temp": retry(lambda: ds.water_temp.isel(Depth=0, Latitude=600, Longitude=1000).values).view("u4")}


def diff_summary(repo, a, b):
    d = repo.diff(from_snapshot_id=a, to_snapshot_id=b)
    chunks = {k.split("/")[-1]: sorted({c[0] for c in v}) for k, v in d.updated_chunks.items()}
    counts = {k.split("/")[-1]: len(v) for k, v in d.updated_chunks.items()}
    return {"hours_by_array": chunks, "chunks_by_array": counts,
            "updated_arrays_metadata": sorted(x.split("/")[-1] for x in d.updated_arrays),
            "updated_groups": sorted(d.updated_groups), "new_arrays": sorted(d.new_arrays)}


def summarise_gate(r):
    return {k: (str(v) if isinstance(v, (pd.Timestamp, dt.datetime)) else v)
            for k, v in r.items() if k not in ("scan",)}


# ------------------------------------------------------------------ tests 1-5 (local)

def store_a(out, R):
    """Test 1 and 2: 2022 axis Jan 1 - Feb 28, references for Jan 1-7 only, with deliberate gaps."""
    times = gv.hourly_axis(pd.Timestamp("2022-01-01"), pd.Timestamp("2022-02-28 23:00"))
    week = times[:168]
    gaps = {"3z only": [(pd.Timestamp("2022-01-02 06:00"), "3z")],
            "2d only": [(pd.Timestamp("2022-01-03 12:00"), "2d")],
            "both": [(pd.Timestamp("2022-01-04 18:00"), "2d"), (pd.Timestamp("2022-01-04 18:00"), "3z")],
            "run of 6 (3z)": [(pd.Timestamp(f"2022-01-05 {h:02d}:00"), "3z") for h in range(6)]}
    files, left = files_for(week, 23, [p for v in gaps.values() for p in v])
    t = T()
    scans, rep = gv.scan_files(files, "h5py", 16)
    assert rep.error.isna().all(), rep.dropna(subset=["error"])
    R["A_scan"] = {"files": len(files), "s": round(T() - t, 1)}
    storage = icechunk.local_filesystem_storage(str(out / "A"))
    t = T()
    repo, built = build(storage, times, files, scans, refs_until=168)
    R["A_build"] = {"s": round(T() - t, 1), "snapshot": built, "left_out": left.key.tolist()}
    log("store A built", R["A_build"]["s"], "s")

    before = reader(storage, built)
    ps_before = point_series(before)
    R["A_gaps_before"] = {name: {f"{tt} {k}": is_gap(before, times.get_loc(tt), k) for tt, k in pairs}
                          for name, pairs in gaps.items()}
    R["A_store_gaps_before"] = gv.gaps_markdown(gv.store_gaps(repo.readonly_session("main")))

    # Test 3 / 4b run against this store before the fills; see gate_tests.
    gate_tests(repo, R)

    # Test 2: fill each shape as its own commit
    snaps = [built]
    R["A_fills"] = []
    for name, pairs in gaps.items():
        keys = [key_for(tt, k, 23) for tt, k in pairs]
        s = repo.readonly_session("main")
        t = T()
        res = gv.check_fill_candidates(keys, s, workers=8)
        gate_s = round(T() - t, 1)
        assert all(r["ok"] for r in res), [r["reasons"] for r in res]
        repo_w = icechunk.Repository.open(storage, gv.build_config_override())
        f = gv.fill_hours(repo_w, res, reason="new hour", log=log)
        snaps.append(f[0]["snapshot"])
        R["A_fills"].append({"gap": name, "gate_s": gate_s, "fill": f,
                             "lon_md5": sorted({r["scan"]["coords_md5"]["Longitude"] for r in res}),
                             "diff": diff_summary(repo_w, snaps[-2], snaps[-1])})
    after = reader(storage)                       # a fresh reader on main
    R["A_values_after"] = {f"{tt} {k}": compare_hour(after, times.get_loc(tt), key_for(tt, k, 23), k)
                           for pairs in gaps.values() for tt, k in pairs}
    R["A_values_all_identical"] = all(all(v.values()) for v in R["A_values_after"].values())
    filled = {k: {times.get_loc(tt) for p in gaps.values() for tt, kk in p if kk == k} for k in ("2d", "3z")}
    ps_after = point_series(after)
    R["A_other_hours_unchanged"] = {}
    for v, k in (("ssh", "2d"), ("water_temp", "3z")):
        changed = set(np.flatnonzero(ps_before[v] != ps_after[v]).tolist())
        R["A_other_hours_unchanged"][v] = {"changed_hours": sorted(changed), "expected": sorted(filled[k]),
                                           "ok": changed == filled[k]}
    exp = after.experiment.values[:168]
    R["A_flags_after"] = {"experiment_first_week": {int(a): int(b) for a, b in zip(*np.unique(exp, return_counts=True))},
                          "cm2d_first_week": {int(a): int(b) for a, b in zip(*np.unique(after.cell_methods_2d.values[:168], return_counts=True))},
                          "cm3z_first_week": {int(a): int(b) for a, b in zip(*np.unique(after.cell_methods_3z.values[:168], return_counts=True))}}
    old = reader(storage, built)                  # the earlier snapshot, by id
    R["A_old_snapshot_still_gaps"] = {f"{tt} {k}": is_gap(old, times.get_loc(tt), k)
                                      for pairs in gaps.values() for tt, k in pairs}
    R["A_old_snapshot_flags"] = {
        "cm3z at 2022-01-05 00-05Z": old.cell_methods_3z.values[96:102].tolist(),
        "experiment at 2022-01-04 18Z": int(old.experiment.values[90])}
    R["A_store_gaps_after"] = gv.gaps_markdown(gv.store_gaps(repo.readonly_session("main")))
    R["A_commits"] = [(a.id, a.message.splitlines()[0]) for a in repo.ancestry(branch="main")]
    meta = next(iter(repo.ancestry(branch="main"))).metadata
    R["A_last_commit_metadata"] = meta
    (out / "store-A.json").write_text(json.dumps({"snapshots": snaps}, indent=1))


def gate_tests(repo, R):
    """Test 3 (rejections) and the 2022 half of test 4 (Longitude variant)."""
    s = repo.readonly_session("main")
    real = {
        "layout B chunking (2004_153_19_2d)": "2004/010_archv.2004_153_19_2d.nc",
        "empty 3z (2006_177_18_3z)": "2006/010_archv.2006_177_18_3z.nc",
        "hour not on the axis": "2022/023_archv.2022_100_00_3z.nc",
        "hour not a gap, no replacement flag": "2022/023_archv.2022_001_00_3z.nc",
        "layout B experiment 027": "2024/027_archv.2024_100_00_3z.nc",
        "_COPY name": "2012/010_archv.2012_138_00_3z.nc_COPY",
        "_CORRUPTED name (HYCOM's, not on S3)": "2002/010_archv.2002_046_12_3z.nc_CORRUPTED",
    }
    t = T()
    res = gv.check_fill_candidates(list(real.values()), s, workers=8)
    R["gate_reject_real_s"] = round(T() - t, 1)
    R["gate_reject_real"] = {n: {"ok": r["ok"], "reasons": r["reasons"]} for n, r in zip(real, res)}
    ref = gv.gate_reference(s)
    r = gv.check_fill_candidate("2022/023_archv.2022_001_00_3z.nc", ref, replacement=False,
                                reference_exists=gv.has_reference(s, "3z", 0))
    # Replacement flag on an hour that is a gap
    r2 = gv.check_fill_candidate("2022/023_archv.2022_002_06_3z.nc", ref, replacement=True,
                                 reference_exists=gv.has_reference(s, "3z", 30))
    R["gate_reject_flags"] = {"not a gap (single-file path)": r["reasons"],
                              "replacement flag on a gap": r2["reasons"]}
    # Simulated: a good candidate (the 3z-only gap) with one thing changed in its scan or the store
    key, i = "2022/023_archv.2022_002_06_3z.nc", 30
    good = gv.check_fill_candidate(key, ref, reference_exists=gv.has_reference(s, "3z", i))
    R["gate_accept_2022_3z"] = {"ok": good["ok"], "reasons": good["reasons"],
                                "lon_md5_file": good["scan"]["coords_md5"]["Longitude"],
                                "lon_md5_store": ref["coords"]["Longitude"], "fingerprint": good["fingerprint"]}
    import copy

    def tamper(fn_scan=None, fn_ref=None):
        sc, rf = copy.deepcopy(good["scan"]), copy.deepcopy(ref)
        if fn_scan:
            fn_scan(sc)
        if fn_ref:
            fn_ref(rf)
        return gv.check_fill_candidate(key, rf, scan=sc, size=good["size"], modified=good["modified"])["reasons"]

    def cm(sc):
        for a in sc["attrs"].values():
            a["cell_methods"] = "MT: sum"
        sc["cell_methods"] = "MT: sum"

    def exp26(rf):
        rf["experiment"][:] = np.where(rf["experiment"] != 0, 26, 0)

    def flipmask(rf):
        rf["mask"] = 1 - rf["mask"]
    R["gate_reject_simulated"] = {
        "unknown cell_methods": tamper(cm),
        "unknown Longitude": tamper(lambda sc: sc["coords_md5"].update(Longitude="deadbeef")),
        "unknown Latitude": tamper(lambda sc: sc["coords_md5"].update(Latitude="deadbeef")),
        "unknown Depth": tamper(lambda sc: sc["coords_md5"].update(Depth="deadbeef")),
        "changed variable attribute (units)": tamper(lambda sc: sc["attrs"]["u"].update(units="cm/s")),
        "changed global title": tamper(lambda sc: sc["global_attrs"].update(title="HYCOM v2")),
        "MT one hour off": tamper(lambda sc: sc.update(MT=sc["MT"] + 1 / 24)),
        "experiment differs from neighbours": tamper(fn_ref=exp26),
        "land check against an inverted mask": tamper(fn_ref=flipmask),
    }


def store_b(out, R):
    """Test 5: replacement. 2002 day 046 10-17Z. The 12Z 3z hour is built referencing the 13Z file
    (a simulated wrong reference); 16Z 3z is a gap (as when these files were held back)."""
    times = gv.hourly_axis(pd.Timestamp("2002-02-15 10:00"), pd.Timestamp("2002-02-15 17:00"))
    t12, t13, t16 = (pd.Timestamp(f"2002-02-15 {h}:00") for h in (12, 13, 16))
    files, left = files_for(times, 10, [(t12, "3z"), (t16, "3z")])
    scans, rep = gv.scan_files(files, "h5py", 8)
    assert rep.error.isna().all()
    k13 = key_for(t13, "3z", 10)
    wrong = pd.DataFrame([dict(key=k13, size=0, modified=None, time=t12, kind="3z", experiment=10)])
    storage = icechunk.local_filesystem_storage(str(out / "B"))
    repo, built = build(storage, times, files, scans, extra_rows=wrong)
    i12, i16 = times.get_loc(t12), times.get_loc(t16)
    ds = reader(storage)
    R["B_before"] = {"12Z reads the 13Z file": compare_hour(ds, i12, k13, "3z"), "16Z is a gap": is_gap(ds, i16, "3z")}
    k12, k16 = key_for(t12, "3z", 10), key_for(t16, "3z", 10)
    # 5a: a different key for an already-referenced hour
    s = repo.readonly_session("main")
    no_flag = gv.check_fill_candidates([k12], s, workers=2)[0]
    res = gv.check_fill_candidates([k12], s, replacement=True, workers=2)
    assert res[0]["ok"], res[0]["reasons"]
    rw = icechunk.Repository.open(storage, gv.build_config_override())
    f = gv.fill_hours(rw, res, reason="replacement", log=log)
    ds = reader(storage)
    R["B_5a"] = {"without replacement flag": no_flag["reasons"], "fill": f,
                 "diff": diff_summary(rw, built, f[0]["snapshot"]),
                 "12Z now equals the 12Z file": compare_hour(ds, i12, k12, "3z"),
                 "12Z still equals the 13Z file at the box (should be False)": bool(np.array_equal(
                     ds.water_temp.isel(MT=i12, Depth=0, Latitude=BOX[0], Longitude=BOX[1]).values,
                     ds.water_temp.isel(MT=i12 + 1, Depth=0, Latitude=BOX[0], Longitude=BOX[1]).values)),
                 "old snapshot 12Z still the 13Z file": compare_hour(reader(storage, built), i12, k13, "3z")["water_temp map depth 0"]}
    # 5b: the checksum pin. Fill 16Z pinned BEFORE the object's Last-Modified (as if HYCOM had
    # rewritten it after the fill), see reads fail, then refill it as a replacement with the gate's pin.
    s = repo.readonly_session("main")
    res = gv.check_fill_candidates([k16], s, workers=2)
    assert res[0]["ok"], res[0]["reasons"]
    stale = dt.datetime(2026, 11, 10, tzinfo=dt.timezone.utc)
    f1 = gv.fill_hours(rw, res, reason="new hour", pin=stale, log=log)
    ds = reader(storage)
    try:
        ds.water_temp.isel(MT=i16, Depth=0, Latitude=600, Longitude=1000).values
        stale_read = "read OK (pin NOT enforced)"
    except Exception as e:  # noqa: BLE001
        stale_read = f"{type(e).__name__}: {str(e).splitlines()[0][:200]}"
    s = repo.readonly_session("main")
    res2 = gv.check_fill_candidates([k16], s, replacement=True, workers=2)
    f2 = gv.fill_hours(rw, res2, reason="replacement", log=log)
    ds = reader(storage)
    R["B_5b"] = {"object_last_modified": str(res[0]["modified"]), "stale pin": stale.isoformat(),
                 "read with stale pin": stale_read, "fill_stale": f1, "refill": f2,
                 "16Z after refill equals h5py": compare_hour(ds, i16, k16, "3z"),
                 "diff refill": diff_summary(rw, f1[0]["snapshot"], f2[0]["snapshot"])}
    R["B_flags"] = {"cell_methods_3z": ds.cell_methods_3z.values.tolist(), "experiment": ds.experiment.values.tolist()}


def store_c(out, R):
    """Test 4: the ncra stand-in 2005-03-20 04Z 3z is accepted and flagged MT_mean."""
    times = gv.hourly_axis(pd.Timestamp("2005-03-20 00:00"), pd.Timestamp("2005-03-20 07:00"))
    t4 = pd.Timestamp("2005-03-20 04:00")
    files, _ = files_for(times, 10, [(t4, "3z")])
    scans, rep = gv.scan_files(files, "h5py", 8)
    assert rep.error.isna().all()
    storage = icechunk.local_filesystem_storage(str(out / "C"))
    repo, built = build(storage, times, files, scans)
    res = gv.check_fill_candidates(["2005/010_archv.2005_079_04_3z.nc"], repo.readonly_session("main"), workers=2)
    rw = icechunk.Repository.open(storage, gv.build_config_override())
    R["C_gate"] = {"ok": res[0]["ok"], "reasons": res[0]["reasons"], "cell_methods": res[0]["cell_methods"],
                   "fingerprint": res[0]["fingerprint"], "full_fingerprint": gv.fingerprint(res[0]["scan"])}
    f = gv.fill_hours(rw, res, reason="new hour", log=log)
    ds = reader(storage)
    R["C_after"] = {"fill": f, "cell_methods_3z": ds.cell_methods_3z.values.tolist(),
                    "values": compare_hour(ds, times.get_loc(t4), "2005/010_archv.2005_079_04_3z.nc", "3z"),
                    "commit_metadata": next(iter(repo.ancestry(branch="main"))).metadata,
                    "attrs_water_temp_unchanged": {k: ds.water_temp.attrs.get(k) for k in ("cell_methods", "ancillary_variables")}}


def local(out):
    out.mkdir(parents=True, exist_ok=True)
    zarr.config.set({"async.concurrency": 128})
    R = {}
    for name, fn in (("C", store_c), ("B", store_b), ("A", store_a)):
        t = T()
        fn(out, R)
        R[f"{name}_total_s"] = round(T() - t, 1)
        log(f"store {name} done in {R[f'{name}_total_s']} s, rss {rss_gb()} GB")
        (out / "results-local.json").write_text(json.dumps(R, indent=1, default=str))
    R["peak_rss_gb"], R["read_retries"] = rss_gb(), RETRIES
    (out / "results-local.json").write_text(json.dumps(R, indent=1, default=str))


# ------------------------------------------------------------------ test 6 (bulk)

def bulk(out):
    zarr.config.set({"async.concurrency": 128})
    R = {}
    storage = icechunk.local_filesystem_storage(str(out / "A"))
    times = gv.hourly_axis(pd.Timestamp("2022-01-01"), pd.Timestamp("2022-02-28 23:00"))
    files, _ = files_for(times[168:], 23)
    repo = icechunk.Repository.open(storage, gv.build_config_override())
    before = repo.lookup_branch("main")
    t = T()
    res = gv.check_fill_candidates(files.key.tolist(), repo.readonly_session("main"), workers=16)
    R["gate"] = {"files": len(res), "s": round(T() - t, 1), "rejected": [(r["key"], r["reasons"]) for r in res if not r["ok"]],
                 "rss_gb": rss_gb(),
                 "children_peak_rss_gb": round(resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / 2**20, 2)}
    log("gate", R["gate"]["s"], "s")
    t = T()
    R["fill"] = gv.fill_hours(repo, [r for r in res if r["ok"]], reason="bulk", log=log)
    R["fill_s"] = round(T() - t, 1)
    R["peak_rss_gb"], R["read_retries"] = rss_gb(), RETRIES
    d = diff_summary(repo, before, repo.lookup_branch("main"))
    R["diff_chunks"] = d["chunks_by_array"]
    R["diff_hours_range"] = {k: [v[0], v[-1], len(v)] for k, v in d["hours_by_array"].items()}
    ds = reader(storage)
    R["values"] = {f"{tt} {k}": compare_hour(ds, times.get_loc(tt), key_for(tt, k, 23), k)
                   for tt, k in ((pd.Timestamp("2022-02-14 12:00"), "3z"), (pd.Timestamp("2022-01-20 03:00"), "2d"))}
    R["flags"] = {v: {int(a): int(b) for a, b in zip(*np.unique(ds[v].values, return_counts=True))}
                  for v in ("experiment", "cell_methods_2d", "cell_methods_3z")}
    R["store_gaps"] = gv.gaps_markdown(gv.store_gaps(repo.readonly_session("main")))
    R["manifests_mb"] = round(sum(f.stat().st_size for f in (out / "A" / "manifests").rglob("*") if f.is_file()) / 1e6, 1)
    (out / "results-bulk.json").write_text(json.dumps(R, indent=1, default=str))
    log(json.dumps({k: R[k] for k in ("fill_s", "peak_rss_gb")}))


# ------------------------------------------------------------------ test 7 (Source Cooperative)

BUCKET, PREFIX = "ocean-icechunks", "test-repo/hycom/gapfill-test/store"
PUBLIC = f"https://data.source.coop/{BUCKET}/{PREFIX}"
R_TIMES = gv.hourly_axis(pd.Timestamp("2022-01-01"), pd.Timestamp("2022-01-03 23:00"))
R_GAPS = {"3z only": [(pd.Timestamp("2022-01-02 06:00"), "3z")],
          "2d only": [(pd.Timestamp("2022-01-02 12:00"), "2d")],
          "both": [(pd.Timestamp("2022-01-02 18:00"), "2d"), (pd.Timestamp("2022-01-02 18:00"), "3z")],
          "run of 6 (3z)": [(pd.Timestamp(f"2022-01-03 {h:02d}:00"), "3z") for h in range(6)]}


def remote_repo(config):
    from icechunk_utils import open_source_icechunk_repo
    repo, storage, _c, _left = open_source_icechunk_repo(BUCKET, PREFIX, config=config, min_minutes_left=30, verbose=False)
    assert repo is not None, "Source Cooperative token too close to expiry; Eli needs to run source-coop login"
    return repo


def remote(step):
    zarr.config.set({"async.concurrency": 128})
    R = {"url": PUBLIC}
    if step == "build":
        files, left = files_for(R_TIMES, 23, [p for v in R_GAPS.values() for p in v])
        scans, rep = gv.scan_files(files, "h5py", 16)
        assert rep.error.isna().all()
        repo = remote_repo(gv.repository_config())
        repo.save_config()
        t = T()
        # build() re-opens through Repository.open(storage, override); give it fresh remote storage
        from icechunk_utils import open_source_icechunk_repo
        _r, storage, _c, _l = open_source_icechunk_repo(BUCKET, PREFIX, min_minutes_left=30, verbose=False)
        repo = icechunk.Repository.open(storage, gv.build_config_override())
        k2 = files[files.kind == "2d"].key.iloc[0]
        k3 = files[files.kind == "3z"].key.iloc[0]
        grid = gv.read_grid(src(), k2, k3)
        topo = gv.read_topo(src(), grid)
        src_attrs = {**scans[k2]["attrs"], **scans[k3]["attrs"]}
        sk = xr.merge([gv.loaded_variables(R_TIMES, files, grid, topo, scans),
                       gv.virtual_variables(R_TIMES, files.iloc[:0], {}, D, src_attrs)])
        sk.attrs = gv.global_attrs(scans[k2]["global_attrs"])
        s = repo.writable_session("main")
        sk.vz.to_icechunk(s.store, group=gv.GROUP, mode="w")
        s.commit("skeleton (gap-fill test, #22)")
        batch = gv.virtual_variables(R_TIMES, files, scans, D, src_attrs)
        s = repo.writable_session("main")
        batch.vz.to_icechunk(s.store, group=gv.GROUP, region={"MT": slice(0, len(R_TIMES))})
        R["built_snapshot"] = s.commit("references for 2022-01-01 to 2022-01-03, with 10 hours left out on purpose (#22)")
        R["build_s"] = round(T() - t, 1)
        R["left_out"] = left.key.tolist()
    elif step == "fill":
        R["fills"] = []
        for name, pairs in R_GAPS.items():
            repo = remote_repo(gv.build_config_override())
            keys = [key_for(tt, k, 23) for tt, k in pairs]
            t = T()
            res = gv.check_fill_candidates(keys, repo.readonly_session("main"), workers=8)
            assert all(r["ok"] for r in res), [r["reasons"] for r in res]
            g = round(T() - t, 1)
            f = gv.fill_hours(repo, res, reason="new hour", log=log)
            R["fills"].append({"gap": name, "gate_s": g, "fill": f,
                               "gate": [summarise_gate(r) for r in res]})
        Path("remote-fill-log.json").write_text(json.dumps(R["fills"], indent=1, default=str))
    else:   # read, anonymously, as a reader would
        t = T()
        repo = icechunk.Repository.open(icechunk.http_storage(PUBLIC))
        auth = {p: icechunk.credentials.HttpAccess for p in repo.config.virtual_chunk_containers}
        repo = repo.reopen(authorize_virtual_chunk_access=auth)
        R["open_s"] = round(T() - t, 2)
        anc = list(repo.ancestry(branch="main"))
        R["commits"] = [(a.id, a.message.splitlines()[0], a.metadata.get("fill_reason")) for a in anc]
        built = next(a.id for a in anc if a.message.startswith("references for"))
        ds = xr.open_zarr(repo.readonly_session("main").store, group=gv.GROUP, consolidated=False,
                          chunks=None, mask_and_scale=False, decode_times=False)
        old = xr.open_zarr(repo.readonly_session(snapshot_id=built).store, group=gv.GROUP, consolidated=False,
                           chunks=None, mask_and_scale=False, decode_times=False)
        R["values"], R["old_snapshot_gap"] = {}, {}
        for pairs in R_GAPS.values():
            for tt, k in pairs:
                i = R_TIMES.get_loc(tt)
                R["values"][f"{tt} {k}"] = all(compare_hour(ds, i, key_for(tt, k, 23), k).values())
                R["old_snapshot_gap"][f"{tt} {k}"] = is_gap(old, i, k)
        R["flags_main"] = {v: {int(a): int(b) for a, b in zip(*np.unique(ds[v].values, return_counts=True))}
                           for v in ("experiment", "cell_methods_2d", "cell_methods_3z")}
        R["flags_old"] = {v: {int(a): int(b) for a, b in zip(*np.unique(old[v].values, return_counts=True))}
                          for v in ("experiment", "cell_methods_2d", "cell_methods_3z")}
        R["store_gaps_main"] = gv.gaps_markdown(gv.store_gaps(repo.readonly_session("main")))
        R["store_gaps_old"] = gv.gaps_markdown(gv.store_gaps(repo.readonly_session(snapshot_id=built)))
        # masked, as a normal reader sees it
        m = xr.open_zarr(repo.readonly_session("main").store, group=gv.GROUP, consolidated=False, chunks=None)
        R["masked_ssh_nan_at_land"] = int(np.isnan(m.ssh.isel(MT=36).values).sum())
    R["rss_peak_gb"] = rss_gb()
    print(json.dumps(R, indent=1, default=str))


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "local":
        local(Path(sys.argv[2]))
    elif cmd == "bulk":
        bulk(Path(sys.argv[2]))
    else:
        remote(sys.argv[2])
