"""Can 2d and 3z variables, with different chunk shapes, share ONE group, one lat/lon and one time axis?
Two hours; ssh as 53-row bands, water_temp as one depth of one tile. Checks the two files' coordinates
are identical, writes one group, reopens it read-only, compares with h5py. Writes out/one-group.txt."""
import shutil, tempfile, numpy as np, xarray as xr, zarr, icechunk
from virtualizarr.manifests import ChunkManifest, ManifestArray
from common import PREFIX, chunks_of, h5open, meta

zarr.config.set({"async.concurrency": 4})
NY, NX, NZ = 1537, 2101, 40
hours = ["2010/010_archv.2010_100_00", "2010/010_archv.2010_100_01"]
S = np.dtypes.StringDType()
sshP, sshO, wtP, wtO, truth = [], [], [], [], []
for h in hours:
    with h5open(PREFIX + h + "_2d.nc") as f2, h5open(PREFIX + h + "_3z.nc") as f3:
        for c in ["Latitude", "Longitude"]:
            assert np.array_equal(f2[c][:], f3[c][:]), c
        # 3z MT is stored at reduced precision (report F11); it agrees with 2d only to the hour
        assert np.array_equal(np.round(f2["MT"][:] * 24), np.round(f3["MT"][:] * 24)), (f2["MT"][:], f3["MT"][:])
        d = f2["ssh"]; (off, _), = chunks_of(d).values(); rb = 53 * NX * 4
        sshP.append([PREFIX + h + "_2d.nc"] * 29); sshO.append([off + k * rb for k in range(29)])
        w = f3["water_temp"]; C = chunks_of(w); cz, cy, cx = w.chunks[1:]; lvl = cy * cx * 4
        O = np.zeros((NZ, 4, 4), "uint64")
        for (_, z0, y0, x0), (o, _) in C.items():
            for k in range(cz): O[z0 + k, y0 // cy, x0 // cx] = o + k * lvl
        wtP.append(np.full((NZ, 4, 4), PREFIX + h + "_3z.nc", dtype=S)); wtO.append(O)
        truth.append((d[0, 600:800, 1000:1200], w[0, 25, 600:800, 1000:1200]))
        lat, lon, depth, mt = f2["Latitude"][:], f2["Longitude"][:], f3["Depth"][:], None
        dt2, dt3, fill = d.dtype, w.dtype, float(d.fillvalue)
sshO = np.array(sshO, "uint64")[:, :, None]
ssh = ManifestArray(metadata=meta((2, NY, NX), (1, 53, NX), ("time", "lat", "lon"), dt2, fill),
                    chunkmanifest=ChunkManifest.from_arrays(paths=np.array(sshP, dtype=S)[:, :, None], offsets=sshO, lengths=np.full(sshO.shape, rb, "uint64")))
wtO = np.stack(wtO)
wt = ManifestArray(metadata=meta((2, NZ, NY, NX), (1, 1, cy, cx), ("time", "depth", "lat", "lon"), dt3, fill),
                   chunkmanifest=ChunkManifest.from_arrays(paths=np.stack(wtP), offsets=wtO, lengths=np.full(wtO.shape, lvl, "uint64")))
ds = xr.Dataset({"ssh": (("time", "lat", "lon"), ssh), "water_temp": (("time", "depth", "lat", "lon"), wt)},
                coords={"time": [0, 1], "depth": depth, "lat": lat, "lon": lon})
tmp = tempfile.mkdtemp(dir=".")
try:
    cfg = icechunk.RepositoryConfig.default()
    cfg.set_virtual_chunk_container(icechunk.VirtualChunkContainer(url_prefix=PREFIX, store=icechunk.http_store()))
    repo = icechunk.Repository.create(icechunk.local_filesystem_storage(tmp), cfg); repo.save_config()
    s = repo.writable_session("main"); ds.vz.to_icechunk(s.store); s.commit("one group")
    repo = icechunk.Repository.open(icechunk.local_filesystem_storage(tmp), authorize_virtual_chunk_access={PREFIX: icechunk.credentials.HttpAccess})
    r = xr.open_zarr(repo.readonly_session("main").store, consolidated=False, chunks=None, mask_and_scale=False)
    with open("out/one-group.txt", "w") as out:
        for line in [f"variables in one group: {list(r.data_vars)}; dims {dict(r.sizes)}",
                     f"ssh chunks {r.ssh.encoding['chunks']}, water_temp chunks {r.water_temp.encoding['chunks']}",
                     "2d and 3z Latitude and Longitude identical, MT equal to the hour, in both hours: True"]:
            print(line); print(line, file=out)
        for i in range(2):
            a = r.ssh.isel(time=i, lat=slice(600, 800), lon=slice(1000, 1200)).values
            b = r.water_temp.isel(time=i, depth=25, lat=slice(600, 800), lon=slice(1000, 1200)).values
            line = f"hour {i}: ssh equal {np.array_equal(a, truth[i][0])}, water_temp equal {np.array_equal(b, truth[i][1])}"
            print(line); print(line, file=out)
finally:
    shutil.rmtree(tmp)
