# Plan — virtual Icechunk of the HYCOM GOFS 3.1 reanalysis (issue #1)

Written 2026-09-18, after the research pass and a feasibility probe. No build code exists
yet. This is the `virtual-icechunk` skill's "research and plan" deliverable; the next step
is the smoke-test notebook.

## Source (measured, not from the docs)

- Bucket `hycom-gofs-3pt1-reanalysis`, us-west-2, anonymous. The hub is also us-west-2.
- **63,341** `.nc` files, **305.8 TB** (278 TiB), plus one zero-byte `2015/` key.
  1994-01-01 12Z → 2015-12-31 09Z, **one 3-hourly step per file**.
- Filename: `YYYY/hycom_GLBv0.08_<expt>_<YYYYMMDD>12_t<tau>.nc`; valid time = run date 12Z
  + tau. In a 200-file sample the in-file `time` equalled the filename time 200/200, and
  in-file `tau` equalled `tNNN` 200/200.
- NetCDF 64-bit offset (`CDF\x02`), `numrecs = 1`, uncompressed big-endian `int16` with
  `scale_factor`/`add_offset` (float32) and `_FillValue = -30000`.
- Grid `depth 40 × lat 3251 × lon 4500`; `lon` is −180 … 179.92 (not 0–360).
- Variables: `water_u`, `water_v`, `water_temp`, `salinity` (4-D, 1,170,360,000 bytes
  each) and `water_u_bottom`, `water_v_bottom`, `water_temp_bottom`, `salinity_bottom`,
  `surf_el` (2-D, 29,259,000 bytes each). Also `tau` (per time) and the coordinates.
- One depth level = 3251 × 4500 × 2 = **29,259,000 bytes**, contiguous. That is the chunk.
  It cannot be split further: 3251 is prime (no equal latitude bands), and longitude
  ranges are not contiguous bytes.

### Two header layouts — the thing that breaks the "template" trick

Only two file sizes exist: 4,827,801,984 (35,902 files) and 4,827,801,944 (27,439 files).
In the 200-file stratified sample (all ten experiments, both sizes), size predicted the
header layout every time: header length 4640 vs 4600, every data offset 40 bytes apart.
The cause is four standard names — older files write `…_at_bottom`, newer ones omit the
suffix (4 × 10 bytes). Coordinates were byte-identical across the whole sample. Sizes are
mixed *within* experiments 532–537, so experiment number does not predict layout.

rsignell's `0_hycom_generate_refs.ipynb` scans the first file with kerchunk and reuses its
offsets for every file. For the 27,439 short-header files that would be 40 bytes = 20
`int16` values = 20 longitude cells off. **Inferred from his notebook; his published
parquet was not opened to confirm.** Do not repeat this: offsets come from each file's own
header.

### Gaps

Of 64,272 three-hourly slots, **931 have no file**; 593 of those are 12Z (the analysis
step, ~7 % of all 12Z steps; other hours lose ~0.6 % each). No duplicate times, no overlap
between experiments. hycom.org has an FAQ on missing days
(`/faqs/471-did-you-know-there-are-missing-days-in-the-gofs-3pt1-global-reanalysis`) —
cross-check our list against it in the smoke test.

Experiments by valid time (from the listing): 530 1994-01-01→1999-04-01, 531 →2001-01-01,
532 →2003-07-01, 533 →2005-07-01, 534 →2007-07-01, 535 →2009-07-01, 536 →2011-07-01,
537 →2013-07-01, 538 →2014-12-31, 539 2015. Each starts at 12Z and ends at 09Z.

## Build approach

No per-file VirtualiZarr/kerchunk pass, and no `NetCDF3Parser` (so no kerchunk/scipy).

1. List the bucket (64 requests; `list_bucket.py`).
2. **One small ranged GET per file** (~67 KB: header + `time` + `tau`), parsed with a
   ~40-line CDF header parser (`cdfhdr.py`). ~4 GB total, in-region.
3. **Check every file; assume nothing**: header hash (with `tau:time_origin` masked) is
   one of the two known, `numrecs == 1`, size matches layout, in-file time == filename
   time, coordinate bytes hash identical. Any failure stops the build.
4. Compute the references vectorised and build `ChunkManifest.from_arrays` →
   `ManifestArray` with codec `bytes(endian=big)`, no compressor. ~10.5 M references
   (63,341 × 165), under VirtualiZarr's ~50 M single-commit guidance.
5. One repository, one group, nine science variables. Manifests split on `time`; `time`
   written as a single chunk. Splitting size is to be measured, not copied.

## Feasibility probe (2026-09-18) — `issue-1-research/probe.py`

