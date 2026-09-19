# Handoff — hycom

Rolling state for this repo. Orientation only: the open threads below are a record of what
is unfinished, not a task list.

## Where things stand (2026-09-18)

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
The docs were mirrored from merged `main` on 2026-09-19 (again after PR #3) and checked by
checksum:
dataset docs at `hycom/docs/hycom-gofs-3pt1-reanalysis/`, collection README and LICENSE at
`hycom/`. Re-mirror after any change to them. Issue #1 is closed and the branch deleted
(2026-09-19). PRs #2–#5 are merged and their branches deleted: #2 the build, #3 README
format and viewer default, #4 the stale-gridlook guard, #5 the "icechunk 1.x will not work"
README note. The docs were last mirrored after #5.

Notes, in reading order: [notes/plan-issue-1.md](notes/plan-issue-1.md) (measurements and
every decision Eli made), [notes/smoke-test-findings.md](notes/smoke-test-findings.md)
(things in the code that look wrong and are deliberate),
[notes/production-build-2026-09-18.md](notes/production-build-2026-09-18.md) (the build, and
why `chunks={}` must not be used on this store). Research scripts are in
`notes/issue-1-research/`.

The three facts most likely to be got wrong:

- **There are two header layouts, 40 bytes apart, and file size — not experiment number —
  tells them apart.** Offsets must come from each file's own header. Reusing one file's
  offsets as a template (as the rsignell/hycom-kerchunk notebook does) misplaces data in
  27,439 files.
- **Open the store with `chunks=None`, never `chunks={}`** — 2.57 million dask chunks per 4-D
  variable. This contradicts the skill's general advice and is specific to this store's size.
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

- **PR #6 is open, unmerged** (2026-09-19): ports per-store `variables` from
  ocean-icechunks/icechunks' copy of `publish_viewer.py` and fixes a stale `fish-pace` URL in
  its docstring. No republish needed. The two copies are otherwise identical below
  `PRODUCTS`; keep them that way.
- **The CORS request to help@hycom.org is drafted, not sent**:
  [notes/cors-request-hycom.md](notes/cors-request-hycom.md). Eli sends it, after checking the
  sentence about egress being covered by AWS's open-data sponsorship, which was not verified
  for this bucket. When the bucket gets a policy: run the curl checks in that note, have Eli
  look with the extension OFF, then remove the "needs a CORS extension" text from both READMEs
  and `publish_viewer.py` and re-mirror.
- **The Medium citation is unverified.** Title and year (2024) of Rich Signell's Pangeo post
  in both READMEs came from the URL slug, memory and his repo's date; Medium 403s automated
  fetches. Eli was asked to confirm and has not.
- **Offered, not taken up:** the NOAA disclaimer section for the root README; a self-refresh
  check in published viewers against `build-info.json` (see the caching principle above).
- **`globcolour-Icechunks` and `cefi-icechunks` did not get the "icechunk 1.x will not work"
  README note.** globcolour's `http_storage` code exists only in Eli's uncommitted working
  copy; cefi is in the `noaa-nwfsc` org, whose SAML SSO the GitHub CLI token is not
  authorized for (`gh auth refresh -h github.com`, approve the org). cefi's README also still
  authorizes with the deprecated `{prefix: None}`.
- **Next HYCOM datasets**: nothing chosen yet. Eli said this is the first of several. Start
  from the plan→local smoke test→scratch test (with viewer and README)→production order in
  the `virtual-icechunk` skill; add the store to `DATASETS` in `publish_viewer.py`; lift the
  generic parts of `hycom_virtual.py` (header parser, scan, `check_scan`) to the root when
  the second dataset shows what is really shared.
- Lessons from this build that the skill does not have yet are written up in
  `~/agent-skills/claude/notes/inbound-from-hycom-2026-09.md` (pushed there 2026-09-19).
