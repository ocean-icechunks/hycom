# HYCOM ocean model output — Icechunk

**[🌐 View data in browser](#view-it-in-a-browser)** · **[💻 Data access (code)](#how-to-open-it)** · **[📦 Data access (HYCOM.org)](https://www.hycom.org/dataserver)**

[HYCOM](https://www.hycom.org) ocean model output, published as
[Icechunk](https://icechunk.io) stores on
[Source Cooperative](https://source.coop/ocean-icechunks/hycom) so that a whole archive
opens in about a second as one lazy `xarray` datacube.

| Dataset | Icechunk repository | Docs |
|---|---|---|
| **GOFS 3.1 Global Ocean Reanalysis**, GLBv0.08 expt_53.X — global 1/12°, 40 levels, 3-hourly, 1994–2015 | `https://data.source.coop/ocean-icechunks/hycom/hycom-gofs-3pt1-reanalysis` | [README](https://github.com/ocean-icechunks/hycom/blob/main/hycom-gofs-3pt1-reanalysis/README.md) |

This is the first of several; more HYCOM experiments will be added the same way, one
repository each.

The stores are **virtual**: each holds only Zarr metadata and byte-range references. The
arrays stay in the provider's original NetCDF files, nothing is copied or rewritten, and
every read of a science value goes to the provider's bucket. A store therefore works only
as long as its source does, and reads exactly what the source files contain. That costs one
extra step when opening — see [How to open it](#how-to-open-it) — and it is why the browser
viewer needs the workaround described below.

## View it in a browser

> ### ⚠️ Read this first: the data will not draw unless you disable CORS
>
> The viewer loads, lists the variables and draws the map graticule, and then stops —
> because the science arrays are not in the stores. They are in the provider's bucket, and a
> browser reading a virtual store therefore talks to two hosts. Source Cooperative allows
> it; the GOFS 3.1 reanalysis bucket on AWS has no CORS configuration (checked 2026-09-19),
> so **your browser** refuses to hand those bytes to the page. Nothing the viewer or this
> repository can contain will waive that; only the bucket's owner can.
>
> To look at the data anyway, install a CORS-disabling browser extension (search your
> browser's extension store for "CORS unblock" or "Allow CORS"), enable it, and reload
> the viewer. Such an extension switches off a real security protection for the sites you
> enable it on, so turn it back off when you are done — or use a separate browser profile
> for it.
>
> The code path below has no such problem: this affects browsers only.

| Dataset | Viewer |
|---|---|
| GOFS 3.1 Global Ocean Reanalysis | [Open it in the viewer](https://data.source.coop/ocean-icechunks/hycom/viewer/index.html#icechunk+https://data.source.coop/ocean-icechunks/hycom/hycom-gofs-3pt1-reanalysis::varname=water_temp::dimIndices_time=0::dimIndices_depth=0) |

One [gridlook](https://github.com/eeholmes/gridlook) build, published alongside the data at
[`hycom/viewer/`](https://data.source.coop/ocean-icechunks/hycom/viewer/index.html), serves every store here: the store to open rides in the URL
*fragment*, which the host never sees, and the viewer's dataset picker lists them all. Each
dataset's README has links per variable.

## How to open it

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

## About the data

One directory per dataset in the
[GitHub repository](https://github.com/ocean-icechunks/hycom), each with its own README —
coverage, variables, gaps, known problems, what to expect from reads — plus its build
notebooks, `requirements.txt` and source manifest. On Source Cooperative the same files are
under `docs/<dataset>/`.

| Dataset | Source | Details |
|---|---|---|
| GOFS 3.1 Global Ocean Reanalysis, GLBv0.08 expt_53.X | [AWS Open Data](https://registry.opendata.aws/hycom-gofs-3pt1-reanalysis/), 63,341 NetCDF files, 306 TB | [`hycom-gofs-3pt1-reanalysis/`](https://github.com/ocean-icechunks/hycom/blob/main/hycom-gofs-3pt1-reanalysis/README.md) |

## How this was built

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

## Credits

- **Data:** the HYCOM Consortium and the U.S. Naval Research Laboratory; served by COAPS
  (Florida State University). Each dataset's README credits its own source.
- **Sub-chunking uncompressed NetCDF-3:** Rich Signell.
- **Icechunk packaging:** built with [Icechunk](https://icechunk.io),
  [VirtualiZarr](https://virtualizarr.readthedocs.io) and [Xarray](https://xarray.dev),
  hosted on [Source Cooperative](https://source.coop/ocean-icechunks/hycom); the original
  file bytes remain with the provider.
