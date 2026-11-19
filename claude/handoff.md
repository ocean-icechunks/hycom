# Handoff — hycom

Rolling state for this repo. Orientation only: the open threads below are a record of what
is unfinished, not a task list. **Eli's own to-do list, written as they signed off on
2026-09-19, is [notes/todo.md](notes/todo.md)** — it spans the sibling repos too.

## Demo notebook for GOFS 3.1 (2026-09-29)

`hycom-gofs-3pt1-reanalysis/bering-sea-snow-crab-demo.ipynb` is on `main` (commit 25324b3).
Eli wrote it for a Colab demo and called it "perfect. Short and clear and compelling", so use
it as the model for future demo notebooks. It maps Bering Sea `water_temp_bottom` and
plots mid-July bottom temperature and cold-pool (< 2 °C) fraction, 1994–2015, over the
snow crab box 57–61°N, 165–173°W. It takes about 10 s in us-west-2, and Eli confirmed it
works on Colab (2026-09-29). The cold years are 1999 and 2007–2012; the warm ones are 2001–05 and 2014–15.

- **READMEs:** Eli's shorter collection and GOFS READMEs, plus the `### Example notebook`
  link, were merged in PR #12 on 2026-09-29 and mirrored to Source Cooperative the same
  day. The served copies match `main`. Links to dataset READMEs go to Source Cooperative, not
  GitHub. The wording "a demonstration product **for** the HYCOM Consortium" is deliberate:
  Eli is not a member.
- **Pitfall:** `xr.concat` on this lazy store (`chunks=None`) reads everything. It OOM'd
  the hub, so `.load()` each side of the dateline before joining them.
