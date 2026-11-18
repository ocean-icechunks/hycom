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
- **028 2d has wind stress, not 10 m wind.** 027 got its winds by an NCO post-processing step
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
