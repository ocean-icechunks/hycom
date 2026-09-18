# Production build, 2026-09-18

Store: `https://data.source.coop/ocean-icechunks/hycom/hycom-gofs-3pt1-reanalysis`, tag `v1`
= `VBMJX9KNE9BN8GTG5100` (also `main`). 24 snapshots: init, skeleton, one per year 1994-2015.
10,451,265 references from 63,341 files on a 64,272-step axis. Built by
`hycom-icechunk-sc.ipynb` with `RUN_WRITE = True`; icechunk 2.2.2, virtualizarr 2.7.3,
zarr 3.4.0, xarray 2026.7.0, Python 3.12.12, hub in us-west-2. Viewer at
`ocean-icechunks/hycom/viewer/` (gridlook `2649e66`).

Times: listing 12 s; full header scan 74-78 s at 128 threads; skeleton plus 22 yearly region
writes 23:26:22 → 23:28:16, about 5 s per year against Source Cooperative.

## The full header scan passed

All 63,341: one schema, one coordinate hash, sizes equal to what the headers imply, in-file
`time` and `tau` equal to the filenames. Exactly two layouts — 35,902 files with a 4640-byte
header and 27,439 with 4600 — mixed within experiments 532-537, as the sample predicted.

## The build log is in the store, not the notebook

The first run (with `RUN_WRITE = True`) wrote and tagged the store and then **stalled in
validation**, at 3.3 GB and climbing, and was killed, so its notebook outputs were never
saved. The committed outputs are a second, `RUN_WRITE = False` run. Nothing was lost: every
batch is a commit whose message gives the year, the reference count and the file count, and
the notebook prints that history. Do not rebuild just to get "build outputs" — that adds 23
snapshots for nothing.

## Why it stalled: `chunks={}` on this store — the most important user-facing fact

With `chunks={}` each 4-D variable is a dask array of **2,570,880 chunks**. Every
`.sel(...)` on it costs ~1.4 s to build and ~2.2 s to compute, and about 1 GB of memory,
before any data moves; the validation loop did that ~270 times with two such datasets open.
Measured on the published store, two levels at a 12x12 box:

| open with | select | compute | peak memory |
|---|---|---|---|
| `chunks=None` | 0.00 s | 0.45-0.63 s | ~300 MB |
| `chunks={}` | 1.4 s | 2.2 s | ~1.1 GB |

The pattern that works: open with `chunks=None` (still lazy), select the times wanted, then
`.chunk({"time": 1})` on the selection if dask is wanted. The README must lead with this —
it is the opposite of the advice in the `virtual-icechunk` skill and in `~/icechunks`, which
say `chunks={}`. That advice is right for stores with thousands of chunks, not millions.

## Other things measured

- Anonymous open 0.9-1.5 s. A level from a year not yet touched 0.65 s (manifest fetch
  included), so the 2920-steps-per-manifest split is fine. Missing step 0.14 s.
- `chunks=None`: one level 0.76 s; 40-chunk profile 2.2 s; a day at a point (8 chunks) 0.46 s.
- `zarr`'s `nchunks_initialized` lists every key: 34 s for one 2-D variable (63,341, correct).
  The 4-D ones would be 40x that, so they are covered by the build's own count plus the value
  checks.
- Values: raw `int16` identical to netCDF4 for 30 files — first, last, both sides of all nine
  experiment boundaries, the longest gap, eight random. 239 s.

## The gaps

hycom.org's FAQ lists 923 missing times; all are gaps here. Our other 8 are the whole
2014-12-31 12Z run (through 2015-01-01 09Z), between experiments 53.8 and 53.9. It is absent
from `data.hycom.org` too, so it is a real gap the FAQ omits, not a fault in the AWS copy.
`missing-time-steps.csv` carries a `listed_by_hycom_org` column.

## Not done yet

README (with reuse statement), mirroring the docs to `ocean-icechunks/hycom/` (mirror from
merged `main` only), the CORS request to help@hycom.org / COAPS, and the PR for branch
`smoke-test-issue-1`. Eli has not yet looked at the production viewer.
