# HYCOM GOFS 3.1 Global Ocean Reanalysis — virtual Icechunk

One of the HYCOM stores in [ocean-icechunks/hycom](https://github.com/ocean-icechunks/hycom),
which says what they have in common. This page is about this dataset.

The [HYCOM GOFS 3.1 global reanalysis](https://www.hycom.org/dataserver/gofs-3pt1/reanalysis)
(GLBv0.08 **expt_53.X**, 41-layer HYCOM + NCODA, 1/12°, **3-hourly, 1994–2015**) as one
[Icechunk](https://icechunk.io) store that opens in about a second as a single
`(time, depth, lat, lon)` datacube:

**`https://data.source.coop/ocean-icechunks/hycom/hycom-gofs-3pt1-reanalysis`**

This is a **virtual** store. It holds about 85 MB of Zarr metadata and 10,451,265 byte-range
references; the 306 TB of arrays stay where they are, in 63,341 NetCDF files in the
[HYCOM bucket on AWS Open Data](https://registry.opendata.aws/hycom-gofs-3pt1-reanalysis/)
(`s3://hycom-gofs-3pt1-reanalysis`, us-west-2, managed by COAPS). Every read of a science
value goes to that bucket, so the store works only as long as the bucket does. No data was
copied, rewritten or changed.

| | |
|---|---|
| Time | 1994-01-01 12:00 → 2015-12-31 09:00, every 3 hours: 64,272 steps, **931 of them missing** |
| Grid | `depth` 40 levels (0–5000 m) × `lat` 3251 (−80…90) × `lon` 4500 (−180…179.92) |
| Variables | `water_temp`, `salinity`, `water_u`, `water_v` (4-D); `surf_el`, `water_temp_bottom`, `salinity_bottom`, `water_u_bottom`, `water_v_bottom` (time, lat, lon) |
| Layout | one repository, one group, one chunk per time step and depth level (29 MB each) |
| Version | tag `v1`, built 2026-09-18 |

## How to open it

Python ≥ 3.12 (Icechunk 2.x requires it). No credentials are needed for anything.

```
pip install "icechunk>=2.2" "xarray>=2026.7" "zarr>=3.4" "dask[array]"
```

```python
import icechunk, xarray as xr, zarr

# Zarr's default of 10 concurrent requests badly under-uses object storage.
zarr.config.set({"async.concurrency": 64})

def open_hycom(ref="v1"):
    """The HYCOM GOFS 3.1 reanalysis as a lazy xarray Dataset. `ref` is a tag or "main"."""
    url = "https://data.source.coop/ocean-icechunks/hycom/hycom-gofs-3pt1-reanalysis"
    repo = icechunk.Repository.open(icechunk.http_storage(url))
    # The arrays live in the HYCOM bucket, outside the store, so each virtual chunk container
    # has to be authorized — anonymously here. This is the one step a virtual store adds. The
    # container is in the store's saved config, so you do not need to know its URL.
    auth = {p: icechunk.credentials.HttpAccess for p in repo.config.virtual_chunk_containers}
    repo = repo.reopen(authorize_virtual_chunk_access=auth)
    session = repo.readonly_session("main") if ref == "main" else repo.readonly_session(tag=ref)
    return xr.open_zarr(session.store, consolidated=False, chunks=None)   # lazy; see below

ds = open_hycom()
```

### Select first, then chunk

`chunks=None` above is deliberate, and it is **still lazy** — nothing is read until you ask
for values. The usual `chunks={}` works here but is slow: it makes each 4-D variable a dask
array of **2,570,880 chunks**, and dask then spends seconds and about a gigabyte on every
operation, however small the selection. Select what you want first and hand dask only that:

```python
sst = ds.water_temp.isel(depth=0).sel(time=slice("2010-06-01", "2010-06-10"),
                                      lat=slice(20, 40), lon=slice(-160, -140))
mean = sst.chunk({"time": 1}).mean("time").compute()     # streams 80 time steps through dask
```

Do not skip the `.chunk(...)` on a large selection: without dask, everything selected is
loaded at once. The same 10-day mean, measured three ways (identical results):

| | time | peak memory |
|---|---|---|
| `chunks=None`, select, `.chunk({"time": 1})` — **recommended** | 5 s | 0.45 GB |
| `chunks={}`, then select | 14 s | 1.6 GB |
| `chunks=None`, select, no dask | 4.5 s | 1.3 GB, and growing with the selection |

### Missing time steps

The time axis is **regular**: every 3-hourly step is there, including the 931 for which the
archive has no file. Those steps read as NaN, fetch nothing, and are marked by two
coordinates that travel with every variable:

```python
present = ds.isel(time=ds.tau.notnull().values)      # only the steps that exist
analyses = ds.isel(time=(ds.tau == 0).values)        # only the 12Z analyses
ds.water_temp.groupby("experiment")                  # by HYCOM experiment (530 … 539; 0 = no file)
```

`tau` is the forecast hour within each daily run (0 is the 12Z analysis, 3–21 the forecast
steps that fill the day). The gaps are **not random**: 593 of the 931 are 12Z analyses, about
7 % of them, against 0.6 % of any other hour. A plain time mean therefore under-weights 12Z;
for anything with a daily cycle, average daily means instead, and use
`resample(time="1D").count()` to see which days are short.

[`missing-time-steps.csv`](missing-time-steps.csv) lists all 931. hycom.org publishes
[its own list](https://www.hycom.org/faqs/471-did-you-know-there-are-missing-days-in-the-gofs-3pt1-global-reanalysis)
of 923 and says they will not be filled; all 923 are gaps here too. The other 8 are the whole
2014-12-31 run, between experiments 53.8 and 53.9, which is absent from hycom.org's own
server as well.

## What to expect from reads

Measured from a JupyterHub in **us-west-2, the same region as the HYCOM bucket**, with
`async.concurrency = 64`. Metadata comes from Source Cooperative and data from the HYCOM
bucket, so elsewhere the shapes are the same and the numbers larger.

| read | time |
|---|---|
| open the store | 0.9 s |
| one level, global map (1 chunk, 29 MB) | 0.8 s |
| full-depth profile at one point (40 chunks, 1.2 GB fetched) | 2.2 s |
| one day at one point, one level (8 chunks) | 0.5 s |
| a missing time step | 0.1 s |

**Any selection inside a level fetches the whole 29 MB level.** The source files are
uncompressed and unchunked, and a level is the smallest contiguous piece (3251 is prime, so
it cannot even be split into latitude bands). Maps, sections, profiles and area means over
days to months are the good cases. **A point time series over the whole record is the bad
one: a single level at a single point is 1.85 TB of reads.** No setting changes that; only
rewriting the data would.

Values decode to **float64**, where the source NetCDF gives float32, because Zarr attributes
are JSON and cannot say "float32". A decoded level is 117 MB. Use `.astype("float32")` to
halve that, or `xr.open_zarr(..., mask_and_scale=False)` for the raw `int16`.

## View it in a browser

[water_temp](https://data.source.coop/ocean-icechunks/hycom/viewer/index.html#icechunk+https://data.source.coop/ocean-icechunks/hycom/hycom-gofs-3pt1-reanalysis::varname=water_temp::dimIndices_time=0::dimIndices_depth=0) ·
[salinity](https://data.source.coop/ocean-icechunks/hycom/viewer/index.html#icechunk+https://data.source.coop/ocean-icechunks/hycom/hycom-gofs-3pt1-reanalysis::varname=salinity::dimIndices_time=0::dimIndices_depth=0) ·
[surf_el](https://data.source.coop/ocean-icechunks/hycom/viewer/index.html#icechunk+https://data.source.coop/ocean-icechunks/hycom/hycom-gofs-3pt1-reanalysis::varname=surf_el::dimIndices_time=0) ·
[water_u](https://data.source.coop/ocean-icechunks/hycom/viewer/index.html#icechunk+https://data.source.coop/ocean-icechunks/hycom/hycom-gofs-3pt1-reanalysis::varname=water_u::dimIndices_time=0::dimIndices_depth=0) ·
[water_v](https://data.source.coop/ocean-icechunks/hycom/viewer/index.html#icechunk+https://data.source.coop/ocean-icechunks/hycom/hycom-gofs-3pt1-reanalysis::varname=water_v::dimIndices_time=0::dimIndices_depth=0)

**This needs a CORS-disabling browser extension.** A browser reading a virtual store talks to
two hosts. Source Cooperative allows it; the HYCOM bucket answers a ranged GET with no
`Access-Control-Allow-Origin` header (checked 2026-09-18), so an ordinary browser draws the
axes and blocks every data read. Only the bucket's owner can change that, with a CORS policy;
the store would not need rebuilding. With an extension, a 16-step test copy of this store
was seen to render on 2026-09-18; this full store uses the same viewer build and layout.
The viewer is [gridlook](https://github.com/eeholmes/gridlook), and each frame is a whole
29 MB level, so it is not quick.

## About the data

Global Ocean Forecasting System (GOFS) 3.1 reanalysis by the U.S. Naval Research Laboratory,
Ocean Dynamics and Prediction Branch: HYCOM with NCODA data assimilation, run on the 1/12°
GLBb0.08 grid and interpolated by NRL to the GLBv0.08 grid (0.08° in longitude; 0.08° in
latitude between 40°S and 40°N and 0.04° poleward) and to 40 fixed depth levels. Surface
forcing is NCEP CFSR and CFSv2. Each day is one run: the 12Z analysis (`tau = 0`) and the
3-hourly steps to 09Z the next day. The reanalysis is a sequence of ten experiments,
53.0 to 53.9, recorded per time step in the `experiment` coordinate:

| experiment | from | to |
|---|---|---|
| 53.0 | 1994-01-01 12Z | 1999-04-01 09Z |
| 53.1 | 1999-04-01 12Z | 2001-01-01 09Z |
| 53.2 | 2001-01-01 12Z | 2003-07-01 09Z |
| 53.3 | 2003-07-01 12Z | 2005-07-01 09Z |
| 53.4 | 2005-07-01 12Z | 2007-07-01 09Z |
| 53.5 | 2007-07-01 12Z | 2009-07-01 09Z |
| 53.6 | 2009-07-01 12Z | 2011-07-01 09Z |
| 53.7 | 2011-07-01 12Z | 2013-07-01 09Z |
| 53.8 | 2013-07-01 12Z | 2014-12-31 09Z |
| 53.9 | 2015-01-01 12Z | 2015-12-31 09Z |

**Known problems, from [hycom.org](https://www.hycom.org/dataserver/gofs-3pt1/reanalysis):**
unrealistic deep-water formation in the Ryukyu Trench in the western Pacific (and possibly
elsewhere), which led to occasional instabilities over the whole water column; and noisy sea
surface height and layer interfaces in the Philippine Sea. Read their description before
using either region.

### Variables

| variable | dims | standard_name | units |
|---|---|---|---|
| `water_temp` | time, depth, lat, lon | `sea_water_temperature` (in-situ) | degC |
| `salinity` | time, depth, lat, lon | `sea_water_salinity` | 1e-3 |
| `water_u` | time, depth, lat, lon | `eastward_sea_water_velocity` | m/s |
| `water_v` | time, depth, lat, lon | `northward_sea_water_velocity` | m/s |
| `surf_el` | time, lat, lon | `sea_surface_height_above_geoid` | m |
| `water_temp_bottom` | time, lat, lon | `sea_water_temperature_at_sea_floor` | degC |
| `salinity_bottom` | time, lat, lon | `sea_water_salinity_at_sea_floor` | 1e-3 |
| `water_u_bottom` | time, lat, lon | `eastward_sea_water_velocity_at_sea_floor` | m/s |
| `water_v_bottom` | time, lat, lon | `northward_sea_water_velocity_at_sea_floor` | m/s |
| `tau` (coordinate) | time | `forecast_period` | hours |
| `experiment` (coordinate) | time | — (CF flag values 0, 530…539) | — |

All nine science variables are stored as the source's big-endian `int16` with
`scale_factor = 0.001`, an `add_offset` of 20 for temperature and salinity, and
`_FillValue = -30000` over land and below the sea floor.

## How this was built

[`hycom-icechunk-sc.ipynb`](hycom-icechunk-sc.ipynb) with
[`hycom_virtual.py`](hycom_virtual.py); dependency floors in
[`requirements.txt`](requirements.txt).
[`hycom-smoke-test-local.ipynb`](hycom-smoke-test-local.ipynb) is the same build on 29 files
into a temporary local repository — it needs no credentials and runs in 90 seconds. The
build notebook also needs `icechunk_utils.py`, from the repository root, for Source
Cooperative write credentials; reading and validating need nothing.

The source files are NetCDF 64-bit offset (NetCDF-3): **uncompressed and unchunked**, each
4-D variable one 1.17 GB byte range. Because nothing is compressed, a depth level is a
contiguous 29 MB slice of that range, so the store references one chunk per level without
rewriting anything. The idea of sub-chunking this archive is Rich Signell's
([hycom-kerchunk](https://github.com/rsignell/hycom-kerchunk),
[write-up](https://medium.com/pangeo/using-kerchunk-with-uncompressed-netcdf-64-bit-offset-files-cloud-optimized-access-to-hycom-ocean-9008ba6d0d67)).

**No file is parsed.** Each file's header is read with one 67 kB ranged GET and the
references are computed from it, which is why 63,341 files of 4.8 GB take a 75-second scan
and two minutes of writes. Before anything is written, every file must pass the same checks:
one record, the same schema as every other file, byte-identical coordinates, a size equal to
what its header implies, and an in-file `time` and `tau` equal to those in its filename. All
63,341 passed.

**Offsets come from each file's own header, never from a template.** The archive has two
header layouts, 40 bytes apart: 35,902 files spell four standard names `…_at_bottom` and
27,439 do not. The two are mixed within experiments 53.2–53.7, so neither the experiment nor
the date predicts the layout. References built from one file's offsets put the data of the
other kind 20 grid cells out of place.

The store is written as a skeleton (coordinates, and science arrays holding no references)
followed by one commit per year, so its history is its build log:
`icechunk.Repository.open(...).ancestry(branch="main")`.

### What was changed from the source

Metadata only — no array value is touched — to make the store CF-1.11 compliant. The IOOS
compliance checker passes `cf:1.11` on an export of it.

| what | source | store | why |
|---|---|---|---|
| bottom variables' `standard_name` | `…_at_bottom`, or no suffix at all | `…_at_sea_floor` | the CF names; also reconciles the two file layouts |
| `surf_el` `standard_name` | `sea_surface_elevation` | `sea_surface_height_above_geoid` | the former is only an alias in the CF table |
| salinity `units` | `psu` | `1e-3`, with `source_units = "psu"` | `psu` is not a unit UDUNITS can parse; values unchanged |
| `tau` | `units = "hours since analysis"`, per-file `time_origin` | `units = "hours"`, `standard_name = "forecast_period"`, no `time_origin` | the source units do not parse; the origin differs in every file |
| `time` `calendar` | `gregorian` | `standard` | CF's current name for the same calendar |
| temperature, `time` | — | `units_metadata` | CF-1.11 recommendations |
| global | `Conventions = "CF-1.6 NAVO_netcdf_v1.1"` | `CF-1.11`, plus `title`, `experiment_id`, `references`, `source_data`, `comment`; the original kept as `source_Conventions` | the source files name no experiment, grid or version anywhere but the filename |
| added | — | `experiment` coordinate; `tau` extended over the missing steps as NaN | provenance per time step, and a way to find the gaps without reading data |

### Provenance and validation

- Store tag **`v1`** = snapshot `VBMJX9KNE9BN8GTG5100`, built 2026-09-18 with icechunk 2.2.2,
  virtualizarr 2.7.3, zarr 3.4.0, xarray 2026.7.0, Python 3.12.
- [`source-files.csv.gz`](source-files.csv.gz) is the source manifest: every file referenced,
  with its size, experiment, forecast hour and header length.
- Validated anonymously from the public URL: the time axis, `tau` and `experiment` reconcile
  exactly with the bucket listing; `surf_el` holds exactly 63,341 references; and raw `int16`
  read through the references is **identical to netCDF4-C's own byte-range reader** for 30
  files — the first and last, both sides of all nine experiment boundaries, the longest gap,
  and eight at random — across all nine variables. The executed notebook shows the run.
- **Not verified:** reads from outside us-west-2; rendering of this full store in a browser
  (only the 16-step test copy was looked at, and only with a CORS extension); and the
  references for the ~63,000 files not sampled, which rest on the header checks above.

The archive is static (1994–2015, no updates), so there is no update pipeline.

## Reuse and citation

**Code.** The notebooks and `hycom_virtual.py` are released under
[Apache-2.0](https://github.com/ocean-icechunks/hycom/blob/main/LICENSE). You are free to
use, copy, modify, and redistribute them, including commercially. If you use them in
published work, in a presentation, or in another repository, please give attribution:

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

**Data.** The data is not ours, and this store contains none of it — only references to
files in the HYCOM bucket. The AWS Open Data registry states "There are no restrictions on
the use of this data." hycom.org
[recommends this acknowledgement](https://www.hycom.org/publications/acknowledgements/hycom-data)
in any publication using HYCOM data:

> Funding for the development of HYCOM has been provided by the National Ocean Partnership
> Program and the Office of Naval Research. Data assimilative products using HYCOM are funded
> by the U.S. Navy. Computer time was made available by the DoD High Performance Computing
> Modernization Program. The output is publicly available at https://hycom.org.

The data is a demonstration product of the HYCOM Consortium, provided as is.

## Credits

- **Data:** U.S. Naval Research Laboratory, Ocean Dynamics and Prediction Branch; served by
  the HYCOM Consortium and COAPS (Florida State University); hosted on AWS Open Data.
  Questions about the data: help@hycom.org.
- **Sub-chunking uncompressed NetCDF-3:** Rich Signell.
- **Icechunk packaging:** built with [Icechunk](https://icechunk.io),
  [VirtualiZarr](https://virtualizarr.readthedocs.io) and [Xarray](https://xarray.dev),
  hosted on [Source Cooperative](https://source.coop/ocean-icechunks/hycom).
