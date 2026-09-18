# Handoff — hycom

Rolling state for this repo. Orientation only: the open threads below are a record of what
is unfinished, not a task list.

## Where things stand (2026-09-18)

The repo holds only `LICENSE` (Apache-2.0), a stub `README.md` and this directory. Issue #1
asks for a virtual Icechunk of the HYCOM GOFS 3.1 reanalysis on AWS Open Data (63,341
uncompressed NetCDF-3 files, 305.8 TB), published to Source Cooperative at
`ocean-icechunks/hycom/hycom-gofs-3pt1-reanalysis`, with tests going to
`ocean-icechunks/test-repo/hycom`.

Research and a feasibility probe are done and the plan is fully decided (2026-09-18);
**no build code exists yet**. The plan, the
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
- No browser on the hub: verify transport (status, content type, CORS) here, and ask Eli
  whether it renders.

## Open threads

- Smoke-test notebook not started.
- Source bucket has no CORS, so the viewer will not show data in an ordinary browser; a
  request to help@hycom.org / COAPS is undrafted.
- README is a stub: the reuse statement is missing and is part of the README deliverable.
