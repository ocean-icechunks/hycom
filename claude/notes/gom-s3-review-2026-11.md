# GOMb0.01 on S3 — file review (2026-11-18) and the hackathon project

The findings are in `hycom-tsis-gom-reanalysis/s3-review/report.md`. This note records what the
report does not: how the work is tracked, and what the next session must not get wrong.

## How this work is tracked

- **Project issue: [ocean-icechunks/2026-ioos-hackathon#22](https://github.com/ocean-icechunks/2026-ioos-hackathon/issues/22)**
  ("Project: HYCOM GOM", with Michael McDonald). Eli asked (2026-11-18) that **every prompt
  she writes in this work is posted to that issue** as a comment, quoted verbatim, numbered
  "Prompt N". Prompt 1 is there. The code and notes stay in this repo (ocean-icechunks/hycom).
- Issue #11 in this repo (3z chunking and performance tests) is the store-design task this
  review feeds. It was waiting for "one year on S3". That condition is now met by 2021–2023.

## Status (2026-11-18)

- The bucket exists, is public, and is in us-west-2. The copy, by the file team, was still in
  progress: 2001–2020 stalled partway through each year about 2026-11-16 18:16 UTC, and only 2025 was
  still moving. Re-list before trusting any count in the report.
- **Open decisions for Eli, D1–D4 in the report.** The big one is D1: 027 was *not*
  reprocessed, and the new experiment 028 (2024-09 to 2026-07, not on data.hycom.org) has 027's
  layout. Do not assume the September "reprocess 027" plan still holds; ask.

## Facts easy to get wrong

- **The September audit's file list is out of date.** HYCOM renamed 17 hourly 3z files
  `*_CORRUPTED` since then, with no replacement, and wrote new copies of 5 more. The
  experiment-028 files exist only on S3 (and on whatever HYCOM source the file team used).
- **027 + 028 share one layout, down to identical 3z chunk offsets**, but the build must still
  read each file's header.
- **028 2d has wind stress (Pa, ocean points only), not 10 m wind (m/s, every point): missing, not
  renamed** (checked against hycom.org's variable list and by values). 027 got its winds from an NCO post-processing step
  (see its `history` attribute).
- **The `_CORRUPTED` spot check is inconclusive**: at three 1 MiB ranges per file, old, new and the S3
  copy were identical. Do not report the S3 copies of those 5 files as verified.
- **HYCOM's Apache index links every directory twice.** Deduplicate any list of directories
  scraped from it (`01_inventories.py` does now).

## Environment on this hub

- This hub's image is not the September one: the kernel is Python 3.13 and there is no
  `/srv/conda/bin/python3.12`. The venv was made with
  `/srv/conda/envs/notebook/bin/python3.13 -m venv` in the scratchpad, then
  `pip install --no-cache-dir -r hycom-tsis-gom-reanalysis/s3-review/requirements.txt`.
  Memory cap 3.9 GB.
- The `topo/*.nc` files are NetCDF-3 and need `scipy` (or netCDF4) to open with xarray. That is
  not in requirements.txt, because no script reads them yet.

## Does VirtualiZarr's variable-chunk work solve D1? (checked 2026-11-18)

Eli asked. **No, not as it stands, and not within the next releases.** What is being built:
rectilinear chunk grids (zarr-python#3802 merged 2026-04; xarray#11592 read-only, merged
2026-09; VirtualiZarr#954 still open, tests not written; tracking issue VirtualiZarr#12).

- A rectilinear grid gives each *axis* its own list of chunk lengths. The grid is still a
  Cartesian product, so lat/lon boundaries are the same at every time step. Our problem is
  that the spatial tiling changes at 2024-04 (4 × 4 tiles of 385 × 526 → 5 × 5 of 308 × 421,
  depth groups of 10 → 7). A per-axis grid cannot say "different tiles after time T".
- A common refinement of both tilings would be a valid rectilinear grid. But it needs splits
  in longitude inside a tile, and a tile's column window is not one contiguous byte range. The
  proposed `records` codec (VirtualiZarr#1147) could express a strided range. Codecs are per
  array, though, and the two layouts need different strides (526 vs 421 floats per row).
- The padded edge tiles add a further block (VirtualiZarr#1111, zarr-extensions#74).
- What would solve it is an array defined as a concatenation of differently chunked arrays:
  zarr-specs#288 (open since 2024), zarr-python#2536, VirtualiZarr#5. This is a proposal only; there is
  no implementation to use.

So D1 is still: reprocess 027 + 028, or keep the second layout in its own store or group (a
reader concatenates in xarray, and that can be replaced by one array if #288 lands).
