# Plan: GOMb0.01 layout A virtual Icechunk store (issue #17)

Written 2026-11-18 and revised 2026-11-19 with Eli's answers. This is step 1 of #17, the
`virtual-icechunk` skill's "research and plan" deliverable. **Step 2, the local smoke test, is done**
([result](#smoke-test-result-2026-11-19)), and its findings are folded in below. *Measured*
means run on 2026-11-18/19. *Predicted* is arithmetic from the audit's throughput tests
(`audit/report.md`, "Expected performance from S3"), not yet measured on this bucket. The
decisions made earlier are in #17 ("Decided"). This round's are under [Decisions](#decisions-eli-2026-11-19).

Contents: [Decisions](#decisions-eli-2026-11-19) · [For the HYCOM team](#for-the-hycom-team) ·
[For the team (FYI)](#for-the-team-fyi) · [Known gaps](#known-gaps-at-first-build) ·
[Scope](#scope) · [Source and destination](#source-and-destination-two-separate-configurations) ·
[Source facts](#source-facts-measured) · [Parser](#parser-and-reference-scheme) ·
[Discovery and bad files](#discovery-and-bad-file-handling) · [Store layout](#store-layout) ·
[Time](#time-the-encoding-of-mt) · [Proposed repairs](#proposed-repairs-every-one) ·
[Manifests](#manifests-and-batches) · [Performance](#predicted-read-performance-to-be-measured-on-2022) ·
[Next steps](#steps-24-what-follows-the-review) · [Open questions](#still-open)

## Decisions (Eli, 2026-11-19)

- **Names follow the GOM files, not GOFS 3.1:** `MT`, `Depth`, `Latitude`, `Longitude`, `Date`, and
  the variable names as the files have them. Repairs (attributes, CF) may follow the GOFS 3.1 store
  where nothing in the GOM files argues otherwise. **Every proposed repair is listed below**, for
  review.
- **Parser:** (a) `HDFParser` plus a manifest split, with (b) h5py timed against it in the
  smoke test, keeping the faster.
- **3z chunkings for the 2022 test:** 10, 2 and 1 depths per chunk.
- **Static fields:** add bathymetry and the land/sea mask from `topo/`.
- **Viewer:** check gridlook with a store whose data are in a group when the scratch store goes up (step 4).
- **Known gaps:** document them as a table in the README, not as flags in the store ("fine I think").
- **Time: (A), the source's convention** (Eli, 2026-11-19): float64 `days since 1900-12-31 00:00:00`,
  the values as the 2d files hold them. That 1/24 of a day is not exact in binary comes from how
  HYCOM wrote its files, and the store keeps it as they did. No switch to integer hours.
- **Repairs R4, R8 and R10 follow what the GOFS 3.1 store did** (Eli, 2026-11-19); see the
  table for what that means for each.
- **R13: `bathy` gets `standard_name = "sea_floor_depth_below_geoid"`. R7: drop `valid_range`.
  R14: `mask` as int8 with flags** (Eli, 2026-11-19). With these, every repair R1–R20 is settled.
  R19 and R20 came out of the CF check below; R19 is GOFS's repair, and R20 is mechanical.
- **R21: the store declares 2**100 as `_FillValue` and Zarr `fill_value`** (Eli, 2026-11-19). That is the value
  HYCOM actually wrote on land, not the attribute's 1.267651e30, so land and gap hours both read as missing.
  Metadata only. Found in the smoke test; see the R21 row and HYCOM item 7.
- **R22: a per-hour `cell_methods` flag** (Eli, 2026-11-19). Some hours are not model output: HYCOM
  rebuilt them as the mean of the neighbouring hours with `ncra`, and those files say so in their own
  `cell_methods = "MT: mean"` attribute (audit F5; the 2005-03-20 04Z 3z file in the smoke test). A
  per-hour attribute cannot go on a variable, so the store carries it as a flag variable along `MT`,
  **taken from the files' attributes, not invented**. Proposed shape in the R22 row, for the team.
- **2004-06-01 19Z 2d is a gap** (Eli, 2026-11-19): the file is chunked like layout B, so it is skipped. It is
  in the gaps table and on the HYCOM list (item 6).
- **The 3z `Longitude` drift goes to HYCOM** (item 8), and with the fill-value mismatch it is an FYI for the
  team ([For the team](#for-the-team-fyi)).

## For the HYCOM team

What Eli needs to raise with HYCOM, with the file names. Everything here was checked against
HYCOM's listing (`s3-review/out/hycom-listing.csv.gz`, 2026-11-18) and the S3 listing (2026-11-18/19).
Items 1–8 affect this store (layout A). Items 9–10 are about layout B.

1. **When will the rest of 2001–2020 be on S3?** The copy of every year from 2001 to 2020 stopped
   partway through the year about 2026-11-16 18:16 UTC. For example, 2001 stops at day 266 and 2010 at day 219.
   About 111,600 hourly files are still to come, and the S3 listing had not moved on
   2026-11-19. *(If the file team, not HYCOM, runs the copy, this question goes to them.)*
2. **Five 2002 3z files were regenerated on 2026-11-10**, with the old ones kept as
   `_CORRUPTED`: `010_archv.2002_046_12_3z.nc`, `…_046_16_3z.nc`, `…_051_06_3z.nc`, `…_051_07_3z.nc`,
   `…_051_09_3z.nc`. What was wrong with the old ones, and are the new ones final? Our spot check
   (three 1 MiB ranges) found old and new identical, so we cannot tell from the bytes. **These are
   left out of the store until HYCOM answers.**
3. **17 3z hours were renamed `_CORRUPTED` with no replacement.** Will they be regenerated?
   - 2002 day 139 (19 May): 18, 20, 21, 23Z
   - 2004 day 083 (23 Mar): 12, 16, 18, 21Z
   - 2006 day 210 (29 Jul): 00, 01, 03, 04, 05Z
   - 2006 day 268 (25 Sep): 01, 02, 04, 05Z
4. **18 3z files are empty** (zero time steps; 239 bytes or 49 KB), and their 2d files are fine. Is
   the 3z output for these hours lost, or can it be regenerated?
   - 2002 day 347 (13 Dec): 00–05Z
   - 2006 day 177 (26 Jun): 18–23Z. *These six were also copied to S3. The file team should delete them.*
   - 2014 day 335 (1 Dec): 12–17Z
5. **6 3z hours have no file at all**: 2011 day 148 (28 May) 00–05Z. Their 2d files exist. Lost or
   recoverable?

   Items 3–5 are all of layout A's 3z gaps on HYCOM's server: **41 hours, all experiment 010**.
   No other hour has a 2d file without a 3z file. All gaps at first build are in the table under
   [Known gaps at first build](#known-gaps-at-first-build).
6. **`2004/010_archv.2004_153_19_2d.nc` (2004-06-01 19Z) is chunked like layout B**: 2d
   chunks of 769 × 1051 instead of whole maps, though it is experiment 010. It is also 102 kB larger
   than the other 2d files. Was it regenerated? Could it be rewritten with the usual chunking? Until
   then the store skips it, so that hour is a 2d gap (found by the smoke test, 2026-11-19).
7. **The `_FillValue` attribute does not match the land values.** In every layout A file sampled
   (2001–2024, all three experiments, every variable), `_FillValue` is float32(1.267651e30), but land
   is written as 2**100 = 1.2676506e30, 3 ulps away. Readers that mask by `_FillValue` (xarray,
   netCDF4, CF tools) leave every land point at 1.27e30 when they open these files. HYCOM may want to
   know. The store works around it (R21, decided).
8. **The 3z files' `Longitude` drifts from the 2d files' from 2021 on.** In 3z files from 2021-01-01 00Z
   onward (023 and 026), 1,848 of the 2,101 longitudes differ from the 2d files' by up to 3.4e-5°. The 3z
   files up to 2020-10-18 11Z (the last 2020 file on S3) match the 2d ones. The 2d values are right, equal to
   float32(−98 + 0.01·i) within 3.7e-6. The 3z values drift along the axis (−97.98999, −97.97998,
   −97.96997, …), as if the longitude were built by adding 0.01 repeatedly in float32. Latitude is the same in
   both. Questions: which 3z files are affected (we see 2021-01-01 on; Oct–Dec 2020 is not on S3 yet), what changed in
   the processing, and is anything else in those 3z files different? The data are on the same grid. The
   store uses the 2d longitudes. (Found 2026-11-19.)
9. *(Layout B, #16, only if the team wants it)*: 028 has wind stress and no 10 m winds. Could
   HYCOM add `wnd_ewd`/`wnd_nwd` to 028, as was done for 027?
10. *(Layout B, for the file team rather than HYCOM)*: 9 truncated 028 copies to redo. Also, 3z hours
   missing on S3: 2025-08-02 01Z, 05–09Z and 11Z, and 2026-02-05 08Z, 03-13 07Z, 04-10 22Z and 04-20 12Z.
   Also remove `2012/010_archv.2012_138_00_3z.nc_COPY` from the bucket. Full detail is in
   `s3-review/report.md`, "For the file team".

## For the team (FYI)

Two inconsistencies in the source files that do not change the store's data, but do affect anyone who reads the
files directly (on S3, data.hycom.org or THREDDS). Both are on the HYCOM list.

- **Land is not masked when the files are opened directly** (HYCOM item 7). The `_FillValue` attribute
  (1.267651e30) is not the value written on land (2**100), and CF readers need an exact match. xarray on a
  source file returns 945,478 land points per map as 1.27e30, which breaks means and colour scales unless the
  user masks it. The store fixes this with R21. A script that reads the files must mask `> 1e29` itself.
- **The 3z longitudes drift from 2021 on** (HYCOM item 8): up to 3.4e-5° (about 3.5 m), growing along the axis.
  It is the same grid, and the store uses the 2d longitudes. Code that matches 2d and 3z source files by exact
  longitude, or that takes the grid from a 2021+ 3z file, will see different coordinates.
- Also worth knowing: the hours HYCOM rebuilt as means of their neighbours are flagged in the store (R22), and
  the 2004-06-01 19Z 2d file is a gap (layout B chunking).

## Known gaps at first build

Hours on the time axis with no reference, so they read as missing. The 2001–2020 hours not yet copied to S3
are left out of this table (HYCOM item 1). They are gaps only until the copy finishes.

| Kind | Hours | Which | Why | HYCOM item |
|---|---|---|---|---|
| 3z | 17 | 2002 day 139 (18, 20, 21, 23Z); 2004 day 083 (12, 16, 18, 21Z); 2006 day 210 (00, 01, 03, 04, 05Z); 2006 day 268 (01, 02, 04, 05Z) | renamed `_CORRUPTED` by HYCOM, no replacement | 3 |
| 3z | 18 | 2002 day 347 00–05Z; 2006 day 177 18–23Z; 2014 day 335 12–17Z | empty files (zero time steps) | 4 |
| 3z | 6 | 2011 day 148 00–05Z | no file | 5 |
| 3z | 5 | 2002 day 046 12, 16Z; day 051 06, 07, 09Z | held back: regenerated 2026-11-10, waiting for HYCOM | 2 |
| **2d** | **1** | **2004 day 153 19Z** (2004-06-01) | **chunked like layout B; found by the smoke-test scan** | 6 |

That is 46 3z hours and 1 2d hour, of 204,096. The 2d gap is the only one in the 2d record, and its 3z file is
fine. So far only the 32-file transition sample and 9 files of 2022 have been scanned, so the full scan may find
more files like 2004_153_19. This table is updated from each build's skip list. The store README will carry it.

Optional, not needed for the build: the 653 hours where 026 and 027 overlap (2024-04-01 19Z →
04-28 23Z). Which run does HYCOM consider authoritative? This store uses 026 because of the layout.

## Scope

Experiments 010, 023 and 026, all chunk layout A, **2001-01-16 00Z → 2024-04-28 23Z, 204,096 hourly
time steps**. One group, `hourly`, holds all 11 variables and the two static fields. The overlap
hours come from 026, because 027 is layout B. 027/028 are out of scope (#15).

## Source and destination: two separate configurations

| | Source (the NetCDF bytes) | Destination (the Icechunk repository) |
|---|---|---|
| Where | `s3://hycom-tsis-gom-reanalysis/data/YYYY/` (us-west-2) | Test: `s3://ocean-icechunks/test-repo/hycom/hycom-tsis-gom-reanalysis`. Production: `…/hycom/hycom-tsis-gom-reanalysis` (Source Cooperative) |
| Access | Anonymous. *Measured:* listing with `--no-sign-request`, and h5py and `HDFParser` reads over S3 | Write: `source-coop creds` (renews itself, 0.3.0). Read: anonymous HTTPS `https://data.source.coop/ocean-icechunks/…` |
| URL in references | **`https://hycom-tsis-gom-reanalysis.s3.us-west-2.amazonaws.com/data/`**, as GOFS 3.1 uses (`URL_PREFIX`). Readers need no AWS client, and a browser can read it if the bucket gets CORS | n/a |
| Readers authorize | `{URL_PREFIX: icechunk.credentials.HttpAccess}` (icechunk ≥ 2.1) | `icechunk.http_storage(...)` (≥ 2.0) |

To check before step 4: does the source bucket send `Access-Control-Allow-Origin` on a ranged GET?
If not, the viewer gets the same "needs a CORS extension" caveat as GOFS 3.1.

## Source facts (measured)

- **Bucket re-listed 2026-11-19: unchanged since the review.** 347,881 objects, the same keys and sizes.
  **2021, 2022 and 2023 are complete: 8,760 × 2d and 8,760 × 3z each.** 2022 is all experiment 023.
- One 2022 2d and one 3z file (day 100, 12Z) were probed over S3: NetCDF-4/HDF5, uncompressed, no
  shuffle, little-endian float32.
  - 2d: 6 variables, chunk {1 × 1537 × 2101}, one 12,916,948-byte chunk each.
  - 3z: 5 variables, chunk {1 × 10 × 385 × 526}, 64 chunks of 8,100,400 bytes. **The edge tiles are
    stored padded to full size** (4 × 385 = 1540 > 1537, 4 × 526 = 2104 > 2101). Zarr also pads edge
    chunks, so a Zarr chunk of 385 × 526 maps byte for byte onto each HDF5 chunk. One depth of one tile
    is a contiguous 810,040 bytes.
- **File sizes vary by a few bytes within a kind.** 3z files are 2,592,206,800 / …209,268 / …206,874
  / …206,837 / …200,447 bytes, and 2d files 77,566,331 / …414 / …343 / …426 / 77,668,896. So offsets come from every file's
  own header (audit F1).
- `HDFParser` (VirtualiZarr 2.8.0) opened each file in about 1 s, serially, from the hub.
- **Global attributes are the same in 010, 023 and 026** (`Conventions` CF-1.0, `title` HYCOM,
  `source` HYCOM archive file, `experiment` "01.0", `history` python). So `experiment` is
  HYCOM's product version, not the experiment number in the filename. `_NCProperties` differs between
  files (netCDF/HDF5 versions).
- **`MT`** is `days since 1900-12-31 00:00:00`, `calendar = standard`, float64. In 2d files it is
  exact to float64 (2024-04-09 01Z = 45025.041666666664). In 3z it was rounded through float32
  (2010-04-10 01Z = 39912.04296875, which decodes to 01:01:52.5) (audit F8).
- **`topo/`** (NetCDF-3): `regional.depth.nc` (`bathy`), `regional.mask.nc` (`mask`), and
  `regional.grid.nc` (`plon`, `plat`, `pscx`, `pscy`), on dims `(y, x)` with a dummy `time`. **The
  grid is identical** to the data files' `Latitude`/`Longitude` (`plon` rows and `plat` columns
  constant, max difference 0.0). **`mask == 1` exactly where `ssh` is defined** at 2022-04-10 12Z
  (3,229,237 of 3,229,237 points). `bathy` is 0 at all 945,478 land points and runs to 6,726.5 m.
  Neither has units in the file.

## Parser and reference scheme

Decided: (a), timed against (b), keeping the faster. **Outcome (smoke test, 2026-11-19): (b) h5py.** The two
gave byte-identical offsets for all 31 sample files both accepted. h5py was 2–3× faster (32 files: 4.6 s
against 7.7 s, 16 processes). The scan runs in **processes, not threads**. h5py serialises every call on one
global lock, and the reads happen inside those calls, so threads give no parallelism: 8 files took as
long on 8 threads as 4 files serially. `HDFParser` uses h5py too. On this 4-core hub, h5py reaches about
17 files/s at 16 processes: about 17 min for 2022, about 5 h for all 296,585 files. A bigger VM should do better; step 3 measures it.

- **(a) `HDFParser` + manifest split.** `open_virtual_dataset` per file. For 3z, each 10-depth
  reference is split into `10/d` references at `offset + k·d·810,040`, length `d·810,040`. The
  smoke test checks that the split offsets equal h5py's.
- **(b) h5py chunk index** (`audit/08_one_group.py`): `get_chunk_info` per file, then
  `ChunkManifest.from_arrays`.

Either way, a month's references go into pre-allocated numpy arrays (`paths`, `offsets`,
`lengths`), and a gap hour is an empty path, which is a missing chunk and reads as the fill value. There is no
`xr.concat` of 8,760 virtual datasets.

## Discovery and bad-file handling

- One S3 listing of `data/` (31 s). Keep keys matching
  `^(010|023|026)_archv\.\d{4}_\d{3}_\d{2}_(2d|3z)\.nc$`. That drops `_COPY` and `_CORRUPTED` keys and
  the `u.y2016_*` strays. 027/028 are dropped by experiment number, and there is a cut at 2024-04-28 23Z.
- **Size check, changed in the smoke test:** a floor only (77.0 MB 2d, 2.590 GB 3z), which catches the
  six empty 2006 day 177 files on S3. The ±70 kB band would have rejected a file for its size alone
  (2004_153_19_2d is 102 kB larger). **Truncation is caught by the scan instead:** every chunk must end
  inside the file.
- **Per-file layout check in the scan:** shape, chunk shape, dtype, no compression, chunk sizes, and
  `_FillValue`. A file that fails is skipped and listed with its reason. That is how 2004_153_19_2d (layout B
  chunking) was found. Attribute fingerprints (without `valid_range`) and coordinate checksums are
  reported but not fatal. They pick out HYCOM's `ncra` stand-ins (`cell_methods = "MT: mean"`, an NCO
  `history`) and the 3z `Longitude` difference below.
- **Exclusion by name:** the 5 regenerated 2002 3z files (HYCOM item 2).
- Each build writes its skip list (key, reason) beside its log. Hours with no file read as NaN.
- **Checksum pin:** `last_updated_at` = build time (`audit/07_checksum_pin.py`).

## Store layout

Group `hourly`. The names are the source's.

| Name | Dims | Kind | Notes |
|---|---|---|---|
| `MT` | MT | loaded, **one chunk** (204,096) | from the filenames; encoding in [Time](#time-the-encoding-of-mt) |
| `Date` | MT | loaded, one chunk | auxiliary coordinate, as the source has it (`coordinates = "Date"` on every variable); from the filenames |
| `Depth` | Depth | loaded | 40 depths, 0–5000 m |
| `Latitude`, `Longitude` | Latitude / Longitude | loaded | identical in 2d, 3z and `topo/` |
| `experiment` | MT | loaded, one chunk | new: int16 10/23/26, 0 where no file (as GOFS 3.1 has; R12) |
| `cell_methods_2d`, `cell_methods_3z` | MT | loaded, one chunk | new: int8 flags from each file's `cell_methods` (R22) |
| `ssh`, `mixed_layer_thickness`, `u_barotropic_velocity`, `v_barotropic_velocity`, `wnd_ewd`, `wnd_nwd` | MT, Latitude, Longitude | virtual | chunk {1, 1537, 2101} |
| `u`, `v`, `w_velocity`, `water_temp`, `salinity` | MT, Depth, Latitude, Longitude | virtual | chunk {1, d, 385, 526}, d chosen on 2022 |
| `bathy`, `mask` | Latitude, Longitude | loaded | from `topo/`, the names as there (R13, R14) |

## Time: the encoding of `MT`

xarray decodes `MT` to the same datetimes whichever of these is chosen. The choice only affects
what is stored, and what non-xarray readers (netCDF-Java/THREDDS, cftime, gridlook in the
browser) see. All three are standard CF. *Measured:* both (A) and (B) written to Zarr v3 and reopened with
xarray decode all 204,096 hours exactly on the hour (max offset 0 ns).

| | Stored | Pro | Con |
|---|---|---|---|
| **(A) as the source** | float64 `days since 1900-12-31 00:00:00` | The GOM files' own convention. The values equal the 2d files' `MT` bit for bit, so a user comparing with a file sees the same numbers | Hours aren't exact in binary (1/24 day). xarray rounds this away. A reader that does not round could show 00:59:59.999… |
| **(B) source epoch, integer hours** | int64 `hours since 1900-12-31 00:00:00` | Exact everywhere; same epoch as the source; a common choice for hourly model output | The stored number differs from the file's `MT` (a factor of 24) |
| (C) GOFS 3.1 | float64 `hours since 2000-01-01 00:00:00` | Same as the GOFS store | No reason in the GOM files for it; Eli chose source conventions |

**Decided: (A)** (Eli, 2026-11-19). The inexact 1/24 day is how HYCOM wrote the files, and the
store keeps their convention. A reader that does not round is HYCOM's convention showing
through, not a defect of the store, so it is not a reason to switch to (B). The values are not taken
from the 3z files' `MT`, because those are float32-rounded. They are computed from the filename, exactly as a 2d file holds them.

## Proposed repairs, every one

Metadata only: no array values in the source files are changed. "GOFS" means the GOFS 3.1 store
made the same repair. "GOM-specific" means it is needed because of something in these files.
CF standard names were checked against CF standard-name table **v95** (downloaded 2026-11-19):
every source standard name is in the table except `sea_surface_elevation`, which is an alias.

**Coordinates**

| # | What | Source | Proposed | Why | Kind |
|---|---|---|---|---|---|
| R1 | `MT` values | from each file; float32-rounded in 3z | computed from the filename | audit F8 | GOM-specific (GOFS also used filename times) |
| R2 | `MT` attributes | `long_name time`, `units`, `calendar standard`, `axis T` | keep; add `standard_name = "time"` | CF: identifies the time axis without relying on `axis` | GOFS |
| R19 | `MT` `units_metadata` | none | add `"leap_seconds: unknown"` | CF-1.11 §4.4 recommends it with `calendar = standard`; the only recommendation left after R1–R18 in the CF check | GOFS (same on `time`) |
| R3 | `Date` values | float, in 3z float32-rounded (20100410.042) | computed from the filename, `YYYYMMDD + hour/24`, as the 2d files hold it | same as R1 | GOM-specific |
| R4 | `Date` units | `"day as %Y%m%d.%f"` | **Decided: as GOFS.** GOFS replaced `tau`'s non-UDUNITS units (`hours since analysis`) with a valid one and moved the meaning into `long_name`, and it kept a source unit it changed as `source_units` (salinity). For `Date` no valid unit exists, so: remove `units`, keep `source_units = "day as %Y%m%d.%f"`, and set `long_name = "date (YYYYMMDD.fraction of day)"` | not a UDUNITS unit; CF checkers flag it, and a reader could try to decode it as a time | GOFS (same pattern as `tau`, salinity) |
| R5 | `Latitude`, `Longitude`, `Depth`: `_FillValue` | HDF5 default fill (9.97e36) | none | CF 2.5.1: coordinate variables must not have one | GOFS |
| R6 | `Latitude`, `Longitude` `long_name` | none | add `Latitude` / `Longitude` | as `topo/` names them | GOM-specific |

**Data variables**

| # | What | Source | Proposed | Why | Kind |
|---|---|---|---|---|---|
| R7 | `valid_range` | per file, the min/max of that hour (water_temp 0.73–28.77 at one hour) | **drop** | the value of one hour would be wrong for the store, and CF readers would mask valid data outside it | GOM-specific |
| R8 | `long_name` | e.g. `" sea surf. height  [01.0H]"`, `"    baro. u-vel.[01.0H]"` | **Decided: as GOFS, which kept the source `long_name`s verbatim.** The only one GOFS replaced was salinity's, as part of its salinity repair (R10). So keep every `long_name` as written, `[01.0H]` and spacing included. It is the same in all layout A files, so it is consistent across the store. The stripping proposed earlier is withdrawn | GOFS did not tidy source text | GOFS |
| R9 | `ssh` `standard_name` | `sea_surface_elevation` | `sea_surface_height_above_geoid` | only an alias in the CF table | GOFS (same repair on `surf_el`) |
| R10 | `salinity` | `units psu`, `long_name "salinity [01.0H]"` | **Decided: as GOFS.** `units = "1e-3"`, `source_units = "psu"`, `standard_name = "sea_water_salinity"` (unchanged), `long_name = "Sea Water Salinity"` | `psu` is not UDUNITS; `1e-3` is the table's canonical unit | GOFS (`sea_water_practical_salinity`, units `1`, was the alternative; not taken) |
| R11 | `water_temp` | `units degC` | add `units_metadata = "temperature: on_scale"` | CF 1.11 §3.1.2 | GOFS |
| R20 | `coordinates` | `"Date"` on every variable | not copied as an attribute. xarray writes it from the dataset's coordinates, giving `"Date experiment"` | copied verbatim, it overrode xarray's and left `experiment` unattached (seen in the CF check). `Date` stays an auxiliary coordinate, as in the source | mechanical |
| — | `_FillValue` | 1.267651e+30 | keep, as the Zarr fill value too | the CF attribute is the same in every layout A file (audit F7) | — |
| — | HDF5 internals | `_Netcdf4Coordinates`, `_Netcdf4Dimid`, `CLASS`, `NAME`, `DIMENSION_LIST`, `REFERENCE_LIST` | not carried | HDF5/netCDF-4 bookkeeping, not metadata | — |

**New variables**

| # | What | Proposed | Why | Kind |
|---|---|---|---|---|
| R12 | `experiment(MT)` | int16, `flag_values 0 10 23 26`, `flag_meanings "no_source_file expt_01.0_010 …"` (exact wording in the smoke test) | which run each hour came from; the files' global `experiment` is "01.0" in all three, so it can't tell | GOFS |
| R13 | `bathy` | values unchanged, `units = "m"`, `positive = "down"`, **`standard_name = "sea_floor_depth_below_geoid"`** (decided, Eli 2026-11-19), `long_name` kept, `comment` "0 on land" | the file has no units. Land left as 0, not NaN, so no values change | GOM-specific: GOFS 3.1 had no bathymetry, so there was nothing to follow. The choices considered are below |
| R14 | `mask` | int8 (source float32 0/1), `flag_values 0 1`, `flag_meanings "land sea"`, `standard_name = "sea_binary_mask"` | 1 = sea, which the comparison with `ssh` confirms; CF flags want an integer type | GOM-specific |
| — | `plon`, `plat` | not added | identical to `Longitude`/`Latitude` | — |
| — | `pscx`, `pscy` (grid spacing, m) | **not proposed**; available if anyone wants cell areas | Eli asked for bathymetry and mask | — |

**R13: the choices for `bathy`'s standard name.** These are from CF standard-name table v95. A model's
bathymetry is a fixed field, the depth of the sea floor below the model's resting sea surface.

| Standard name | Means | Fits a static model bathymetry? |
|---|---|---|
| **`sea_floor_depth_below_geoid`** | below the geoid, "with which mean sea level would coincide if the ocean were at rest" | **Yes. Recommended.** It is the most common choice for model bathymetry: the table makes the bare `sea_floor_depth` an alias of it, and CMIP6 uses it for `deptho` (from the CMIP6 data request; not re-checked today). It pairs with `ssh`'s `sea_surface_height_above_geoid` (R9), so the two use the same reference surface |
| `sea_floor_depth_below_mean_sea_level` | below a tidal-mean sea level at each point | Close, but MSL is an observed time mean; used for charts and surveys |
| `sea_floor_depth_below_sea_surface` | below the instantaneous surface, "including the variance caused by tides and possibly waves" | No: that changes with time |
| `sea_floor_depth_below_geopotential_datum`, `…_below_reference_ellipsoid` | named survey datums | No: for observations tied to a specific datum |

**Global attributes**

| # | What | Source | Proposed | Kind |
|---|---|---|---|---|
| R15 | `Conventions` | `CF-1.0` | `CF-1.11`, `source_Conventions = "CF-1.0"` | GOFS |
| R16 | `title` | `HYCOM` | `"HYCOM-TSIS GOMb0.01 Gulf of Mexico reanalysis, hourly"`, `source_title = "HYCOM"` | GOFS (GOFS used its own `TITLE`) |
| — | `source`, `experiment`, `history` | as above | keep verbatim | identical in all layout A files |
| R17 | `_NCProperties` | varies by file | drop | per-file library versions |
| R18 | new: `references`, `source_data`, `comment` | — | product page and bucket; "virtual Icechunk, data read from the source files; hours with no file read as missing and `experiment` = 0 there" | GOFS |

**Found in the smoke test (2026-11-19)**

| # | What | Source | Proposed | Why | Kind |
|---|---|---|---|---|---|
| R21 | `_FillValue` and the Zarr `fill_value` of the 11 science variables | attribute float32(1.267651e30) (bits 1904214019); **land written as 2**100** (bits 1904214016), 3 ulps away, in every file and variable sampled | **Decided (Eli, 2026-11-19):** declare 2**100, the value actually on land | CF readers mask by exact equality. With the source attribute, xarray leaves all 945,478 land points at 1.27e30 (measured on a source file), and the store's gap hours would not match land. With R21, `ssh` is defined at exactly the 2,283,759 sea points (`mask == 1`), and gaps read as NaN. Metadata only; no data change | GOM-specific; nothing like it in GOFS |
| — | coordinate source | the 3z `Longitude` of 023/026 files differs from the 2d one by up to 3.05e-5° (1,848 of 2,101 points); the 2d one is identical in every file and to `topo/` | `Latitude`/`Longitude` from a 2d file, `Depth` from a 3z file | the 2d grid is the one `topo/` and every 2d file share | implementation |
| R22 | per-hour `cell_methods` flag (decided, Eli 2026-11-19) | `cell_methods = "MT: mean"` on the variables of files HYCOM rebuilt with `ncra` from the neighbouring hours (with an NCO `history`); absent on model output | **Proposed shape, for the team:** two int8 auxiliary coordinates along `MT`, `cell_methods_2d` and `cell_methods_3z`. `flag_values 0 1 2`, `flag_meanings "none MT_mean no_source_file"`, and `comment` quoting the source attribute. Each science variable names its kind's flag in `ancillary_variables`. Values come from each file's attributes during the scan. Any other `cell_methods` value the scan finds stops the build until it is reviewed | A per-hour attribute cannot go on a variable that spans all hours. It is the files' own metadata, not an invented flag. How many hours are affected is unknown; the audit saw 627 3z files rewritten in Mar–Jun 2026, but not how many are means | GOM-specific |
| R7+ | coordinate `valid_range` | some 3z files (2023-365 on) put `valid_range` on `Depth`/`Latitude`/`Longitude` | dropped, as R7 drops it on the data | same reason as R7 | GOM-specific |

### CF check of these repairs (run 2026-11-19)

IOOS compliance-checker 6.1.0, `cf:1.11`, criteria `normal`, on two NetCDF corners (2 hours, 2
depths, 4 × 4 points) of real 2022 data, 2022-04-10 12–13Z, plus `topo/`. The script is
`claude/notes/issue-17-research/cf_corner.py`. As in the GOFS smoke test, the checker reads NetCDF, not Zarr,
so it checks an export.

- **The source, as HYCOM wrote it: 4 kinds of issue.** `Date` units not UDUNITS (fixed by R4).
  `valid_range` float64 on float32 variables, 11 variables (R7). `Conventions` not CF-1.11 (R15).
  `water_temp` without `units_metadata` (R11).
- **With R1–R18: one recommendation**, `MT` without `units_metadata`. Added as R19. Also, the copied
  `coordinates` attribute left `experiment` out, which led to R20.
- **With R1–R20: "All tests passed!"** at both the `normal` and `lenient` criteria.
- **What the checker does not catch**, and why R9 and R10 stay: it passed `sea_surface_elevation` (only
  an alias in the table) and `psu` (not a UDUNITS unit) in the source. GOFS repaired both anyway.
  The table was checked directly (v95, above).
- **Not checked yet:** the real store. The smoke test re-runs this on an export from the Icechunk store
  itself (whole axes, the gap hour, every variable), as the GOFS smoke test did.

## Manifests and batches

- **References** (layout A, the full record, *predicted*): 2d 1.2 M. 3z by d: 10 → 65 M, 2 → 327 M,
  1 → 653 M. For 2022 alone at d = 1: 28 M (3z) + 53 k (2d).
- **Manifest splitting along `MT`, one manifest per month** (about 730 steps). At d = 1 that is about
  470 k references per 3z variable per manifest, about 3.4 MB at the audit's 7 B/ref.
- **One commit per month**, so memory stays bounded and there is a restart point. The build skips months
  already committed.
- This hub has 31 GB and 4 cores now (cgroup, 2026-11-18), not the 3.9 GB of earlier sessions. That is
  enough for the 2022 test. The full-build machine is sized from the 2022 measurements.

## Predicted read performance (to be measured on 2022)

These use the audit's same-region raw rates. Icechunk's read path may take up to twice as long.

| One variable | 2d, whole map | 3z, d = 10 | 3z, d = 2 | 3z, d = 1 |
|---|---|---|---|---|
| one hour, one depth, full map | < 1 s | ~1 s (130 MB fetched) | < 1 s (26 MB) | < 1 s (13 MB) |
| point time series, 1 year | ~7 min (113 GB) | ~3.5 min (71 GB) | ~40 s | ~20 s |
| 200 × 200 box, every hour of a year | ~7 min | ~14 min | ~3 min | ~1.5 min |

- 2d point time series are slow by design (whole maps). The 53-row-band option stays available.
- Readers outside us-west-2 will see much less. Data reads go to the HYCOM bucket, not to Source
  Cooperative.
- Readers open with `chunks=None`, select, then `.chunk()`, as GOFS 3.1 recommends. At d = 1 a 3z
  variable has 3.3 billion chunks.

## Steps 2–4 (what follows the review)

1. **Smoke test** (`hycom-tsis-gom-reanalysis/gom-smoke-test-local.ipynb`, local temporary repository; done, see below): 6
   hours of 2022, one of them deliberately left out to make a gap. All 11 variables plus `bathy`/`mask`,
   at d = 1 and d = 10, with every repair above. Reopen read-only, assert dims, coords and attrs,
   compare a map, a 40-depth profile and a 6-hour point series with h5py, and check that the gap is
   NaN. Time the per-file parse, (a) against (b).
2. **2022 performance test** at d = 10, 2, 1: build time, peak memory, parse rate, open time and
   the read table above (a box inside one tile and one across four). Eli chooses d. The CF checker
   runs on the result.
3. **Scratch store** at `test-repo/hycom/hycom-tsis-gom-reanalysis`, with a README (gaps table)
   and a viewer catalog entry. The viewer needs a per-store `view` and `variables`, because the dims are
   `MT`/`Depth`, not the defaults `time`/`depth`. Check the group, the `MT` display (A or B), and CORS.

## Versions (hub kernel, 2026-11-18)

Python 3.13.18, icechunk 2.3.1, virtualizarr 2.8.0, zarr 3.4.2, xarray 2026.9.0, obstore 0.12.1,
h5py 3.16.0. The build gets its own `requirements.txt`, tested in a clean venv.

## Still open

- Waiting on HYCOM: [For the HYCOM team](#for-the-hycom-team), items 1–8. Not blocking the 2022 work.
- **For the team review:** the shape of the R22 flag (names, flag values, one flag per kind), and the two
  [FYI items](#for-the-team-fyi).

## Smoke test result (2026-11-19)

`hycom-tsis-gom-reanalysis/gom-smoke-test-local.ipynb`, code in `gom_virtual.py`. Run in a clean venv from
`hycom-tsis-gom-reanalysis/requirements.txt` (Python 3.13.18, pandas 3.1.1), 0 errors, about 75 s. It built 6 hours
of 2022 at d = 10 and d = 1 in local repositories: a skeleton commit, then two region writes, with manifests split
every 3 steps. Then it reopened them in fresh read-only sessions:

- **Every value identical to h5py**: a 2d map, a 3z one-depth map, a 40-depth profile, a 200 × 200 box over
  four tiles, and a 6-hour point series, at both chunkings.
- **Gaps behave as designed:** 13Z (3z left out) has `ssh` and no 3z data. 14Z (both left out) has
  neither. `experiment` is `[23, 23, 23, 23, 0, 23]`.
- `MT` stored equals the 2d file's `MT` bit for bit (`44295.416666666664`), with the units string verbatim.
- Every repair checked by assertion. **`cf:1.11` "All tests passed!"** on an export from the store, gap hours
  included.
- **R22 added and re-run (2026-11-19, clean venv, 0 errors):** on the transition sample the 2005-03-20 04Z 3z
  file is flagged 1 (`MT_mean`), the skipped 2004-06-01 19Z 2d file 2, every other hour 0. On the store,
  `cell_methods_3z` = `[0,0,0,2,2,0]` and `cell_methods_2d` = `[0,0,0,0,2,0]`. `cf:1.11` still passes.
- **Transition sample** (16 hours, 32 files, both experiment boundaries and every file size): this found
  HYCOM items 6 and 7, the 3z `Longitude` difference, and the 2005 `ncra` stand-in's distinct attribute
  fingerprint.
- Two library details are in the code comments. xarray 2026.9 reads a float `_FillValue` in Zarr v3 only in its
  base64 form, so `gom_virtual.py` encodes it as xarray would. xarray's own datetime encoding would
  shorten the `MT` units string, so `MT` is written as plain float days.

## One-month check (2026-11-19)

`claude/notes/issue-17-research/month_check.py`, clean venv, January 2022 at d = 1, local repository, in-region,
`async.concurrency` 128. Skeleton over all of 2022, then January as one region-write batch.

| | Measured |
|---|---|
| Scan, 1,488 files, 16 processes | 53 s, **28 files/s**, 0 errors; 2 fingerprints (2d, 3z); no `cell_methods` in January |
| Skeleton for the year (8,760 hours) | 8.5 s build, 2.9 s write; 0.84 GB |
| January batch, 2,385,264 references | 6.0 s build, 11.8 s write and commit; 2.2 GB |
| Manifests for the month | 14.9 MB (about 6 B per reference) |
| Open, fresh session | 0.03 s |
| `water_temp` 1-depth map, 1 hour / 40-depth profile | 0.44 s / 0.48 s |
| `water_temp` point, 1 depth, month | 1.6 s |
| 200 × 200 box, month: inside 1 tile / over 4 tiles | 1.6 s / 5.2 s |
| `ssh` point, month (whole 12.9 MB maps) | 14.8 s |
| Peak memory (during the reads) | 4.1 GB |
| Value against h5py | identical |

**For production: the skeleton does not scale to the full record.** It allocates empty path, offset and length
arrays for every chunk on the time axis: 0.84 GB for one year at d = 1, so about 20 GB for 204,096 hours. The full
build must create the empty science arrays without a manifest (for example with zarr directly: same metadata,
attributes and fill value, no chunks), then region-write the months. That is not needed for the 2022 test.

## 2022 test year: results for choosing the 3z chunking (2026-11-19)

`claude/notes/issue-17-research/year_test.py`. Raw results are in `year2022-results/`. Clean venv, this hub (4 cores, 31
GB), local repositories, in-region, `async.concurrency` 128. One scan, then for each d a skeleton and 12 monthly
commits. All 8,760 hours were present (experiment 023). No `cell_methods` and no scan errors in 2022. Value checks
against h5py were identical at every d.

**Scan:** 17,520 files in 626 s, 28 files/s, 0 errors. That predicts about 3 h for all 296,585 layout A files on this hub.

| | d = 1 | d = 2 | d = 10 |
|---|---|---|---|
| References, 2022 | 28.1 M | 14.1 M | 2.9 M |
| Build: 12 monthly batches | 194 s | 94 s | 20 s |
| Manifests, 2022 | 316 MB | 160 MB | 34 MB |
| Open, fresh session (local) | 0.03 s | 0.03 s | 0.03 s |
| `water_temp` 1-depth map, 1 hour | 0.5 s | 0.3 s | 0.3 s |
| `salinity` 40-depth profile, 1 hour | 0.5 s | 0.2 s | 0.2 s |
| **`water_temp` point, 1 depth, year** | **17 s** | 27 s | 117 s |
| **200 × 200 box inside 1 tile, year** | **16 s** | 28 s | 114 s |
| **200 × 200 box over 4 tiles, year** | **58 s** | 112 s | 448 s |
| `ssh` point, year (2d, whole maps; any d) | 157 s | — | — |

**Predicted for the full layout A record (×23.3, arithmetic):** d = 1: 653 M references, about 7.4 GB of manifests,
about 75 min of batches. d = 2: 327 M, 3.7 GB, about 37 min. d = 10: 66 M, 0.8 GB, about 8 min. Add the scan (about 3 h
here) in every case.

**Measured reads were at or below the audit's predictions.** For example, the point series was predicted at about 20 s
(d = 1) and about 3.5 min (d = 10), and the 4-tile box at about 1.5 min and about 14 min.

**Findings from the run:**
- **S3 returned one HTTP 500 InternalError** ("Please try again") on one of the 35,040 GETs of the first 4-tile box
  read. Icechunk passed it straight to the reader. A retry succeeded. The README should tell readers to retry long
  reads. `year_test.py` now retries and records each retry (`run1-s3-500.log`).
- **Build memory grew steadily across monthly batches**: 2.8 → 6.0 GB over 12 months at d = 1, about 0.3 GB per month.
  For the full record, use a fresh process (or reopened repository) per year, or find the leak.
- Manifests were about 11 B per reference for the year against 6 B for January alone. The 730-hour manifest splits
  do not line up with the monthly commits, which may explain it. Check before production.
- **Not measured yet:** opening and reading from Source Cooperative, where manifests come over the network. At
  d = 1 a month of one 3z variable is about 5 MB of manifest. The scratch store (step 4) will show this.

**Choice for Eli:** the d for 3z. Maps and profiles are fast at every d. Time series and boxes are 2–8 times faster at
d = 1 than at d = 10, and about 2 times faster than at d = 2. d = 1 costs 10 times the references and manifests of d = 10.

