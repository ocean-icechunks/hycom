# GOMb0.01 reanalysis — audit (issue #8, PR #10) and what comes next

The findings are in `hycom-tsis-gom-reanalysis/audit/report.md`. This note records what the
report does not: the decisions Eli made, who does what, and what the next session must not get
wrong.

## Status (2026-09-26)

**The follow-up task is issue #11:** the store design and 3z chunking, with the options table, test
plan and build facts. #8 is closed; the `audit-gom-issue-8` branch is deleted.

**Waiting on another team.** They will copy the files to S3 (planned bucket
`hycom-tsis-gom-reanalysis`, which did not exist on 2026-09-25). The bucket and the copy are
theirs, not ours. **Our next step starts when one year of hourly files is on S3.** Then we
decide the 3z chunking and run the performance tests. Nothing on our side is blocked before
that. #8 has a comment for the file team with the four points below.

## Eli's decisions

- **No reprocessing of the files, 3z included.** The store design works around the files'
  chunking. Do not propose rewriting 3z again: 539 TB, and Eli has ruled it out.
- **Experiment 027 is the exception, and is to be reprocessed** to the others' chunking
  (`MT/1,Latitude/1537,Longitude/2101` for 2d, `MT/1,Depth/10,Latitude/385,Longitude/526` for
  3z). That is the file team's job; the report says why.
- **2d uses the whole 12.9 MB map as its virtual chunk.** It is not cut into 53-row bands.
  Eli's view is that 12 MB is a good chunk size. Point time series cost about 7 min per variable
  per year from S3 as a result, which is accepted.
- **3z chunking is open.** It is decided by testing on the real bucket, between 10, 5, 2 or 1
  depths of a tile per chunk (8.1 MB → 810 KB; 66 M → 663 M references).
- **The file team loads one year first.** The report suggests 2010 from experiment 010.
- Also for the file team, not us: leave out the 18 empty 3z files and the stray files, choose
  026 or 027 for the 653 overlap hours, compress nothing, and never overwrite a file on S3.

## Facts easy to get wrong

- **A 3z map at one depth cannot be one reference.** The files tile each depth 4 × 4, and each
  tile stores its 10 depths together, so one depth's map is 16 non-contiguous pieces. Eli first
  expected a 12.9 MB per-depth chunk to be possible; it is not, without rewriting.
- **Always say what a size covers.** "12.9 MB" is one variable, one hour, one depth. Eli asked
  twice for this precision.
- **The 663 M-reference figure is about tiles, not time.** It is 63× GOFS 3.1: 3.3× from hourly
  rather than 3-hourly output, the rest from 16 tiles × 40 depths × 5 variables per hour. GOFS
  had NetCDF-3 with one reference per whole global map.
- **Offsets differ between some files** (by a few bytes), so the build reads every file's header:
  1 read per 2d file, 6 per 3z file. Never template from one file.
- **The time axis comes from the filenames.** The 3z `MT` is float32-rounded, up to about
  2 min off the hour.
- **Pin checksums** (`to_icechunk(last_updated_at=…)`): tested, and it fails loudly on a
  changed file. HYCOM rewrote about 2,200 files in 2026.
- **The 2d and 3z variables go in one group** (tested). What must be uniform is one variable's
  chunk grid across time.

## Performance test plan, once a year is on S3

Build the year at two or three 3z chunkings, plus 2d whole-map. For each, measure:

- build time and peak memory;
- store open time;
- a one-depth full map;
- a 40-depth profile;
- a one-depth point time series over the year;
- a 200 × 200 box over time, placed both inside one tile and straddling four.

Start from `audit/05_split_and_time.py` and `08_one_group.py`, which already build split
references from per-file headers. Only the prefix changes. Local temporary repository first,
then `ocean-icechunks/test-repo/hycom/` with a viewer and README, per the skill's order.

## Server etiquette (only while files are still read from HYCOM)

- Use `data.hycom.org`, not `tds.hycom.org`. THREDDS sends no `Content-Length`, and Icechunk
  cannot read it.
- At most 8 connections, as Eli relayed from HYCOM. data.hycom.org answers bursts of 6–8
  concurrent requests to ONE file with 403, intermittently, and Icechunk does not retry a 403.
  Use concurrency 4.
- The THREDDS catalog XML is unusably slow. Use the Apache directory listings (about 6 s per
  year).

## Where things are

- The report, scripts and outputs are in `hycom-tsis-gom-reanalysis/audit/`. The directory name
  follows the planned bucket name; Eli has not objected to it.
- The CEFI audit used as the model is `~/cefi-icechunks/audit/`, read locally. `gh` is not
  authorized for the noaa-nwfsc SSO.
- Venv: `/srv/conda/bin/python3.12 -m venv`, then `pip install --no-cache-dir -r
  hycom-tsis-gom-reanalysis/audit/requirements.txt`. Verified in a clean venv.
