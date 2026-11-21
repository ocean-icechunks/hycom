# HYCOM test stores — Icechunk

**[🌐 View data in browser](#gomb001-gulf-of-mexico-2022-test)** · **[💻 Data access (code)](#how-to-open-it)** · **[📦 Source code](https://github.com/ocean-icechunks/hycom)**

**Scratch copies for debugging**, not published datasets. Each one is a virtual
[Icechunk](https://icechunk.io) store: metadata and byte-range references only, with the arrays left in the
source NetCDF files. They may be rewritten or deleted at any time. The code is in
<https://github.com/ocean-icechunks/hycom>.

- [GOMb0.01 Gulf of Mexico, 2022 (test)](#gomb001-gulf-of-mexico-2022-test): the HYCOM-TSIS 1/100° hourly reanalysis
- [GOFS 3.1 reanalysis (test)](#gofs-31-reanalysis-test): 16 three-hourly steps of the global reanalysis

## GOMb0.01 Gulf of Mexico, 2022 (test)

One year, 2022 (8,760 hours, experiment 023), of the
[HYCOM-TSIS GOMb0.01 reanalysis](https://www.hycom.org/data/gomb0pt01/gom-reanalysis). The arrays stay in
the public bucket `s3://hycom-tsis-gom-reanalysis` (us-west-2). The variables are in the group **`hourly`**, and
the names follow the HYCOM files: `MT` (time), `Depth`, `Latitude`, `Longitude`. 3-D fields are
referenced one depth of one 385 × 526 tile per chunk. Built for ocean-icechunks/hycom#17. Its plan,
decisions and metadata repairs are in `claude/notes/plan-issue-17.md` there.

### View it in a browser

[water_temp at the surface](https://data.source.coop/ocean-icechunks/test-repo/hycom/viewer/index.html#icechunk+https://data.source.coop/ocean-icechunks/test-repo/hycom/hycom-tsis-gom-reanalysis/hourly::varname=water_temp::dimIndices_MT=0::dimIndices_Depth=0)

Change `varname=` to `salinity`, `ssh`, `u` or `v`. Both hosts send CORS headers, so no browser extension
should be needed.

### How to open it

Python >= 3.12, `pip install "icechunk>=2.3" "xarray>=2026.9" "zarr>=3.4"`. No credentials are needed.

```python
import icechunk, xarray as xr, zarr

zarr.config.set({"async.concurrency": 128})   # the default of 10 is slow against object storage

url = "https://data.source.coop/ocean-icechunks/test-repo/hycom/hycom-tsis-gom-reanalysis"
repo = icechunk.Repository.open(icechunk.http_storage(url))
# The data is read from the HYCOM bucket; each virtual prefix has to be authorized, even anonymously.
auth = {p: icechunk.credentials.HttpAccess for p in repo.config.virtual_chunk_containers}
store = repo.reopen(authorize_virtual_chunk_access=auth).readonly_session("main").store
ds = xr.open_zarr(store, group="hourly", consolidated=False, chunks=None)

sst = ds.water_temp.sel(MT="2022-07-01 12:00").isel(Depth=0).values               # one map, < 1 s
ts = ds.water_temp.isel(Depth=0).sel(Latitude=24.5, Longitude=-87, method="nearest").values  # a year at one point
```

Measured from us-west-2 (2026-11-19): open in about 1.4 s, a one-depth map in 0.3–0.6 s, a 40-depth profile in
0.6 s, a one-year point series in 16 s, and a one-year 200 × 200 box in 18–53 s (more when it straddles tiles).
`ssh` and the other 2-D fields are whole 12.9 MB maps, so a one-year point series of them takes minutes.
Outside AWS, all of these are slower.

- **Land and gaps read as NaN.** The store declares the fill value that is actually on land (2**100). The source
  files' `_FillValue` attribute is 3 ulps off it, so opening a source file directly leaves land at 1.27e30.
- `cell_methods_2d` / `cell_methods_3z` flag any hour that HYCOM rebuilt as a mean of its neighbours (none in 2022).
- A long read can now and then fail with an S3 `500 InternalError` ("Please try again"). Run it again.

## GOFS 3.1 reanalysis (test)

A **scratch copy for debugging**, not the published dataset. It holds 16 three-hourly time
steps (2004-12-27 12Z to 2004-12-29 09Z) of a virtual [Icechunk](https://icechunk.io) store:
metadata and byte-range references only, with the arrays left in the
[HYCOM bucket on AWS Open Data](https://registry.opendata.aws/hycom-gofs-3pt1-reanalysis/).
One step, 2004-12-28 12Z, has no source file and reads as missing. Written by
`hycom-smoke-test-sc.ipynb` in <https://github.com/ocean-icechunks/hycom>; it may be
rewritten or deleted at any time.

### View it in a browser

[water_temp at the surface](https://data.source.coop/ocean-icechunks/test-repo/hycom/viewer/index.html#icechunk+https://data.source.coop/ocean-icechunks/test-repo/hycom/hycom-gofs-3pt1-reanalysis::varname=water_temp::dimIndices_time=0::dimIndices_depth=0)

Change `varname=` to `salinity`, `surf_el`, `water_u` or `water_v` for the other fields.

Both hosts send CORS headers (the HYCOM bucket since November 2026), so no browser extension is
needed. Each frame is one whole 29 MB level fetched from us-west-2, so it is slow.

### How to open it

Python >= 3.12, `pip install "icechunk>=2.2" "xarray>=2026.7" "zarr>=3.4" "dask[array]"`.
No credentials are needed.

> **icechunk 1.x will not work.** `icechunk.http_storage` does not exist in icechunk 1.x
> (it arrived in 2.0), and `icechunk.credentials.HttpAccess` arrived in 2.1. Every icechunk
> 2.x release needs **Python 3.12 or newer**, so on an older Python `pip install icechunk`
> quietly installs 1.1.x, and the code below fails with
> `AttributeError: module 'icechunk' has no attribute 'http_storage'`. Check what you have:
> `python -c "import icechunk; print(icechunk.__version__)"`.

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
