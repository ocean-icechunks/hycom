# Handoff — hycom

Rolling state for this repo. Orientation only: the open threads below are a record of what is unfinished, not a
task list. Eli's cross-repo to-do list (not GOM) is [notes/todo.md](notes/todo.md).

## Where it stands (2026-11-21, Eli away about two weeks)

- **GOFS 3.1 reanalysis: done and published** (tag `v1`, viewer, docs mirrored). **CORS is now set on both HYCOM
  buckets** (2026-11-21, curl checks pass); the README caveat comes out once Eli sees the viewer work with the
  extension off. Also open: a performance section (#9).
- **GOMb0.01 / GOMe0.01: waiting on HYCOM.** Phase 1 (plan, smoke test, 2022 test year, scratch store) and gap
  filling (#22) are merged. Phase 2 (HYCOM's answers and Eli's decisions) is on branch **`gom-phase2-hycom-answers`**,
  pushed, no PR yet. Eli emailed HYCOM the chunk layouts on 2026-11-19; nothing can be built for production until
  the decisions under "What Eli decides when she is back" are made.
- Nothing is running. No store was written after 2026-11-19.

## GOMb0.01 / GOMe0.01 (#17)

A 2026 IOOS hackathon project:
[ocean-icechunks/2026-ioos-hackathon#22](https://github.com/ocean-icechunks/2026-ioos-hackathon/issues/22).
**Post each GOM prompt Eli writes to that issue, verbatim, before acting on it** (Prompts 1–51 are there).
Side questions stay out. Don't confuse it with ocean-icechunks/hycom#22 (gap filling).

**Read first:** [notes/plan-issue-17.md](notes/plan-issue-17.md) — "HYCOM's answers", "For the HYCOM team" (status of
items 1–13), "Scope" (decisions), "Still open". Gap filling: [notes/gapfill-22.md](notes/gapfill-22.md).

**Decided (Eli, 2026-11-19): two stores, one per HYCOM product.**
- **GOMb0.01** = experiments 010, 023, 026, 027; 2001-01-16 → 2024-09-01 18Z; GOFS 3.1 boundaries; `topo/` bathymetry;
  10 m winds. Layout A for 010/023/026, **layout B for 027**.
- **GOMe0.01** = 028 only; 2024-09-01 19Z → present, still running; ESPC-D-V02 boundaries; bathymetry changed near the
  boundaries (not on the bucket, item 12); wind stress instead of 10 m winds. Layout B throughout.
- **Why Eli waits on 027:** it belongs to GOMb0.01 but is chunked like GOMe0.01, and the two layouts cannot share a
  Zarr chunk grid. If HYCOM rewrites 027 in layout A, GOMb0.01 is one array. If not, it needs a second group, which
  Eli does not want. Full table and options: the plan's "Scope".

**Not decided (Eli, 2026-11-21): how 027 gets into GOMb0.01.** Her latest pitch to the team is to redo the
April–August 2024 (027) files in layout A, so GOMb0.01 is one array (HYCOM item 13); nobody has agreed yet. The
`026`/`027` groups with tags `v1`/`v2` were her working assumption on 2026-11-19, now only the fallback option (e).
HYCOM says 027 is authoritative for the 653 overlap hours. Options table: the plan's "Scope".

**Next step on the files (Eli, 2026-11-21): wait until HYCOM says everything is up on S3, then run another audit.**
HYCOM is sorting out corruption issues and resuming the transfer; Eli takes them to mean the 3z gaps (the 41 bad
hours included) will be filled. **`_CORRUPTED` files are never used.** The new audit sets the real gaps table.

**When HYCOM replies:** update the item status table in the plan (it does not record which of items 6–8, 12, 13 went
in Eli's email; ask her), then PR the branch.

**What Eli decides when she is back (open):**
- 027: redone in layout A (her pitch), or two groups, or another option in the plan's "Scope". Settles group names, releases and `END`.
- Production 3z chunking d for GOMb0.01 (d = 1 was chosen for the test store only), and d for GOMe0.01's 7-depth chunks.
- Production prefixes on Source Cooperative for the two stores.
- Gap filling: where reviewed fingerprints live; whether a replacement needs sign-off.
- The 2d latitude-band option (53-row bands, ~15 s vs 157 s for a one-year point series; virtual, no rewrite).
  Not acted on: it would reopen her September choice of whole maps.
- When to start GOMe0.01 (needs its own bathymetry/mask from HYCOM, item 12).

**GitHub issues out of date (suggested 2026-11-21, not done; Eli's call):** #15 and #16 were answered by HYCOM on
2026-11-19 and could get a summary comment and be closed. #17's title and "Decided" still say group `hourly` and
layout A only. #21's fix is confirmed for d = 1 over one year; still untested at d = 2/10 and over multiple years.

**Small code change waiting:** `HELD_BACK` in `gom_virtual.py` still excludes the five 2002 3z files HYCOM confirmed good.

**Facts most likely to be got wrong:**
- **The source `_FillValue` (1.267651e30) is not the land value (2**100).** The store declares 2**100 (R21). Never
  write the fill value as a decimal.
- **Names follow the GOM files** (`MT`, `Depth`, `Latitude`, `Longitude`, `Date`). `MT` is float64
  `days since 1900-12-31 00:00:00`, written as plain numbers, because xarray's datetime encoding shortens the units.
- **Scan in processes, not threads** (h5py's global lock). About 28 files/s at 16 processes on this hub.
- **`Latitude`/`Longitude` come from a 2d file.** The 3z longitude drifts from 2021 on (HYCOM item 8).
- **`2004/010_archv.2004_153_19_2d.nc` is chunked like layout B**, so it is skipped (a 2d gap).
- **A float `_FillValue` on a ManifestArray must be in xarray's base64 form**, or the store won't open (xarray 2026.9).
- **No Zarr chunk grid fits both layouts** (tile widths 526 vs 421, 421 prime) — that is why 027 as it is cannot join the layout A arrays.
  The product change (027 → 028) does not change the chunking; 028 has 1,611 fewer sea points than `topo/`.
- **The skeleton does not scale to the full record** (0.84 GB per year at d = 1). Production must create the empty
  arrays without manifests. Also check the final manifest size after snapshot expiry.
- **Build memory (#21):** `gc.collect()` per batch, `gv.build_config_override()` at open, never in `create`.
- **Reprocessing 027 is a question to HYCOM (item 13), not a decision.** "Reprocessing" was never decided in
  September either.

**Stores on test-repo (the team's; never write to them):** `test-repo/hycom/hycom-tsis-gom-reanalysis` (2022, group
`hourly`, d = 1), `test-repo/hycom/gapfill-test/store` and `…/with-gaps`. All are in the test viewer; Eli checked them.

**Older GOM notes, now history:** [notes/gomb0pt01-audit-2026-09.md](notes/gomb0pt01-audit-2026-09.md) (September audit,
#8), [notes/gom-s3-review-2026-11.md](notes/gom-s3-review-2026-11.md) (S3 review, PR #18). Both carry a banner.

## GOFS 3.1 reanalysis (#1, done 2026-09-19)

Tag `v1`, 10.45 M references from 63,341 NetCDF-3 files, validated from the public URL, viewer at
`ocean-icechunks/hycom/viewer/`. Docs are mirrored from merged `main` (dataset docs at
`hycom/docs/hycom-gofs-3pt1-reanalysis/`, collection README and LICENSE at `hycom/`); **re-mirror after any change**.
Notes, in reading order: [plan-issue-1.md](notes/plan-issue-1.md), [smoke-test-findings.md](notes/smoke-test-findings.md)
(things that look wrong and are deliberate), [production-build-2026-09-18.md](notes/production-build-2026-09-18.md).

- **Demo notebook** `hycom-gofs-3pt1-reanalysis/bering-sea-snow-crab-demo.ipynb` (Bering Sea bottom temperature and
  cold pool, 1994–2015; ~10 s in us-west-2; works on Colab). Eli called it "perfect. Short and clear and
  compelling": **the model for future demo notebooks.** Pitfall: `xr.concat` on the lazy store (`chunks=None`) reads
  everything and OOM'd the hub; `.load()` each side of the dateline first.
- README wording "a demonstration product **for** the HYCOM Consortium" is deliberate: Eli is not a member.
- **CORS: set by the HYCOM team on both buckets; curl checks passed 2026-11-21**
  ([notes/cors-request-hycom.md](notes/cors-request-hycom.md)). Next: Eli looks at the viewer with the extension OFF,
  then remove the "needs a CORS extension" text from both READMEs, `test-repo-README.md` and `publish_viewer.py`, and
  re-mirror.

Facts most likely to be got wrong:
- **Two header layouts, 40 bytes apart; file size, not experiment number, tells them apart.** Offsets come from each
  file's own header. A template (as the rsignell/hycom-kerchunk notebook does) misplaces data in 27,439 files.
- **Recommend `chunks=None`, select, then `.chunk()` — not `chunks={}`.** `chunks={}` gives 2.57 M dask chunks per 4-D
  variable: slow, not broken (10-day box mean 5 s / 0.45 GB vs 14 s / 1.6 GB). Specific to this chunk count.
- **The time axis is regular with 931 gaps left as NaN**; `tau` (NaN at gaps) is the presence indicator. A
  `has_data` flag was rejected as invented.

## Collection layout and working principles

- **This repo is a collection of HYCOM stores** laid out like `~/icechunks`: one directory per dataset, shared tooling
  at the root (`icechunk_utils.py`, `publish_viewer.py` with `DATASETS` and `TEST_ONLY`), a root README about the
  collection. On Source Cooperative: stores at `ocean-icechunks/hycom/<dataset>`, docs at `hycom/docs/<dataset>/`
  (never inside an Icechunk prefix). `hycom_virtual.py` (NetCDF-3) and `gom_virtual.py` (HDF5/h5py) stay
  dataset-specific; lift shared parts to the root only when it is clear what is shared.
- **Store READMEs use Eli's standard format** (title ending "— Icechunk", emoji navbar, fixed section order); this
  repo's READMEs are the reference copy. They carry the **"icechunk 1.x will not work" note** above the opening code
  (`http_storage` needs 2.0, `HttpAccess` 2.1, every 2.x needs Python >= 3.12).
- **One viewer per root**: `hycom/viewer/`, plus the scratch `test-repo/hycom/viewer/`. A new dataset is a catalog
  entry, never its own viewer. The `publish_viewer.py` copy here and the one in ocean-icechunks/icechunks are identical
  below `PRODUCTS`; keep them that way.
- **`~/gridlook` goes stale silently** (once 98 commits behind `eeholmes/gridlook`); `publish_viewer.py` refuses a stale
  checkout. **Never publish a viewer that falls back to gridlook's demo dataset**; `publish_viewer.py` injects a
  default hash.
- **A republished viewer looks unchanged until a hard reload** (Source Cooperative drops `Cache-Control`). Check with
  curl first, then tell Eli to Ctrl+Shift+R.
- **Hub specifics:** check which Python exists (September: `/srv/conda/bin/python3.12`; November:
  `/srv/conda/envs/notebook/bin/python3.13`). Build venvs in the scratchpad with `pip install --no-cache-dir` (`~` has
  a small quota). Clean-venv runs use each dataset's `requirements.txt`. Background jobs: use the tool's background
  mode, not `nohup … &`, and don't wait with `pgrep -f <name>`.
- **Source Cooperative login** goes through the hub proxy: `source-coop login --duration 1d --port 8400`, then open
  `https://nmfs-openscapes.2i2c.cloud/user/eeholmes/proxy/8400/`. CLI 0.3.0 at `~/.local/bin/source-coop`; after login
  `source-coop creds` renews keys itself, so multi-day runs work.
- No browser on the hub: verify transport (status, content type, CORS) here, and ask Eli whether it renders.

## Open threads (not GOM)

- **Issues:** #9 (GOFS 3.1 performance section, not started); #7 (Eli's scratch notes on GOMe0.01 at data.hycom.org —
  relevant again now that GOMe0.01 is a store); #20 (a file-audit script from the audit skill, plus what the team
  wants in it; not started).
- **PR #13 (Renovate)** is open; Eli is looking at it, don't touch it.
- **`icechunk-readme` skill** — Eli will do it later: [eeholmes/claude-config#4](https://github.com/eeholmes/claude-config/issues/4).
- **Offered, not taken up:** a NOAA disclaimer section for the root README; a viewer self-refresh check against
  `build-info.json`.
- Cross-repo items (cefi and globcolour README notes, OISST README after noaa_oisst#2 was fixed, skill Learn pass,
  gridlook default dataset, VirtualiZarr dtype report): [notes/todo.md](notes/todo.md).
