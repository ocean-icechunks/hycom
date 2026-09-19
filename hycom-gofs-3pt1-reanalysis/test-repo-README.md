# HYCOM GOFS 3.1 reanalysis — test store

A **scratch copy for debugging**, not the published dataset. It holds 16 three-hourly time
steps (2004-12-27 12Z to 2004-12-29 09Z) of a virtual [Icechunk](https://icechunk.io) store:
metadata and byte-range references only, with the arrays left in the
[HYCOM bucket on AWS Open Data](https://registry.opendata.aws/hycom-gofs-3pt1-reanalysis/).
One step, 2004-12-28 12Z, has no source file and reads as missing. Written by
`hycom-smoke-test-sc.ipynb` in <https://github.com/ocean-icechunks/hycom>; it may be
rewritten or deleted at any time.

## Open it in the viewer

[water_temp at the surface](https://data.source.coop/ocean-icechunks/test-repo/hycom/viewer/index.html#icechunk+https://data.source.coop/ocean-icechunks/test-repo/hycom/hycom-gofs-3pt1-reanalysis::varname=water_temp::dimIndices_time=0::dimIndices_depth=0)

Change `varname=` to `salinity`, `surf_el`, `water_u` or `water_v` for the other fields.

**You need a CORS-disabling browser extension.** The HYCOM bucket sends no
`Access-Control-Allow-Origin` header, so an ordinary browser draws the axes and blocks the
data. Each frame is one whole 29 MB level fetched from us-west-2, so it is slow.

## Load it in Python

Python >= 3.12, `pip install "icechunk>=2.2" "xarray>=2026.7" "zarr>=3.4" "dask[array]"`.
No credentials are needed.

```python
import icechunk, xarray as xr, zarr

zarr.config.set({"async.concurrency": 64})   # the default of 10 is slow against object storage

url = "https://data.source.coop/ocean-icechunks/test-repo/hycom/hycom-gofs-3pt1-reanalysis"
repo = icechunk.Repository.open(icechunk.http_storage(url))
# The data is read from the HYCOM bucket; each virtual prefix has to be authorized, even anonymously.
auth = {p: icechunk.credentials.HttpAccess for p in repo.config.virtual_chunk_containers}
store = repo.reopen(authorize_virtual_chunk_access=auth).readonly_session("main").store
ds = xr.open_zarr(store, consolidated=False, chunks={})

sst = ds.water_temp.sel(time="2004-12-28 09:00").isel(depth=0).load()   # one 29 MB level
present = ds.isel(time=ds.tau.notnull().values)                        # drop the missing step
```
