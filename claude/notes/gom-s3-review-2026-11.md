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
- **Open decisions for Eli, D1–D4 in the report.** The big one is D1 (#15): 027 and the new
  experiment 028 (2024-09 to 2026-07, not on data.hycom.org) share a second chunk layout.
  **There was never a plan to reprocess 027.** That was Eli brainstorming, and HYCOM was not
  involved (Eli, 2026-11-18). Keep the September audit out of #15.

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

So D1 is still: rewrite 027 + 028, keep the second layout in its own store or group (a
reader concatenates in xarray, and that can be replaced by one array if #288 lands).

## Next: layout A store, starting with a 2022 test (Eli's answers, 2026-11-18)

Eli's plan: **build layout A** (010, 023, 026; 2001-01-16 → 2024-04-28) now. If the team decides to
rewrite 027/028 to layout A (#15), append those hours to it later.

- **Test year: 2022** (complete on S3, experiment 023, layout A). It is used to pick the 3z
  virtual chunking (10/5/2/1 depths per chunk) and to measure build cost (#11).
- **Next work: the smoke test, then a test store on Source Cooperative under
  `ocean-icechunks/test-repo/hycom/`** for the team to look at. It gets a viewer and README, as
  every test-repo store does. Eli expects it to raise more questions.
- **Time axis:** regular hourly from 2001-01-16 00Z. Gaps (empty 3z files, the 17 `_CORRUPTED` hours,
  anything not yet copied) are left as NaN; HYCOM will probably fill them in later, as new commits.
- **Full build waits** for the S3 copy. Eli is asking HYCOM when the 2001–2020 files will be
  added, and about the 5 regenerated 2002 files (D5 in the review): leave them out until HYCOM answers.
- **Group: `hourly`** (Eli, 2026-11-18). If layout B ends up as a separate group (#15), she may
  rename it, e.g. to `2001-04-2024`, so don't build anything that hard-codes the path more than it
  has to. Renaming works: Groups can be renamed later:
  Icechunk 2.3.1 `repo.rearrange_session("main").move("/a", "/b")` is metadata-only (tested with a
  virtual array: new path reads, old snapshots keep the old path). An ordinary writable session
  refuses `move`. Renaming still breaks README code and links that use the old path.
- **Build machines (Eli offered several VMs):** Eli asked what is needed; the answer so far is an estimate to confirm on 2022.
  Probably one VM in **us-west-2** (the bucket's region) is enough. GOFS wrote 10.45 M refs in
  about 2 min and scanned 63 k headers in 75 s at 128 threads. Layout A needs about 1.45 M
  header reads (1 per 2d file, 6 per 3z file), about 30 min at that rate. At 1 depth per chunk it
  is about 28 M refs per year, so write in monthly batches to bound memory, with manifests split along time.
  Parallel VMs are possible with Icechunk `session.fork()`/`merge()`, but probably not needed.
  The 3.9 GB hub is too small to be sure of a full year in one batch.

- **Source Cooperative credentials renew themselves** (Eli, 2026-11-18; she runs multi-day jobs
  this way in ~/pacioos). source-coop CLI **0.3.0**, at `~/.local/bin/source-coop` on this hub
  (not `~/.cargo/bin` as older notes say), logs in with `offline_access` by default. After that,
  `source-coop creds` refreshes expired keys without a browser. `icechunk_utils.get_source_credentials()`
  calls `source-coop creds`, so a long build just reopens the repo, or refreshes its credentials,
  per batch. For rclone/AWS tools: a profile with `credential_process = source-coop creds`
  (see ~/pacioos/upload/upload_to_source_coop.sh).