Four slots, 2004-12-28 06Z–15Z: both layouts and one missing step. Clean 3.12 venv:
icechunk 2.2.2, virtualizarr 2.7.3, zarr 3.4.0, xarray 2026.7.0, obstore 0.11.1;
`async.concurrency = 64`; hub in us-west-2. Local repo 116 KB / 22 files, fresh
read-only session with explicit virtual authorisation.

| Read | `s3://` refs | HTTPS refs |
|---|---|---|
| one level (29 MB) | 0.6 s | 0.4 s |
| 40 levels (1.17 GB) | 5.4 s | 4.2 s |

Missing step read back all-NaN (not timed separately — do that in the smoke test). Values
identical to a netCDF4-C `#mode=bytes` read for one file of each layout. The probe decoded
to float64 because it passed `scale_factor` as a Python float; keep it float32 as in the
source so reads decode to float32.

## Decisions (Eli, 2026-09-18)

- **Regular 3-hourly time axis, 64,272 steps, gaps left unreferenced (NaN).** Main uses are
  means and time series, not the viewer: `rolling(time=8)` is then always 24 h and plots
  break at gaps instead of bridging them.
- **No `has_data` variable** — it was invented, not a convention. **`tau` does that job**:
  it is a real source variable, loaded along `time`, NaN at gaps.
  `ds.sel(time=ds.time[ds.tau.notnull()])` is the present-only view; `tau == 0` is
  analysis-only. Repair its metadata: `standard_name = forecast_period`, `units = "hours"`
  (the source's `hours since analysis` fails UDUNITS), drop per-run `time_origin`.
- **HTTPS references**, prefix
  `https://hycom-gofs-3pt1-reanalysis.s3.us-west-2.amazonaws.com/`.
- **Salinity**: `standard_name = sea_water_salinity`, `long_name = "Sea Water Salinity"`,
  `units = "1e-3"`, plus `source_units = "psu"`. Values unchanged. `salinity_bottom` the
  same with `sea_water_salinity_at_sea_floor`.
- **Experiment identity in the store, not just a README** — "there are loads of HYCOM
  experiments". The files themselves carry no experiment, grid or version attribute
  (`source` is just `HYCOM archive file`); it exists only in filenames. So: global
  `experiment_id = "GLBv0.08 expt_53.X"` (CMIP's attribute name; CF has none), **the
  experiment ID in the dataset `title`**, plus `references`/source URLs.
- Also ship a CSV of the 931 missing time steps beside the store.

- **Per-time `experiment` variable — yes.** `int16` along `time`, 530–539 as in the
  filenames, CF `flag_values`/`flag_meanings` (`expt_53.0 … expt_53.9`), and
  `0 = no_source_file` rather than a fill value, so it stays integer and nothing is guessed
  at gaps (experiment boundaries fall at 12Z, the hour most often missing).
- **Title**: "HYCOM GOFS 3.1 Global Ocean Reanalysis, GLBv0.08 expt_53.X, 3-hourly,
  1994–2015".

## CF repairs (metadata only; checked against standard-name table v94 and UDUNITS)

- `…_at_bottom` → `…_at_sea_floor` (valid names; also reconciles the two layouts).
- `sea_surface_elevation` is an alias → `sea_surface_height_above_geoid`.
- `psu` → `1e-3`; `tau` units as above; `calendar = gregorian` → `standard`.
- Keep `missing_value`, `NAVO_code`. Run cf-checker in the smoke test.

## Known limits — say these in the README

- **Point time series are expensive and unfixable**: one level at one point over the
  record fetches 29 MB per step, ~1.8 TB. Maps, sections and area means are the good case.
- **A plain time mean under-weights 12Z** because the gaps are not random. Average daily
  means instead; `resample(time="1D").count()` shows short days.
- **The browser viewer will draw axes but no data.** The source bucket answers ranged GETs
  with 206 and no `Access-Control-Allow-Origin`; OPTIONS preflight is 403 (checked
  2026-09-18). Same failure as CoastWatch. Fix is a bucket CORS policy from
  help@hycom.org / COAPS; publish the viewer anyway and draft that request.
- Provider's own known problems (hycom.org): unrealistic deep water in the Ryukyu Trench;
  noisy SSH in the Philippine Sea.

## Destinations

- Tests: `ocean-icechunks/test-repo/hycom`. Production:
  `ocean-icechunks/hycom/hycom-gofs-3pt1-reanalysis`. Never point a test at the latter.
- Write credentials come from the `source-coop` CLI (`~/.cargo/bin/source-coop`); the cache
  was dated 2026-09-17 when checked, so expect to need `source-coop login`.

## Remaining deliverables from the issue

Smoke-test notebook (local, then scratch prefix) → production notebook → README with reuse
statement → `requirements.txt` and the reproducibility set used in `~/icechunks` → gridlook
viewer → mirror docs to the store root.
