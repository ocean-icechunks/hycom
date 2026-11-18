# Plan: GOMb0.01 layout A virtual Icechunk store (issue #17)

Written 2026-11-18. This is step 1 of #17, the `virtual-icechunk` skill's "research and plan"
deliverable. **No build code exists yet. Eli reviews this before the smoke test is written.**
Everything marked *measured* was run today; *predicted* is arithmetic from the audit's
throughput tests (`audit/report.md`, "Expected performance from S3") and is not yet measured on
this bucket. Decisions already made are in #17 ("Decided"). The open questions are at the end
(Q1–Q8).

## Scope

The scope is experiments 010, 023 and 026, all with chunk layout A, from **2001-01-16 00Z to 2024-04-28 23Z**. That is
**204,096 hourly time steps**. The store has one group, `hourly`, holding all 11 variables. The 653 hours where 026 and 027
overlap (2024-04-01 19Z → 04-28 23Z) come from 026, because 027 is layout B. That follows from
the layout, not from any judgement about which run is better. 027/028 are out (#15).

## Source and destination: two separate configurations

| | Source (the NetCDF bytes) | Destination (the Icechunk repository) |
|---|---|---|
| Where | `s3://hycom-tsis-gom-reanalysis/data/YYYY/` (us-west-2) | Test: `s3://ocean-icechunks/test-repo/hycom/hycom-tsis-gom-reanalysis`. Production: `…/hycom/hycom-tsis-gom-reanalysis` (Source Cooperative) |
| Access | Anonymous. *Measured:* listing with `--no-sign-request`, h5py and `HDFParser` reads over S3 | Write: `source-coop creds` (renews itself, 0.3.0). Read: anonymous HTTPS `https://data.source.coop/ocean-icechunks/…` |
| URL in references | **`https://hycom-tsis-gom-reanalysis.s3.us-west-2.amazonaws.com/data/`**, as in GOFS 3.1 (`URL_PREFIX`), so readers need no AWS client or region setup, and so a browser can read it if the bucket gets CORS | n/a |
| Readers authorize | `{URL_PREFIX: icechunk.credentials.HttpAccess}` (needs icechunk ≥ 2.1) | `icechunk.http_storage(...)` (≥ 2.0) |

Check before step 4: does the source bucket send `Access-Control-Allow-Origin` on a ranged GET?
If not, the viewer gets the same "needs a CORS extension" caveat as GOFS 3.1.

## Source facts (measured 2026-11-18)

- **Bucket re-listed today: unchanged since the review this morning.** It has 347,881 objects with the
  same keys and sizes. 2001–2020 are still stopped partway through each year. **2021, 2022 and 2023
  are complete: 8,760 × 2d and 8,760 × 3z each.**
- 2022 is all experiment 023. One 2d and one 3z file from 2022 (day 100, 12Z) were probed over
  S3. Both are NetCDF-4/HDF5, uncompressed, no shuffle, little-endian float32:
  - 2d: 6 variables, chunk {1 × 1537 × 2101}, one 12,916,948-byte chunk each.
  - 3z: 5 variables, chunk {1 × 10 × 385 × 526}, 64 chunks of 8,100,400 bytes each. **The edge tiles
    are stored padded to full size** (4 × 385 = 1540 > 1537, 4 × 526 = 2104 > 2101). Zarr also pads
    edge chunks, so a Zarr chunk of 385 × 526 maps byte-for-byte onto each HDF5 chunk. One depth
    of one tile is a contiguous 810,040 bytes.
- **File sizes vary by a few bytes within a kind** (layout A files on S3 today: 3z 2,592,206,800 /
  …209,268 / …206,874 / …206,837 / …200,447; 2d 77,566,331 / …414 / …343 / …426 / 77,668,896).
  So offsets come from every file's own header, as the audit found (F1).
- `HDFParser` (VirtualiZarr 2.8.0) opened each file in about 1 s, serially, from the hub. The 2d
  output is ready to use as it stands. The 3z output is the 10-depth chunk only.
- **Attributes that must not be copied from one file:** each 3z variable has `valid_range`
  *for that hour* (water_temp at 2022-04-10 12Z: 0.73–28.77). `long_name` carries the
  experiment version (`temp [01.0H]`). The global `experiment` attribute is `"01.0"` in a 023 file,
  so it is not the experiment number in the filename.
- Time: `MT` = days since 1900-12-31, float64, but rounded through float32 in 3z (audit F8).
  The time axis is built from the filenames: `NNN_archv.YYYY_DDD_HH_{2d,3z}.nc`.

## Parser and reference scheme

Two ways to get each file's chunk offsets. Both are proven on these files:

- **(a) `HDFParser` + manifest split (recommended).** Open each file with `open_virtual_dataset`.
  For 3z, split every 10-depth reference into `10/d` references at `offset + k·d·810,040`, with length
  `d·810,040`. VirtualiZarr reads the attributes, dims and coordinates; we write one small, testable
  function. Verify on the smoke-test hours that the split offsets equal h5py's.
- **(b) h5py chunk index, as in `audit/08_one_group.py`.** Read `get_chunk_info` per file and
  build `ChunkManifest.from_arrays` directly. More code of our own, but no dependence on
  VirtualiZarr's dataset assembly. That matters if building per-file `xr.Dataset`s for 2 × 8,760
  files is slow, which is the main thing the smoke test will tell us.

Either way, the per-hour references go into pre-allocated numpy arrays (`paths`, `offsets`,
`lengths`) for a month at a time, and a gap hour is an empty path (a missing chunk, which reads
as the fill value). No `xr.concat` of 8,760 virtual datasets.

## Discovery and bad-file handling

- One S3 listing of `data/YYYY/` (31 s for the whole bucket). Keep keys matching
  `^(010|023|026)_archv\.\d{4}_\d{3}_\d{2}_(2d|3z)\.nc$`, which drops `_COPY` and `_CORRUPTED`
  keys and the `u.y2016_*` strays. 027/028 are dropped by experiment number, plus a time cut at
  2024-04-28 23Z.
- **Expected size check:** within ±70 kB of 77.57 MB (2d) or 2.592 GB (3z). Anything else is skipped
  and listed. This catches the 6 empty 2006 day 177 3z files (49,818 bytes) and any truncated copy.
  Every file is also opened, so a size inside the band that will not open as HDF5 is skipped and listed too.
- **Exclusion list, applied by name:** the 5 regenerated 2002 3z files (day 046 12, 16Z; day 051
  06, 07, 09Z) until HYCOM confirms them.
- Each build writes its skip list (key, reason) next to the build log. Hours without a file are
  NaN.
- **Checksum pin:** `last_updated_at` = the build time, as tested in `audit/07_checksum_pin.py`.
  A file HYCOM later replaces then fails loudly instead of returning new bytes under the old
  references.

## Store layout

Group `hourly`. Names and repairs follow the GOFS 3.1 store, so the two can be read the same
way (Q3):

| Name | Dims | Kind | Notes |
|---|---|---|---|
| `time` | time | loaded, **one chunk** (204,096) | int64 hours since 2001-01-16 00Z… or GOFS's `hours since 2000-01-01`; from filenames |
| `depth` | depth | loaded | 40 depths, 0–5000 m |
| `lat`, `lon` | lat / lon | loaded | identical in 2d and 3z (audit `08_one_group.py`) |
| `experiment` | time | loaded, one chunk | int16 10/23/26, as GOFS 3.1 has; 0 where no file |
| `ssh`, `mixed_layer_thickness`, `u_barotropic_velocity`, `v_barotropic_velocity`, `wnd_ewd`, `wnd_nwd` | time, lat, lon | virtual | chunk {1, 1537, 2101}, as decided |
| `u`, `v`, `w_velocity`, `water_temp`, `salinity` | time, depth, lat, lon | virtual | chunk {1, d, 385, 526}, d chosen on 2022 |
| `bathymetry`, `mask` (Q4) | lat, lon | loaded | from `topo/regional.{depth,mask}.nc`, if their grid matches |

- `_FillValue` 1.267651e+30 as the Zarr fill value and in the encoding. Data are not scaled.
- Variable attributes come from the source without `valid_range`, with `long_name` stripped of
  the `[01.0H]` suffix (Q5). CF repairs as in GOFS (`Conventions` CF-1.11, `source_Conventions`
  kept, `standard_name`s checked against the table, `units_metadata` for temperature).
- Global attributes are built once by us, not taken from whichever file was opened first.

## Manifests and batches

- **References** (layout A, the full record, *predicted*): 2d 1.2 M. 3z by d: 10 → 65 M,
  5 → 131 M, 2 → 327 M, 1 → 653 M. For 2022 alone at d = 1: 28 M (3z) + 53 k (2d).
- **Manifest splitting along `time`, one manifest per month** (about 730 time steps). At d = 1
  that is about 470 k references per 3z variable per manifest, about 3.4 MB at the audit's 7 B/ref.
  A reader opening one month touches 5 manifests of that size, not one 5 GB manifest.
- **One commit per month.** That bounds memory and gives a restart point. The build skips months
  already committed (it reads `time` and `experiment` from the store).
- This hub now has 31 GB and 4 cores (cgroup today), not the 3.9 GB of earlier sessions. That is
  enough for the 2022 test. The full-build machine (one us-west-2 VM, or several with
  `fork`/`merge`) is sized from the 2022 measurements in step 3.

## Predicted read performance (to be measured on 2022)

From the audit's same-region rates, at raw S3 speed. Icechunk's read path may take up to twice as long.

| One variable | 2d, whole map | 3z, d = 10 | 3z, d = 2 | 3z, d = 1 |
|---|---|---|---|---|
| one hour, one depth, full map | < 1 s | ~1 s (130 MB fetched) | < 1 s (26 MB) | < 1 s (13 MB) |
| point time series, 1 year | ~7 min (113 GB) | ~3.5 min (71 GB) | ~40 s | ~20 s |
| 200 × 200 box, every hour of a year | ~7 min | ~14 min | ~3 min | ~1.5 min |

- 2d point time series are slow by design (whole maps). The 53-row-band option stays
  available if the team needs them (audit, "2d: the whole map").
- Readers outside us-west-2 will see much less. Data reads go to the HYCOM bucket, not to
  Source Cooperative.
- Store open time with 204 k time steps, a one-chunk `time` and monthly manifests is predicted
  to take seconds. It is measured in step 3.
- Readers should open with `chunks=None`, select, then `.chunk()`, as GOFS 3.1 recommends. At
  d = 1 a 3z variable has 3.3 billion chunks for the full record, so `chunks={}` would build a
  dask graph that big.

## Steps 2–4 (what follows the review)

1. **Smoke test** (`hycom-tsis-gom-reanalysis/smoke-test.ipynb`, local temporary repository): 6
   hours of 2022 including **one gap hour made deliberately** (one key left out of the list,
   since 2022 has no real gap). All 11 variables at d = 1 and d = 10. Reopen read-only, assert
   dims, coords and attrs, and compare a map, a 40-depth profile and a 6-hour point series with
   h5py. Time the per-file parse, (a) against (b).
2. **2022 performance test** at d = 10, 2 and 1 (Q2). It measures build time, peak memory,
   parse rate, open time, and the read table above (box inside one tile and across four).
   Eli chooses d.
3. **Scratch store** in `test-repo/hycom/hycom-tsis-gom-reanalysis`, with a README and the
   viewer catalog entry (`publish_viewer.py` `DATASETS`). The viewer must point to group `hourly`
   (Q7).

## Versions (hub kernel, 2026-11-18)

Python 3.13.18, icechunk 2.3.1, virtualizarr 2.8.0, zarr 3.4.2, xarray 2026.9.0, obstore 0.12.1,
h5py 3.16.0. The build gets its own `requirements.txt`, tested in a clean venv
(`/srv/conda/envs/notebook/bin/python3.13 -m venv` in the scratchpad).

## Questions for Eli

- **Q1. Parser:** (a) `HDFParser` + split, or (b) h5py chunk index? Recommendation: write (a) and
  time both in the smoke test, then keep the faster.
- **Q2. 3z candidates for the 2022 test:** d = 10 (as stored, the baseline), 2 and 1? 5 adds
  little between 10 and 2.
- **Q3. Names:** GOFS-style `time/depth/lat/lon` (the viewer already defaults to `time` and `depth`),
  or HYCOM's `MT/Depth/Latitude/Longitude`? Recommendation: the GOFS names, with the source names in
  attributes.
- **Q4. Static fields (review D4):** add `bathymetry` and `mask` from `topo/` as 2-D loaded
  variables? The smoke test checks their grid against `lat`/`lon` first.
- **Q5. Attributes:** drop per-hour `valid_range`, and strip `[01.0H]` from `long_name`? Keep a
  per-time `experiment` coordinate (10/23/26), as GOFS 3.1 has?
- **Q6. Time units:** `hours since 2001-01-16 00:00:00` (the record start), or GOFS's
  `hours since 2000-01-01`? Only the encoding differs. xarray decodes either to the same times.
- **Q7. Viewer:** gridlook has not been pointed at a store whose data sit in a group. It needs
  checking in step 4. If it can't, the fallback is a viewer-only path, not moving the data.
- **Q8. Gaps not yet listed:** the 2011-05-28 00–05Z hours that the audit found missing from
  HYCOM, and the empty 3z hours other than 2006 day 177, are NaN in 3z with 2d present. Fine
  to document them in the README as a table rather than flag them in the store?