- **The GOBAI-O2 version is finished:** `GOBAI-O2/gobai-o2-oxygen-niche-demo.ipynb` in
  nmfs-opensci/gobai-rfrom-icechunks (issue #36, PR #37 merged 2026-09-29). GOBAI HR has
  **no data on the Bering shelf**, so it can't show bottom O₂ on the crab grounds. It shows
  the oxygen-niche depth instead (first level with O₂ < 60 µmol kg⁻¹), weekly for
  1993–2025, over the Aleutian Basin. The niche is about 70 m shallower since 2016. The
  notebook runs in 67 s from the hub.
- **Both demo notebooks work on Colab**, as Eli confirmed on 2026-09-29.

## GOMb0.01 / GOMe0.01 (#17): phase 1 done, gap filling (#22) done; phase 2 waiting on HYCOM (2026-11-19)

GOM work is a 2026 IOOS hackathon project,
[ocean-icechunks/2026-ioos-hackathon#22](https://github.com/ocean-icechunks/2026-ioos-hackathon/issues/22).
**Post each GOM prompt Eli writes to that issue, verbatim, before acting on it** (Prompts 1–51 are
there; find the last N from the comments). Side questions stay out. "Notes:" comments summarise results for the
team (the last one, 2026-11-19, summarises phase 1). Don't confuse it with ocean-icechunks/hycom#22 (gap filling).

**Where it stands: waiting on HYCOM's reply.** Eli emailed them the two chunk layouts on 2026-11-19 and will come back
when they answer. Read first: [notes/plan-issue-17.md](notes/plan-issue-17.md), "HYCOM's answers" and "For the
HYCOM team" (a status per item, 1–13), then "Scope".

- **Branch `gom-phase2-hycom-answers`** (pushed, **no PR yet**) holds all of phase 2: HYCOM's answers of 2026-11-19, the
  decisions below, HYCOM items 12–13, and the gap-filling summary in the plan. When HYCOM replies, update the status
  table (it does not record which of items 6–8, 12, 13 went in Eli's email; ask her), then PR.
- **Decided (Eli, 2026-11-19):** two stores, **GOMb0.01** (010/023/026/027, to 2024-09-01 18Z) and **GOMe0.01** (028,
  still running). GOMb0.01 has groups **`026`** (all of layout A, 010/023/026 included) and **`027`**. Tag **`v1`** = the
  `026` group to 2024-04-28 23Z (the current `END`; the 653 overlap hours from 026); **`v2`** adds `027`. HYCOM says 027
  is authoritative for the overlap, so the v2 README must say so. Groups are a workaround Eli dislikes: she asked HYCOM
  about rechunking 027 to layout A (item 13). Her idea for afterwards, an option only: a `best` group plus a `026` group
  of the superseded hours.
- **HYCOM's answers (2026-11-19):** the five regenerated 2002 3z files are good (`HELD_BACK` in `gom_virtual.py` is
  still to remove); the 41 missing 3z hours and the 028 truncated/missing files will be regenerated (slow: Navy archive
  maintenance); no 10 m winds for 028 (#16 answered); item 1 and the 028 layout question go to Michael McDonald.
- **Measured 2026-11-19:** the product change does not change the chunking (027 is already layout B, and 027 → 028 has
  the same grid and chunks). 028 has 1,611 fewer sea points than `topo/`, which holds only GOMb0.01's topography
  (item 12). No Zarr chunk grid fits both layouts (tile widths 526 vs 421), which is why 027 needs its own group.
- **Not acted on, Eli's call:** 53-row latitude bands for 2d (virtual, no rewrite; ~15 s vs 157 s measured for a
  one-year point series). It would reopen her September choice of whole maps.
- **Gap filling (#22) is merged** (PR #25, issue closed, branch deleted): `check_fill_candidates` and `fill_hours` in
  `gom_virtual.py`; [notes/gapfill-22.md](notes/gapfill-22.md). Test stores `test-repo/hycom/gapfill-test/store`
  (filled) and `…/with-gaps` (never filled), both in the test viewer; **Eli confirmed gaps show as no data**. Open
  for Eli: where reviewed fingerprints live; sign-off for replacement fills.
- **Phase 1 (merged, PR #23):** code `hycom-tsis-gom-reanalysis/gom_virtual.py`, smoke test `gom-smoke-test-local.ipynb`,
  scripts `notes/issue-17-research/`. The 2022 scratch store `test-repo/hycom/hycom-tsis-gom-reanalysis` (group
  `hourly`, d = 1, Eli's choice for the test store only) is in the test viewer and is the team's: never write to it.
  #21 (build memory) is fixed: `gc.collect()` per batch, `gv.build_config_override()` at open, never in `create`.
- Skill lessons: ocean-icechunks/ocean-icechunks-skills#20 (its file links still point at a deleted branch; Eli wants to
  be asked before they are fixed). **PR #13 (Renovate)** is open; Eli is looking at it, don't touch it.

**Facts most likely to be got wrong:**
- **The source `_FillValue` (1.267651e30) is not the land value (2**100).** The store declares 2**100 (R21). Never write
  the fill value as a decimal.
- **Names follow the GOM files** (`MT`, `Depth`, `Latitude`, `Longitude`, `Date`). `MT` is float64
  `days since 1900-12-31 00:00:00`, written as plain numbers, because xarray's datetime encoding shortens the units.
- **Scan in processes, not threads** (h5py's global lock). About 28 files/s at 16 processes on this hub.
- **`Latitude`/`Longitude` come from a 2d file.** The 3z longitude drifts from 2021 on (HYCOM item 8).
- **`2004/010_archv.2004_153_19_2d.nc` is chunked like layout B**, so it is skipped (a 2d gap).
- **A float `_FillValue` on a ManifestArray must be in xarray's base64 form**, or the store won't open (xarray 2026.9).
- **The skeleton does not scale to the full record** (0.84 GB per year at d = 1). Production must create the empty
  arrays without manifests. Also check the final manifest size after snapshot expiry.
- **Reprocessing 027 is a question to HYCOM (item 13), not a decision.** Layout B is #15; the 028 winds (#16) are answered: no.

**Hub notes:** a `nohup … &` process started in one shell call is invisible to `ps` in later calls, and is killed when
its call ends if the call waits. Use the tool's background mode, and don't wait with `pgrep -f <name>`, which matches
the waiting loop itself. The test venv used for every clean-venv run is in the session scratchpad. Rebuild it
from `hycom-tsis-gom-reanalysis/requirements.txt` with `/srv/conda/envs/notebook/bin/python3.13 -m venv`.

S3 file review, merged 2026-11-18 (PR #18): `hycom-tsis-gom-reanalysis/s3-review/report.md`, notes in
[notes/gom-s3-review-2026-11.md](notes/gom-s3-review-2026-11.md).

## Second dataset: GOMb0.01 reanalysis (2026-09-26)

**HYCOM-TSIS GOMb0.01, the 1/100° Gulf of Mexico hourly reanalysis**, is the second store.
Issue #8 asked whether its NetCDF-4 files need reprocessing first. The audit is merged (PR #10; #8 closed, branch deleted):
`hycom-tsis-gom-reanalysis/audit/report.md`. In short: the files are good as they are. 027 (and now 028) has a different chunk
layout, and how to handle that is open (#15). Reprocessing 027 was never decided; it was
brainstorming, and HYCOM was not involved (Eli, 2026-11-18). 2d will use whole 12.9 MB maps. The 3z
chunking is open.

**Next step for us: when one year of hourly files is on S3**, decide the 3z chunking and run
performance tests. That task is issue #11, which carries the chunking options and build facts. Copying the files to S3 (planned bucket `hycom-tsis-gom-reanalysis`) is
another team's job, not ours. Until they have a year there, nothing is ours to do. Eli's
decisions, the test plan, and the facts most likely to be got wrong are in
[notes/gomb0pt01-audit-2026-09.md](notes/gomb0pt01-audit-2026-09.md).

## Where things stand (2026-09-19)

**This repo is a collection: GOFS 3.1 reanalysis is the first of several HYCOM stores Eli
plans** (said 2026-09-19). So it is laid out like `~/icechunks`: one directory per dataset
(`hycom-gofs-3pt1-reanalysis/` holds that dataset's README, notebooks, `hycom_virtual.py`,
`requirements.txt` and manifests), shared tooling at the root (`icechunk_utils.py`,
`publish_viewer.py` with a `DATASETS` table), and a root README about the collection. Do not
write root-level docs as if they were about one dataset. On Source Cooperative the stores sit
at `ocean-icechunks/hycom/<dataset>`, one viewer at `hycom/viewer/` serves them all, and each
dataset's docs mirror to `hycom/docs/<dataset>/` — never into an Icechunk prefix.
`hycom_virtual.py` is deliberately still dataset-specific; lift the generic parts (the
NetCDF-3 header parser, the scan) to the root when a second dataset shows what is shared.

Issue #1 asked for the first one: the GOFS 3.1 reanalysis on AWS Open Data (63,341
uncompressed NetCDF-3 files, 305.8 TB), with tests going to `ocean-icechunks/test-repo/hycom`.

**The store is built** (2026-09-18): tag `v1`, 10.45 M references from 63,341 files, validated
from the public URL, with a gridlook viewer at `ocean-icechunks/hycom/viewer/`. Everything is
merged to `main` in PR #2 (2026-09-19): `hycom_virtual.py`, the production notebook
`hycom-icechunk-sc.ipynb`, two smoke-test notebooks, `publish_viewer.py`, `requirements.txt`.
The docs are mirrored from merged `main` and checked by checksum: dataset docs at `hycom/docs/hycom-gofs-3pt1-reanalysis/`, collection README and LICENSE at
`hycom/`. Re-mirror after any change to them. Issue #1 is closed and the branch deleted
(2026-09-19). PRs #2–#6 are merged and their branches deleted: #2 the build, #3 README
format and viewer default, #4 the stale-gridlook guard, #5 the "icechunk 1.x will not work"
README note. The docs were last mirrored after #5.

Notes, in reading order: [notes/plan-issue-1.md](notes/plan-issue-1.md) (measurements and
every decision Eli made), [notes/smoke-test-findings.md](notes/smoke-test-findings.md)
(things in the code that look wrong and are deliberate),
[notes/production-build-2026-09-18.md](notes/production-build-2026-09-18.md) (the build, and
what `chunks={}` costs on this store). Research scripts are in
`notes/issue-1-research/`.

The three facts most likely to be got wrong:

- **There are two header layouts, 40 bytes apart, and file size — not experiment number —
  tells them apart.** Offsets must come from each file's own header. Reusing one file's
  offsets as a template (as the rsignell/hycom-kerchunk notebook does) misplaces data in
  27,439 files.
- **Recommend `chunks=None`, select, then `.chunk()` — not `chunks={}`.** With `chunks={}`
  each 4-D variable is 2.57 million dask chunks, and every operation costs seconds and about
  1 GB before data moves. It is slow, not broken: an early note here said "never", which Eli
  questioned and measurement softened (10-day box mean: 5 s / 0.45 GB select-then-chunk,
  14 s / 1.6 GB with `chunks={}`, and `chunks=None` with no `.chunk()` loads everything
  selected). This contradicts the skill's general advice and is specific to this chunk count.
- **The time axis is deliberately regular with 931 gaps left as NaN**, and `tau` (NaN at
  gaps) is the presence indicator. A `has_data` flag was considered and rejected as
  invented.

## Working principles

- **READMEs carry the "icechunk 1.x will not work" note** directly above the opening code:
  `icechunk.http_storage` arrived in 2.0 and `credentials.HttpAccess` in 2.1 (measured by
  installing 1.1.21, 2.0.1, 2.1.0), and every 2.x needs Python >= 3.12.
- **Store READMEs use Eli's standard format** (PR #3): title ending "— Icechunk", the emoji
  navbar, then View it in a browser / How to open it / About the data / How this was built /
  Reuse and citation / Credits. **Reference copy is now this repo's own READMEs** (root and
  GOFS 3.1), not noaa-ohc (Eli, 2026-09-29). Applies to the root README and the test-repo
  README too. Also saved as a project memory.
- **One viewer per root, and every dataset is a catalog entry in it** (Eli, 2026-09-19): the
  published one at `hycom/viewer/`, plus the scratch copy at `test-repo/hycom/viewer/` that
  the always-a-viewer-for-tests rule calls for. Never a viewer per dataset. A new dataset is
  one line in `DATASETS` in `publish_viewer.py`.
- **`~/gridlook` is a per-machine clone and goes stale silently.** On 2026-09-18 the viewer was
  built from a clone 98 commits behind `eeholmes/gridlook`, missing Eli's log10 transform,
  swatch fix and CORS pop-up (that work was done on another hub). `publish_viewer.py` now
  fetches and refuses a stale checkout (PR #4, merged). `~/gridlook-xl` is old and irrelevant. This
  hub has no Node 24 (gridlook asks for >= 24.16); the build works on Node 20.19.
- **Never link or publish a viewer that falls back to gridlook's demo dataset.** gridlook
  hard-codes an OGS Mediterranean store as its default for URLs with no `#…` fragment;
  `publish_viewer.py` injects a default-hash script into the published `index.html` so a bare
  link opens HYCOM. Confirmed by Eli in a browser, 2026-09-19. The noaa-ohc,
  oa-indicators and gobai-o2 viewers got the same two fixes and a rebuild from `b3c42b1` on
  2026-09-19 (ocean-icechunks/icechunks#28, merged).
- **A republished viewer looks unchanged until a hard reload.** Source Cooperative drops the
  `Cache-Control: no-cache` uploaded with `index.html` and sends only `Last-Modified`, so
  browsers cache the page heuristically, and the JS is served `max-age=14400`. Check the
  server with curl before believing "the update isn't there"; tell Eli to Ctrl+Shift+R. A
  self-refresh check against `build-info.json` was offered and not taken up.

- Follow the `virtual-icechunk` skill's order: plan → smoke test → production → docs. The
  plan is reviewed; the smoke test is next.
- **Hub images differ; check which Python you have.** In September the kernel was Python 3.11,
  and the venv was built with `/srv/conda/bin/python3.12 -m venv`. On 2026-11-18 the kernel env
  was Python 3.13 with icechunk 2.3.1 already installed, and no `python3.12` existed, so the venv
  was built with `/srv/conda/envs/notebook/bin/python3.13 -m venv`. Either way, build the venv in
  the scratchpad and use `pip install --no-cache-dir` (`~` has a small quota; pip's cache fills it).
- Conventions for README, `requirements.txt`, notebooks-as-build-log, mirroring and the
  gridlook viewer follow `~/icechunks` (its `CLAUDE.md` and `claude/notes/`).
- **Source Cooperative login** goes through the hub proxy. Run
  `source-coop login --duration 1d --port 8400`, then open
  `https://nmfs-openscapes.2i2c.cloud/user/eeholmes/proxy/8400/` in a browser. The CLI is
  0.3.0, at `~/.local/bin/source-coop` on this hub. After login, `source-coop creds` renews the
  keys itself, so multi-day runs work (see notes/gom-s3-review-2026-11.md). The hub's
  hostname is in no environment variable; it was inferred from the scratch bucket name
  (`nmfs-openscapes-scratch`) and confirmed by Eli using it.
- No browser on the hub: verify transport (status, content type, CORS) here, and ask Eli
  whether it renders.

## Open threads

- **`icechunk-readme` skill planned (Eli will do it later; not a task for now):**
  [eeholmes/claude-config#4](https://github.com/eeholmes/claude-config/issues/4). A personal
  skill that creates, updates (asking which ones first), and QC-checks store READMEs in any
  repo, modelled on the HYCOM READMEs. It uses one README per data product (groups such as
  CEFI's get none), no per-variable viewer table, no wrapper function in the open code, and
  a standard performance table. The full spec is in the issue.
- PR #6 (per-store `variables` in `publish_viewer.py`, ported from ocean-icechunks/icechunks)
  merged 2026-09-19. The two copies are identical below `PRODUCTS`; keep them that way.
- **The CORS request to help@hycom.org is drafted, not sent**:
  [notes/cors-request-hycom.md](notes/cors-request-hycom.md). Eli sends it, after checking the
  sentence about egress being covered by AWS's open-data sponsorship, which was not verified
  for this bucket. When the bucket gets a policy: run the curl checks in that note, have Eli
  look with the extension OFF, then remove the "needs a CORS extension" text from both READMEs
  and `publish_viewer.py` and re-mirror.
- The Medium citation in both READMEs is confirmed: Eli checked the title and year (2024).
- **Offered, not taken up:** the NOAA disclaimer section for the root README; a self-refresh
  check in published viewers against `build-info.json` (see the caching principle above).
- **`globcolour-Icechunks` and `cefi-icechunks` did not get the "icechunk 1.x will not work"
  README note.** globcolour's `http_storage` code exists only in Eli's uncommitted working
  copy; cefi is in the `noaa-nwfsc` org, whose SAML SSO the GitHub CLI token is not
  authorized for (`gh auth refresh -h github.com`, approve the org). cefi's README also still
  authorizes with the deprecated `{prefix: None}`.
- **Next HYCOM datasets**: GOMb0.01 is the second (above). No third chosen yet. Eli said this is the first of several. Start
  from the plan→local smoke test→scratch test (with viewer and README)→production order in
  the `virtual-icechunk` skill; add the store to `DATASETS` in `publish_viewer.py`; lift the
  generic parts of `hycom_virtual.py` (header parser, scan, `check_scan`) to the root when
  the second dataset shows what is really shared. GOMb0.01 is NetCDF-4/HDF5, not NetCDF-3, so
  the NetCDF-3 header parser is not shared; its audit reads offsets with h5py
  (`hycom-tsis-gom-reanalysis/audit/common.py`).
- Lessons from this build that the skill does not have yet are written up in
  `~/agent-skills/claude/notes/inbound-from-hycom-2026-09.md` (pushed there 2026-09-19). Since the
  skill moved on 2026-11-13 it is `docs/design/inbound-from-hycom-2026-09.md` in
  ocean-icechunks/ocean-icechunks-skills (`~/ocean-icechunks-skills`).
