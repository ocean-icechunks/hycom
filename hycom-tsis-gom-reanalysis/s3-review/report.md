# HYCOM-TSIS GOMb0.01 on S3 — file review before building the Icechunk store

Project issue: [ocean-icechunks/2026-ioos-hackathon#22](https://github.com/ocean-icechunks/2026-ioos-hackathon/issues/22).
Review run 2026-11-18 against the public bucket `s3://hycom-tsis-gom-reanalysis` (us-west-2,
anonymous read), compared with `https://data.hycom.org/datasets/GOMb0.01/reanalysis/data/` on
the same day and with the September audit of that server ([../audit/report.md](../audit/report.md),
issue #8). The question: what is on S3, is it a faithful copy, and what does it change for the
store design in issue #11?

**The copy was still in progress during the review.** Objects were written between 2026-10-31
and 2026-11-18 02:00 UTC. Every number below is as of the listing taken 2026-11-18 ~16:57 UTC
(`out/s3-listing.csv.gz`).

## Summary

1. **What is there:** 347,888 objects, 466 TB. 329,193 hourly files, 18,687 daily-mean files,
   the model grid, bathymetry and land mask (`topo/`), and one model configuration file
   (`config/blkdat.input`).
2. **The copies that can be checked match HYCOM.** All 321,168 keys present on both sides have the
   same size (to HYCOM's listing precision). Of 68 sampled files, all 47 that exist on both sides have identical exact sizes and
   identical HDF5 chunk offsets on both sides. No file on HYCOM was modified after it was
   copied.
3. **The archive is longer than in September.** A new experiment, **028**, runs from 2024-09-01
   19Z to 2026-07-09 (hourly) and 2026-08-31 (daily). It is not on data.hycom.org, so it came
   from another HYCOM source.
4. **Experiment 027 was not reprocessed, and 028 shares its layout.** Both have different
   chunking from 010–026 (see [Two layouts](#two-layouts)). That makes about 19,900 hours (and
   growing) in the second layout, not 3,672. **The store design needs a decision from Eli on this
   (D1).**
5. **028's 2d files have a different variable set:** wind stress instead of 10 m wind (D2).
6. **Years 2021, 2022 and 2023 are complete on S3**, all experiment 023, which has the 010
   layout. Any of them can be the "one full year" issue #11 waits for (D3). 2010, the year the
   audit suggested, is only copied to 2010-08-07.
7. **For the file team:** 9 truncated 028 files, a stalled copy for 2001–2020, and a few files
   to remove (see [For the file team](#for-the-file-team)).

## Inventory

Per experiment, hourly files on S3 (`03_compare.py`, `out/compare.txt`):

| Exp | Kind | On S3 | From | To (latest on S3) | Not yet on S3 (on HYCOM) |
|---|---|---|---|---|---|
| 010 | 2d | 100,133 | 2001-01-16 00Z | 2017-06-01 18Z | 43,406 |
| 010 | 3z | 99,840 | 2001-01-16 00Z | 2017-06-01 18Z | 43,676 |
| 023 | 2d | 45,487 | 2017-06-01 19Z | 2024-01-01 18Z | 12,233 |
| 023 | 3z | 45,462 | 2017-06-01 19Z | 2024-01-01 18Z | 12,258 |
| 026 | 2d / 3z | 2,837 each | 2024-01-01 19Z | 2024-04-28 23Z | 0 |
| 027 | 2d / 3z | 3,672 each | 2024-04-01 19Z | 2024-09-01 18Z | 0 |
| 028 | 2d | 12,639 | 2024-09-01 19Z | 2026-07-09 10Z | not on data.hycom.org |
| 028 | 3z | 12,614 | 2024-09-01 19Z | 2026-07-09 06Z | not on data.hycom.org |

**How the copy is going.** Each year directory 2001–2020 is filled in date order and stops
partway through the year (2010 at 2010-08-07, 2001 at 2001-09-23, and so on). All of them
stopped about 2026-11-16 18:16 UTC. 2021–2024 are complete, both kinds. 2025 is complete to
2025-08-04, and was the only year still being written on 11-17 and 11-18. 2026 runs to
2026-07-09, with five single 3z hours missing (2026-02-05 08Z, 03-13 07Z, 04-10 22Z, 04-20 12Z,
and 2025-08-02 01Z plus 05–09Z and 11Z).

**Daily means** (`data/daily_netcdf/YYYY/gomb1_daily_YYYY_DDD_{2d,3z}.nc`): 2001 day 17 to 2026
day 243 (2026-08-31). Every daily file on HYCOM is on S3; S3 also has the 028 dailies from
2024 day 245 on.

**Other objects:** `topo/regional.{grid,depth,mask}.nc` (NetCDF-3; 2-D `plon`/`plat`, `bathy`,
`mask` on the 1537 × 2101 grid) plus two zips; `config/blkdat.input` (the experiment 023 model
configuration); and an `index.html` S3 browser. data.hycom.org's `reanalysis/` page now serves
that same browser.

## Two layouts

| | 010, 023, 026 | 027, 028 |
|---|---|---|
| 2d chunk | {1, 1537, 2101}: whole map, 12.9 MB | {1, 769, 1051}: 2 × 2 tiles, 3.2 MB |
| 3z chunk | {1, 10, 385, 526}: 4 depth groups × 4 × 4 tiles, 8.1 MB | {1, 7, 308, 421}: 6 depth groups × 5 × 5 tiles, 3.6 MB |
| 3z chunks per variable per hour | 64 | 150 |
| `experiment` attribute | 01.0 | 02.3 (027), 02.8 (028) |
| 3z file size | 2,592,206,800 bytes (a few variants) | 2,723,178,743 bytes |

The 027 and 028 3z files have identical schemas *and* identical chunk byte offsets, so a single
header could almost serve both. The build still reads every file's header (offsets differ
by a few bytes among the 010–026 files; see the audit).

The two tilings share no boundaries (2101 = 4 × 526 − 3 = 5 × 421 − 4), so no virtual chunk
shape fits both. One Zarr array cannot change its chunk grid partway along time. So the
second layout has to be either rewritten (the September decision for 027) or kept apart in the
store.

Hours in the second layout, now: 3,672 (027) + 16,216 (028 span, 12.6 k copied) ≈ **19,900**,
about 9 % of the record. If HYCOM keeps extending 028, the share grows. Rewriting 027 + 028 3z
is roughly 54 TB (19,900 × 2.72 GB).

## 2d variables change at 028

| Experiments | 2d variables |
|---|---|
| 010, 023, 026, 027 | `ssh`, `mixed_layer_thickness`, `u_barotropic_velocity`, `v_barotropic_velocity`, `wnd_ewd`, `wnd_nwd` |
| 028 | `ssh`, `mixed_layer_thickness`, `u_barotropic_velocity`, `v_barotropic_velocity`, `surface_e_stress`, `surface_n_stress` |

027's `history` attribute shows how it got winds: HYCOM appended `wnd_ewd`/`wnd_nwd` from a
separate `wind.nc` with NCO and dropped `surface_e_stress`/`surface_n_stress` (September 2025).
028 has not had that step. The 3z variables are the same five throughout.

## Things HYCOM changed since September

- **17 hourly 3z files were renamed `*_CORRUPTED`, with no replacement:** 2002 day 139 (18, 20,
  21, 23Z), 2004 day 083 (12, 16, 18, 21Z), 2006 day 210 (00, 01, 03, 04, 05Z), 2006 day 268
  (01, 02, 04, 05Z). Those hours are now 3z gaps on HYCOM and on S3. They would have looked like
  good files in the September audit.
- **5 more 2002 3z files have a new copy dated 2026-11-10**, with the old one kept as
  `*_CORRUPTED`: day 046 (12, 16Z) and day 051 (06, 07, 09Z). S3 copied them on 11-14,
  after the new copies appeared, and its copies match HYCOM's current files at three 1 MiB
  samples each (`04_spot_bytes.py`). **But at those samples the `_CORRUPTED` copies are
  identical too**, so this check cannot tell old from new. Settling it needs a full-file
  comparison or HYCOM saying what was corrupted.
- The 16 stray `u.y2016_d3NN.nc` files are still on HYCOM, and were not copied. Good.

## For the file team

1. **Re-copy 9 truncated 028 files.** HDF5 refuses to open them ("truncated file"). Their
   sizes are multiples of 4 KiB, the mark of an interrupted transfer:
   `2024/028_archv.2024_298_19_2d.nc`, `2025/028_archv.2025_{100_04,101_18,102_19,103_03}_3z.nc`,
   `2026/028_archv.2026_{145_05,146_11,151_03,151_05}_3z.nc`.
2. **The 2001–2020 copy stopped** about 2026-11-16 18:16 UTC, partway through each year.
   About 111,600 hourly files are still to come.
3. **Remove, or never copy:** `2012/010_archv.2012_138_00_3z.nc_COPY` (copied), and the six empty
   3z files `2006/010_archv.2006_177_{18..23}_3z.nc` (copied, 49,818 bytes, zero time steps).
   The other 12 empty files were left out, as asked.
4. **Fill or confirm the five missing 2026 3z hours and the 2025-08-02 ones** listed above.
5. **Confirm what HYCOM means by `_CORRUPTED`** for the 2002 files with new copies, and whether
   the 17 removed hours will be regenerated.
6. Both 026 and 027 were copied for the 653 overlap hours (2024-04-01 19Z to 04-28 23Z). Fine
   for S3. The store picks one.

## Decisions for Eli

- **D1. Two layouts.** In September the plan was to reprocess 027. 028 now has the same
  layout and is 4–5 times larger. The options: reprocess 027 + 028 (about 54 TB of 3z, plus
  future 028 output); keep a second store, or a second group, for 2024-04 onward; or build
  010–026 only for now. The September decisions (no reprocessing of 010–026, 2d as whole maps)
  are not affected.
- **D2. 2d variables in 028.** Wind stress instead of 10 m wind. Wait for HYCOM to add winds
  as for 027, or carry both sets with NaN where absent?
- **D3. Test year for issue #11.** 2021, 2022 or 2023: each complete, experiment 023, same layout
  as 010. 2010 will not be complete until the stalled copy restarts.
- **D4. Static fields.** `topo/` has bathymetry and the land mask on the model grid, and could go
  in the store as 2-D variables.

## Scripts and outputs

Run from this directory with a Python ≥ 3.12 venv: `pip install -r requirements.txt`
(tested 2026-11-18 on Python 3.13).

| Script | What it does | Output |
|---|---|---|
| `01_inventories.py` | S3 ListObjectsV2 (anonymous) and the data.hycom.org Apache listings | `out/s3-listing.csv.gz`, `out/hycom-listing.csv.gz` |
| `02_sample_layouts.py` | HDF5 layout of 68 sample files on S3 and on HYCOM, compared | `out/sample-layouts.tsv` |
| `03_compare.py` | S3 vs HYCOM by key; HYCOM now vs September; exact sizes of odd files | `out/compare.txt`, `out/s3-vs-hycom.csv.gz` |
| `04_spot_bytes.py` | MD5 of three 1 MiB ranges, S3 vs HYCOM vs `_CORRUPTED` | `out/spot-bytes.txt` |

The HYCOM listing in `out/` was taken by a first version of `01_inventories.py` that fetched every
directory twice. It was deduplicated afterwards: the two copies of each key were identical.
The script is fixed. HYCOM is read one request at a time, as in the audit.
