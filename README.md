# HYCOM as virtual Icechunk stores

[HYCOM](https://www.hycom.org) ocean model output, published as
[Icechunk](https://icechunk.io) stores on
[Source Cooperative](https://source.coop/ocean-icechunks/hycom) so that a whole archive
opens in about a second as one lazy `xarray` datacube.

The stores are **virtual**: each holds only Zarr metadata and byte-range references. The
arrays stay in the provider's original NetCDF files, nothing is copied or rewritten, and
every read of a science value goes to the provider's bucket. A store therefore works only
as long as its source does, and reads exactly what the source files contain.

## Datasets

One directory per dataset, each with its own README, build notebooks and
`requirements.txt`. This is the first of several; more HYCOM experiments will be added the
same way.

| Dataset | Coverage | Store | Docs |
|---|---|---|---|
| **GOFS 3.1 Global Ocean Reanalysis**, GLBv0.08 expt_53.X | global 1/12°, 40 levels, 3-hourly, 1994–2015 | `https://data.source.coop/ocean-icechunks/hycom/hycom-gofs-3pt1-reanalysis` | [`hycom-gofs-3pt1-reanalysis/`](hycom-gofs-3pt1-reanalysis/README.md) |

## Opening a store

Python ≥ 3.12. No credentials are needed. Each dataset's README has the specifics; the
shape is always this:

```python
import icechunk, xarray as xr, zarr

zarr.config.set({"async.concurrency": 64})    # the default of 10 badly under-uses object storage

url = "https://data.source.coop/ocean-icechunks/hycom/hycom-gofs-3pt1-reanalysis"
repo = icechunk.Repository.open(icechunk.http_storage(url))
# The arrays live in the provider's bucket, outside the store, so each virtual chunk container
# has to be authorized — anonymously here. This is the one step a virtual store adds.
auth = {p: icechunk.credentials.HttpAccess for p in repo.config.virtual_chunk_containers}
store = repo.reopen(authorize_virtual_chunk_access=auth).readonly_session("main").store
ds = xr.open_zarr(store, consolidated=False, chunks=None)
```

**Select first, then chunk.** These are large archives of small chunks — the reanalysis has
2.57 million chunks per 4-D variable — and handing dask the whole thing with `chunks={}`
costs seconds and about a gigabyte on every operation. `chunks=None` is still lazy. Select
the times and region you want, then call `.chunk({"time": 1})` on that selection so dask
streams it instead of loading it at once.

## Viewer

One [gridlook](https://github.com/eeholmes/gridlook) build at
`https://data.source.coop/ocean-icechunks/hycom/viewer/index.html` serves every store here;
the store to open rides in the URL fragment, and each dataset's README has its links.
A browser reading a virtual store talks to two hosts, the store's and the source's. Where
the source bucket sends no CORS headers — true of the reanalysis bucket — the viewer draws
the axes and no data unless the browser runs a CORS-disabling extension.

## In this repository

| | |
|---|---|
| `<dataset>/` | that dataset's README, build and smoke-test notebooks, helper module, `requirements.txt` and manifests |
| `icechunk_utils.py` | Source Cooperative write credentials, through the `source-coop` CLI (from [ocean-icechunks/icechunks](https://github.com/ocean-icechunks/icechunks)) |
| `publish_viewer.py` | builds gridlook and publishes it beside the stores |
| `claude/` | working notes: the plan, the decisions and what each build taught |

Each dataset is built in the same order: a written plan, a smoke test into a temporary local
repository, the same test written to `ocean-icechunks/test-repo/hycom/` with a viewer and a
short README, and only then the published store, which is validated anonymously from its
public URL against an independent reader.

## Reuse and citation

This work is released under [Apache-2.0](LICENSE). You are free to use, copy, modify, and
redistribute it, including commercially. If you use it in published work, in a presentation,
or in another repository, please give attribution:

> Holmes, E.E. and Signell, R. (2026). *HYCOM as virtual Icechunk stores*.
> ocean-icechunks/hycom. https://github.com/ocean-icechunks/hycom

Rich Signell is named because this work rests on his: he showed that the uncompressed
NetCDF-3 files of this archive can be given virtual chunks, one per depth level, without
rewriting them. None of his code is used here, but the approach is his. Please cite it too:

> Signell, R. (2024). *Using Kerchunk with uncompressed NetCDF 64-bit offset files:
> Cloud-optimized access to HYCOM Ocean Model output on AWS Open Data*. Pangeo (Medium).
> https://medium.com/pangeo/using-kerchunk-with-uncompressed-netcdf-64-bit-offset-files-cloud-optimized-access-to-hycom-ocean-9008ba6d0d67
>
> Signell, R. (2024). *hycom-kerchunk*. https://github.com/rsignell/hycom-kerchunk

The **data** is not ours, and the stores contain none of it — only references to the
provider's files. Each dataset's README gives its terms and the acknowledgement its provider
asks for. For HYCOM data, hycom.org
[recommends](https://www.hycom.org/publications/acknowledgements/hycom-data):

> Funding for the development of HYCOM has been provided by the National Ocean Partnership
> Program and the Office of Naval Research. Data assimilative products using HYCOM are funded
> by the U.S. Navy. Computer time was made available by the DoD High Performance Computing
> Modernization Program. The output is publicly available at https://hycom.org.
