"""Build a small virtual Icechunk store that SPLITS the source chunks, read it back, check values, time reads.

- ssh, 24 hourly files (2010 day 100), offsets from each file's own header, at three virtual chunkings:
  the native whole field (1,1537,2101), 53-row bands (1,53,2101), single rows (1,1,2101).
- water_temp, one 3z file, native (1,10,385,526) chunks split to one depth level (1,1,385,526).
Legal only because the data are uncompressed C-order float32: every band of whole rows inside a
source chunk is one contiguous byte range. Local temporary repository; reads come from data.hycom.org
at Zarr concurrency 4 (it answers bursts with 403, report F2). Writes out/split-timing.txt.
"""
import shutil, tempfile, time, numpy as np, xarray as xr, zarr, icechunk
from virtualizarr.manifests import ChunkManifest, ManifestArray
from common import PREFIX, chunks_of, h5open, meta

zarr.config.set({"async.concurrency": 4})
out = open("out/split-timing.txt", "w")
def p(*a):
    print(*a, flush=True); print(*a, file=out, flush=True)

NY, NX = 1537, 2101
hours = [f"2010/010_archv.2010_100_{h:02d}_2d.nc" for h in range(24)]
src, truth_pt, truth_box = [], [], []
for h in hours:
    with h5open(PREFIX + h) as f:
        d = f["ssh"]; (off, n), = chunks_of(d).values()
        assert d.compression is None and n == NY * NX * 4 and d.chunks == (1, NY, NX)
        src.append((PREFIX + h, off)); dtype, fill = d.dtype, float(d.fillvalue)
        truth_pt.append(d[0, 700, 1100]); truth_box.append(d[0, 600:800, 1000:1200])
        lat, lon = f["Latitude"][:], f["Longitude"][:]

def ssh(rows):
    nb, rb = NY // rows, rows * NX * 4
    P = np.array([[u] * nb for u, _ in src], dtype=np.dtypes.StringDType())[:, :, None]
    O = np.array([[o + k * rb for k in range(nb)] for _, o in src], "uint64")[:, :, None]
    man = ChunkManifest.from_arrays(paths=P, offsets=O, lengths=np.full(O.shape, rb, "uint64"))
    return xr.Variable(("time", "lat", "lon"), ManifestArray(metadata=meta((24, NY, NX), (1, rows, NX), ("time", "lat", "lon"), dtype, fill), chunkmanifest=man))

u3 = PREFIX + "2010/010_archv.2010_100_00_3z.nc"
with h5open(u3) as f:
    d = f["water_temp"]; C = chunks_of(d); cz, cy, cx = d.chunks[1:]; nz = d.shape[1]
    assert d.compression is None and all(n == cz * cy * cx * 4 for _, n in C.values())
    gy, gx = -(-NY // cy), -(-NX // cx); lvl = cy * cx * 4
    P = np.full((1, nz, gy, gx), u3, dtype=np.dtypes.StringDType()); O = np.zeros((1, nz, gy, gx), "uint64")
    for (_, z0, y0, x0), (off, _) in C.items():
        for k in range(cz):
            O[0, z0 + k, y0 // cy, x0 // cx] = off + k * lvl
    wt = xr.Variable(("time", "depth", "lat", "lon"), ManifestArray(
        metadata=meta((1, nz, NY, NX), (1, 1, cy, cx), ("time", "depth", "lat", "lon"), d.dtype, float(d.fillvalue)),
        chunkmanifest=ChunkManifest.from_arrays(paths=P, offsets=O, lengths=np.full(O.shape, lvl, "uint64"))))
    wt_box, wt_prof, depth = d[0, 25, 600:800, 1000:1200], d[0, :, 700, 1100], f["Depth"][:]

tmp = tempfile.mkdtemp(dir=".")
try:
    cfg = icechunk.RepositoryConfig.default()
    cfg.set_virtual_chunk_container(icechunk.VirtualChunkContainer(url_prefix=PREFIX, store=icechunk.http_store()))
    repo = icechunk.Repository.create(icechunk.local_filesystem_storage(tmp), cfg); repo.save_config()
    s = repo.writable_session("main")
    xr.Dataset({"ssh_full": ssh(NY), "ssh_band53": ssh(53), "ssh_row": ssh(1)}, coords={"lat": lat, "lon": lon}).vz.to_icechunk(s.store, group="2d")
    xr.Dataset({"water_temp": wt}, coords={"depth": depth, "lat": lat, "lon": lon}).vz.to_icechunk(s.store, group="3z")
    s.commit("split test")
    import os
    msize = sum(os.path.getsize(os.path.join(tmp, "manifests", x)) for x in os.listdir(os.path.join(tmp, "manifests")))
    nref = 24 * (1 + 29 + 1537) + nz * gy * gx
    p(f"manifests: {msize} bytes for {nref} references = {msize / nref:.1f} bytes/reference")

    repo = icechunk.Repository.open(icechunk.local_filesystem_storage(tmp), authorize_virtual_chunk_access={PREFIX: icechunk.credentials.HttpAccess})
    st = repo.readonly_session("main").store
    r2 = xr.open_zarr(st, group="2d", consolidated=False, chunks=None, mask_and_scale=False)
    r3 = xr.open_zarr(st, group="3z", consolidated=False, chunks=None, mask_and_scale=False)
    p("ssh, 24 hours, from data.hycom.org at concurrency 4. Values checked against h5py.")
    for v in ["ssh_row", "ssh_band53", "ssh_full"]:
        t = time.perf_counter(); pt = r2[v].isel(lat=700, lon=1100).values; a = time.perf_counter() - t
        t = time.perf_counter(); box = r2[v].isel(lat=slice(600, 800), lon=slice(1000, 1200)).values; b = time.perf_counter() - t
        t = time.perf_counter(); r2[v].isel(time=0).values; c = time.perf_counter() - t
        ok = np.array_equal(pt, truth_pt) and np.array_equal(box, np.stack(truth_box))
        p(f"  {v:11s} point x24h {a:6.2f}s | 200x200 box x24h {b:6.2f}s | full map 1h {c:6.2f}s | equal={ok}")
    t = time.perf_counter(); b3 = r3.water_temp.isel(time=0, depth=25, lat=slice(600, 800), lon=slice(1000, 1200)).values; a = time.perf_counter() - t
    t = time.perf_counter(); pr = r3.water_temp.isel(time=0, lat=700, lon=1100).values; b = time.perf_counter() - t
    p(f"water_temp split per level: 200x200 box at one depth {a:.2f}s equal={np.array_equal(b3, wt_box)} | "
      f"40-level profile {b:.2f}s equal={np.array_equal(pr, wt_prof)}")
finally:
    shutil.rmtree(tmp)
