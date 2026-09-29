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

## Second dataset: GOMb0.01 reanalysis (2026-09-26)

**HYCOM-TSIS GOMb0.01, the 1/100° Gulf of Mexico hourly reanalysis**, is the second store.
Issue #8 asked whether its NetCDF-4 files need reprocessing first. The audit is merged (PR #10; #8 closed, branch deleted):
`hycom-tsis-gom-reanalysis/audit/report.md`. In short: the files are good as they are, except
experiment 027, which the file team will reprocess. 2d will use whole 12.9 MB maps. The 3z
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
  Reuse and citation / Credits. Reference copy: `ocean-icechunks/noaa-ohc/README.md`. Applies
  to the root README and the test-repo README too. Also saved as a project memory.
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
- The kernel env is Python 3.11 and cannot install icechunk 2.x. Build a 3.12 venv in the
  scratchpad with `/srv/conda/bin/python3.12 -m venv` and `pip install --no-cache-dir`
  (`~` has a small quota; pip's cache fills it).
- Conventions for README, `requirements.txt`, notebooks-as-build-log, mirroring and the
  gridlook viewer follow `~/icechunks` (its `CLAUDE.md` and `claude/notes/`).
- **Source Cooperative login** goes through the hub proxy. Run
  `~/.cargo/bin/source-coop login --duration 1d --port 8400`, then open
  `https://nmfs-openscapes.2i2c.cloud/user/eeholmes/proxy/8400/` in a browser. The hub's
  hostname is in no environment variable; it was inferred from the scratch bucket name
  (`nmfs-openscapes-scratch`) and confirmed by Eli using it.
- No browser on the hub: verify transport (status, content type, CORS) here, and ask Eli
  whether it renders.

## Open threads

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
  `~/agent-skills/claude/notes/inbound-from-hycom-2026-09.md` (pushed there 2026-09-19).
