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
The docs were mirrored from merged `main` on 2026-09-19 and checked by checksum:
dataset docs at `hycom/docs/hycom-gofs-3pt1-reanalysis/`, collection README and LICENSE at
`hycom/`. Re-mirror after any change to them. Issue #1 is closed and the branch deleted
(2026-09-19); `main` is the only branch.

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

- Open the PR; after merge, mirror the docs (`RUN_MIRROR = True`). Eli has confirmed `tau`/`experiment` stay auxiliary coordinates.
- Eli has seen the test viewer render (with a CORS extension); the production viewer is
  published and not yet looked at.
- Source bucket has no CORS. The request to help@hycom.org is drafted, not sent, in
  [notes/cors-request-hycom.md](notes/cors-request-hycom.md), with the S3 policy and the curl
  checks to run afterwards. Eli sends it.
- Two things worth feeding back to the `virtual-icechunk` skill: `to_icechunk` has no
  `encoding=` argument in VirtualiZarr 2.7.3, and `chunks={}` is wrong advice at this scale.
  nmfs-opensci/agent-skills#19 (viewer + README on every scratch test) is open, unmerged.
- **Attribution names Rich Signell as well as Eli** ("Holmes, E.E. and Signell, R."), at
  Eli's request: none of his code is used, but sub-chunking this archive is his idea. The
  LICENSE has no copyright line to add him to — only Apache's unfilled appendix template —
  and none was added. The Medium post's title and year (2024) in the citation could not be
  checked: Medium 403s automated fetches. Eli was asked to confirm them.
