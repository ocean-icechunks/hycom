# Handoff — hycom

Rolling state for this repo. Orientation only: the open threads below are a record of what
is unfinished, not a task list.

## Where things stand (2026-09-18)

The repo holds only `LICENSE` (Apache-2.0), a stub `README.md` and this directory. Issue #1
asks for a virtual Icechunk of the HYCOM GOFS 3.1 reanalysis on AWS Open Data (63,341
uncompressed NetCDF-3 files, 305.8 TB), published to Source Cooperative at
`ocean-icechunks/hycom/hycom-gofs-3pt1-reanalysis`, with tests going to
`ocean-icechunks/test-repo/hycom`.

**The store is built** (2026-09-18): tag `v1`, 10.45 M references from 63,341 files, validated
from the public URL, with a gridlook viewer at `ocean-icechunks/hycom/viewer/`. Everything is
on branch `smoke-test-issue-1` (no PR yet): `hycom_virtual.py`, the production notebook
`hycom-icechunk-sc.ipynb`, two smoke-test notebooks, `publish_viewer.py`, `requirements.txt`.
Still to do for issue #1: the README, mirroring the docs beside the store, and the PR.

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

- README with reuse statement; mirror the docs to `ocean-icechunks/hycom/` from merged `main`;
  open the PR. Eli has confirmed `tau`/`experiment` stay auxiliary coordinates.
- Eli has seen the test viewer render (with a CORS extension); the production viewer is
  published and not yet looked at.
- Source bucket has no CORS; a request to help@hycom.org / COAPS is undrafted.
- Two things worth feeding back to the `virtual-icechunk` skill: `to_icechunk` has no
  `encoding=` argument in VirtualiZarr 2.7.3, and `chunks={}` is wrong advice at this scale.
  nmfs-opensci/agent-skills#19 (viewer + README on every scratch test) is open, unmerged.
