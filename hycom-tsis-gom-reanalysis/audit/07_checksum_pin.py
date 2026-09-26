"""Does Icechunk's per-reference checksum protect a store from HYCOM rewriting a file?
Writes one hour of ssh twice: pinned to a date BEFORE the file's Last-Modified (reads must fail) and
AFTER it (reads must succeed). Writes out/checksum-pin.txt."""
import datetime as dt, shutil, tempfile, numpy as np, xarray as xr, zarr, icechunk
from virtualizarr.manifests import ChunkManifest, ManifestArray
from common import PREFIX, chunks_of, h5open, meta

zarr.config.set({"async.concurrency": 4})
url = PREFIX + "2010/010_archv.2010_100_00_2d.nc"   # Last-Modified: Fri, 10 Jan 2025 03:35:39 GMT
with h5open(url) as f:
    d = f["ssh"]; (off, _), = chunks_of(d).values(); truth = d[0, 700, 1000:1100]; dtype, fill = d.dtype, float(d.fillvalue)
rb = 53 * 2101 * 4
man = ChunkManifest.from_arrays(paths=np.full((1, 29, 1), url, dtype=np.dtypes.StringDType()),
                                offsets=(off + np.arange(29, dtype="uint64") * rb).reshape(1, 29, 1), lengths=np.full((1, 29, 1), rb, "uint64"))
ds = xr.Dataset({"ssh": xr.Variable(("time", "lat", "lon"), ManifestArray(metadata=meta((1, 1537, 2101), (1, 53, 2101), ("time", "lat", "lon"), dtype, fill), chunkmanifest=man))})
with open("out/checksum-pin.txt", "w") as out:
    for label, when in [("pinned before Last-Modified", dt.datetime(2024, 6, 1, tzinfo=dt.timezone.utc)),
                        ("pinned after Last-Modified ", dt.datetime(2026, 9, 25, tzinfo=dt.timezone.utc))]:
        tmp = tempfile.mkdtemp(dir=".")
        try:
            cfg = icechunk.RepositoryConfig.default()
            cfg.set_virtual_chunk_container(icechunk.VirtualChunkContainer(url_prefix=PREFIX, store=icechunk.http_store()))
            repo = icechunk.Repository.create(icechunk.local_filesystem_storage(tmp), cfg); repo.save_config()
            s = repo.writable_session("main"); ds.vz.to_icechunk(s.store, last_updated_at=when); s.commit("pin")
            repo = icechunk.Repository.open(icechunk.local_filesystem_storage(tmp), authorize_virtual_chunk_access={PREFIX: icechunk.credentials.HttpAccess})
            try:
                v = xr.open_zarr(repo.readonly_session("main").store, consolidated=False, chunks=None, mask_and_scale=False).ssh.isel(time=0, lat=700, lon=slice(1000, 1100)).values
                line = f"{label} -> read OK, equal to h5py: {np.array_equal(v, truth)}"
            except Exception as e:
                line = f"{label} -> {type(e).__name__}: {str(e).splitlines()[0][:160]}"
        finally:
            shutil.rmtree(tmp)
        print(line); print(line, file=out)
