# Handoff — hycom

Rolling state for this repo. Orientation only: the open threads below are a record of what
is unfinished, not a task list.

## Where things stand (2026-09-18)

The repo holds only `LICENSE` (Apache-2.0), a stub `README.md` and this directory. Issue #1
asks for a virtual Icechunk of the HYCOM GOFS 3.1 reanalysis on AWS Open Data (63,341
uncompressed NetCDF-3 files, 305.8 TB), published to Source Cooperative at
`ocean-icechunks/hycom/hycom-gofs-3pt1-reanalysis`, with tests going to
`ocean-icechunks/test-repo/hycom`.

Research, the plan and a **local smoke test** are done (2026-09-18). The smoke test lives
on branch `smoke-test-issue-1` (`hycom_virtual.py`, `hycom-smoke-test-local.ipynb`,
`requirements.txt`) and passed in a clean venv; a second smoke test wrote the same window to
the Source Cooperative scratch prefix and a gridlook viewer sits beside it. There is no
production notebook and nothing at the published prefix. What it taught, including several things
in the code that look wrong and are deliberate, is in
[notes/smoke-test-findings.md](notes/smoke-test-findings.md). The plan, the
measurements behind it, and every decision Eli has made are in
[notes/plan-issue-1.md](notes/plan-issue-1.md) — read it before touching anything. The
scripts that produced the measurements are in `notes/issue-1-research/`.

The two facts most likely to be got wrong:

- **There are two header layouts, 40 bytes apart, and file size — not experiment number —
  tells them apart.** Offsets must come from each file's own header. Reusing one file's
  offsets as a template (as the rsignell/hycom-kerchunk notebook does) misplaces data in
  27,439 files.
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

- The scratch-prefix smoke test has run and a viewer is published beside it
  (`test-repo/hycom/`); Eli is checking whether the viewer renders with a CORS extension.
  After that comes the production notebook, which does not exist yet.
- `tau`/`experiment` became auxiliary coordinates during the smoke test; Eli has not yet
  confirmed that.
- Source bucket has no CORS, so the viewer will not show data in an ordinary browser; a
  request to help@hycom.org / COAPS is undrafted.
- README is a stub: the reuse statement is missing and is part of the README deliverable.
