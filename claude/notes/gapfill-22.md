# Filling time gaps after the build, with a gate (#22) — 2026-11-19

Part of #17. Code: `hycom-tsis-gom-reanalysis/gom_virtual.py`, section "gap filling (#22)". Tests:
`claude/notes/issue-22-research/gapfill_test.py`; raw results in `issue-22-research/results/`; the test-repo README source is `issue-22-research/gapfill-test-README.md`. Everything below
was run in a clean venv built from `hycom-tsis-gom-reanalysis/requirements.txt` (Python 3.13, icechunk 2.3.1,
virtualizarr 2.8.0, xarray 2026.9.0, zarr 3.4.2, h5py 3.16.0). No dependency was missing.
The two changes to the build path (`scan_h5py` now also records the file's `MT`; `virtual_variables` accepts
`src_attrs=None`) were checked by re-running `gom-smoke-test-local.ipynb` in the same venv: 0 errors, `cf:1.11`
"All tests passed!", every value identical to h5py (the first attempt failed on an S3 503 and the rerun passed).

## What a fill is

An hour with no usable file at build time is on the `MT` axis with no reference, so it reads as the fill value
(NaN), and its `cell_methods_<kind>` flag is 2 ("no source file"). When a file arrives later:

1. **Gate:** `check_fill_candidates(keys, session)` checks each file against one snapshot of the store and
   returns, per file, `ok` and every reason it failed. Nothing is written.
2. **Fill:** `fill_hours(repo, accepted, reason=...)` takes only accepted results, and per batch of hours writes
   one commit: the references for just those hours, the hours' `experiment` and `cell_methods_*` flags, and a
   message plus commit metadata (`fill_reason`, `files`, `pinned_at`, `gated_against`, `cell_methods`).
3. **README gaps table:** `store_gaps(session)` lists the remaining gaps as runs of hours per kind, from the flags;
   `gaps_markdown` makes the README table. So the table is regenerated from the store after each fill, not edited
   by hand. The fill log is the commit history itself (`repo.ancestry`, each commit's metadata).

`reason` is `"new hour"`, `"replacement"` or `"bulk"`. A replacement is explicit: the gate rejects a file for an
hour that already has a reference unless `replacement=True`, and rejects `replacement=True` on a gap.

### The gate's checks

| Check | How | Source of truth |
|---|---|---|
| Name | `KEY_RE` (010/023/026, `YYYY/…_YYYY_DDD_HH_(2d\|3z).nc`); 027/028 and `_CORRUPTED`/`_COPY` named as such | — |
| Time on the axis | the filename's hour on the store's `MT` (to 1e-6 days) | store `MT` |
| Gap, or replacement | `cell_methods_<kind>` == 2, **and** the manifest has no reference there (`Session.chunk_type`); the two disagreeing is its own rejection | store flags + manifest |
| Experiment | equal to the hour's other kind if present, else to the nearest non-zero `experiment` before or after; `allow_experiment=True` for a real boundary | store `experiment` |
| Object | HEAD: exists; Last-Modified not after the gate began | source bucket |
| Empty | size ≥ `MIN_SIZE` (zero-time-step 3z files are 239 B / 49 KB) | — |
| Layout and `_FillValue` attribute | `scan_h5py`: shape, chunk shape, `<f4`, no compression/shuffle, every chunk's size, every chunk inside the file, `_FillValue` bits | — |
| File `MT` | equals the filename to the hour (3z is float32-rounded, audit F8) | file |
| `cell_methods` | in `CELL_METHODS_FLAGS` (`None`, `"MT: mean"`) | code (R22) |
| Attributes | `gate_fingerprint` (all variable and global attributes except `valid_range`, `cell_methods`, `history`, `NCO`, `_NCProperties`) in `GATE_FINGERPRINTS` | code: reviewed values |
| Global attributes | `Conventions`, `title`, `source`, `experiment` equal the store's `source_Conventions`, `source_title`, `source`, `experiment` | store attrs |
| Coordinates | md5 of `Latitude` and `Depth` equal the store's; `Longitude` the store's or, for 3z, `LON_3Z_VARIANTS` (HYCOM item 8) | store coords |
| Land holds 2**100 (R21) | one ranged GET of 8 rows (67 kB of a 2d `ssh` map, 17 kB of a 3z `water_temp` tile at depth 0), rows chosen where land and sea are most mixed: land must be exactly 2**100, sea finite and not fill | store `mask` |

Two choices worth review:

- **The reference fingerprints are reviewed constants in the code**, not something stored in the store. The store
  keeps repaired attributes (R1–R22), not the source's, so it cannot be the reference. One gate fingerprint per
  kind (`8f3485af1c` 2d, `1cb0ede4c6` 3z) covers 010 (2001, 2005, 2010), 023 (2021, 2022) and 026 (2024) files
  and the 2005 ncra stand-in, measured 2026-11-19. A new value rejects the file until someone looks, exactly as
  an unknown `cell_methods` stops the build.
- **The checksum pin is the time the gate began**, rounded up to the second, not the commit time. A file that
  HYCOM rewrites between the gate and the commit then fails to read rather than being served unchecked. (The
  build pins to write time: VirtualiZarr's default `last_updated_at` is now + 1 s.)

### What `fill_hours` writes, and does not

- One region write per run of consecutive hours, with only the kinds being filled. **Hours outside the batch are
  never touched:** VirtualiZarr skips empty paths in `set_virtual_refs_arr`, so a region write cannot erase a
  reference, and the diffs below show only the filled hours' chunks changed.
- No array attributes: `virtual_variables(..., src_attrs=None)` gives the region write no attributes, so the
  stored ones stay as the build wrote them. (Taken from a fill file, an ncra stand-in's could reach the array.)
  The diffs show no array metadata updated.
- `experiment` and both `cell_methods_*` are rewritten whole: they are one chunk along the axis, so this costs the
  same as writing a few hours.
- Before writing, it re-reads the branch and refuses if any hour gained or lost its reference since the gate
  (`RuntimeError`, nothing committed), so two fills of one hour cannot both land.
- `gc.collect()` after each batch; open the repository with `gv.build_config_override()` for a bulk fill (#21).

## Test results (2026-11-19, this hub, local repositories, d = 1)

Three small local stores, built like the scratch store (skeleton, then a region write), with gaps made by
leaving files out:

- **A:** 2022-01-01 to 02-28 on the axis, references for Jan 1–7 only. Left out: 3z only 01-02 06Z; 2d only
  01-03 12Z; both 01-04 18Z; a 3z run 01-05 00–05Z. Jan 8 – Feb 28 is the bulk case (test 6).
- **B:** 2002-02-15 (day 046) 10–17Z, experiment 010. The 12Z 3z hour is built **referencing the 13Z file** (a
  simulated wrong reference); 16Z 3z is a gap. 12Z and 16Z are the regenerated files HYCOM has now confirmed.
- **C:** 2005-03-20 (day 079) 00–07Z, with the 04Z 3z (the ncra stand-in) left out.

"Identical" below means bit for bit (`view("u4")`), store opened with `mask_and_scale=False` against h5py:
all 6 2d maps; for 3z the depth-0 `water_temp` map, a 40-depth `salinity` profile, and a 200 × 200 box over
four tiles at depths 0, 17 and 39 for all 5 variables.

| Test | Result |
|---|---|
| 1. Build with gaps | **Pass.** Store A built in 6.4 s (326 files scanned in 11 s). All 10 left-out (hour, kind) pairs read as the fill value; `store_gaps` lists exactly them plus Jan 8 – Feb 28. |
| 2. Fill back, 4 commits | **Pass.** Gate 0.5–1.6 s, fill 0.2–1.5 s per commit (3,200 / 6 / 3,206 / 19,200 references). Values identical at all 10 filled pairs. `experiment` 23 and both flags 0 for all 168 hours of the week afterwards. **Other hours unchanged:** a point series over all 1,416 hours changed only at the filled hours (ssh: 60, 90; water_temp: 30, 90, 96–101), and each commit's `repo.diff` lists chunks only at its own hours, plus chunk 0 of the three flag arrays, with no array metadata updated. **Earlier snapshot**, opened by id: all 10 still gaps, `cell_methods_3z` 2 at 01-05 00–05Z, `experiment` 0 at 01-04 18Z. A fresh `Repository.open` on `main` sees the filled data. The commit message lists the files; the metadata holds them with the reason and pin. |
| 3. Rejections | **Pass**, each with its reason (below). Real files: 2004_153_19_2d (layout B chunking), 2006_177_18_3z (empty, 49,818 B), an hour off the axis, an hour already filled without `replacement`, 027, a `_COPY` key, a `_CORRUPTED` name; `replacement=True` on a gap. Simulated by changing one thing in a good candidate's scan or in the store reference: unknown `cell_methods`, Latitude, Longitude or Depth checksum, a changed variable attribute, a changed global `title`, `MT` an hour off, a different experiment, and the land check against an inverted mask. |
| 4. Acceptances | **Pass.** The stand-in 2005_079_04_3z is accepted (gate fingerprint `1cb0ede4c6`, the same as model output; its full fingerprint is `615cdf11fc`), filled, flagged `cell_methods_3z` = 1 (`[0,0,0,0,1,0,0,0]`), values identical, and the commit metadata records `"MT: mean"`. Every 2022 3z file is accepted with Longitude `8edb2d05` (the variant) against the store's `e3b00e34`. |
| 5. Replacement | **Pass.** (a) Store B 12Z: without the flag, rejected "not a gap"; with it, accepted and filled. Before: 12Z identical to the 13Z file. After: identical to the 12Z file, no longer equal to 13Z, `diff` shows only hour 2's 640 chunks per 3z variable. The old snapshot still reads the 13Z file there. (b) The pin: 16Z filled with a pin of 2026-11-10, before the object's Last-Modified (2026-11-14 20:16:37): a read fails with `StorageError: the checksum of the object owning the virtual chunk has changed`. Gated again with `replacement=True` and refilled with the gate's pin (17:51:22): reads succeed, identical to h5py. |
| 6. Bulk | **Pass.** Store A, Jan 8 – Feb 28 (1,248 hours, 2,496 files, all of February included), in a fresh process. Gate: **108.7 s, 23 files/s**, 0 rejected (16 scan processes; main process 0.19 GB, largest child 0.11 GB). Fill: 2 commits of 744 and 504 hours, **2,385,264 refs in 14.6 s and 1,615,824 in 9.5 s**, 24.1 s in all. **Peak 2.08 GB** with `build_config_override` and `gc.collect()` per batch. `diff`: 798,720 chunks per 3z variable and 1,248 per 2d variable (= 1,248 hours × 640 and × 1), all between hours 168 and 1415. Values identical at 2022-02-14 12Z (3z) and 01-20 03Z (2d); all 1,416 hours `experiment` 23, flags 0; `store_gaps` empty. One S3 503 on a verification read, retried once. Manifests on disk 43.9 MB. |
| 7. Source Cooperative | **Pass.** `s3://ocean-icechunks/test-repo/hycom/gapfill-test/store`: 2022-01-01 to 01-03 (72 hours) with the same four gap shapes (3z 01-02 06Z; 2d 01-02 12Z; both 01-02 18Z; 3z 01-03 00–05Z). Build 36.7 s. Four fill commits: gate 8.5 / 10.6 / 10.1 / 18.8 s, fill 25.9 / 17.5 / 31.1 / 70.1 s. **Read back anonymously** from `https://data.source.coop/ocean-icechunks/test-repo/hycom/gapfill-test/store`: open 0.42 s, 7 commits with their `fill_reason`, all 10 filled pairs identical to h5py, the built snapshot (by id) still shows all 10 as gaps with flags 2 (2d: 2 hours, 3z: 8) and `experiment` 0 at 01-02 18Z, `main` has none, and a masked read gives NaN at all 945,478 land points. README and `fill-log.json` beside the store. |

Peak memory for all of tests 1–5 in one process: 2.33 GB. No read needed a retry in the final run; an earlier
run hit one S3 `503 Service Unavailable` on a box read, which a rerun did not repeat, so the reads now retry 500
and 503 with a back-off and record it.

### Rejection reasons, as printed

```
2004_153_19_2d    layout: …ssh is not layout A: (1, 1537, 2101) (1, 769, 1051) <f4 None
2006_177_18_3z    empty: 49,818 bytes; a good 3z file has at least 2,590,000,000 (zero time steps)
off the axis      time: 2022-04-10 00:00:00 is not on the store's MT axis (2022-01-01 00:00:00 to 2022-02-28 23:00:00)
already filled    not a gap: 2022-01-01 00:00:00 already has a 3z reference; a replacement must say so (replacement=True)
replacement, gap  replacement: 2022-01-02 06:00:00 has no 3z reference to replace; fill it as a new hour
027               name: not a layout A hourly file name (a layout B experiment (027/028))
_COPY/_CORRUPTED  name: not a layout A hourly file name (a _CORRUPTED, _COPY or stray name)
cell_methods      cell_methods: 'MT: sum' is not a known value ["'MT: mean'", 'None']; review it first
Longitude         coordinates: Longitude checksum deadbeef is not the store's or a known variant ['8edb2d05', 'e3b00e34']
units changed     attributes: fingerprint ed5817cc86 is not a reviewed 3z fingerprint ['1cb0ede4c6']
title changed     attributes: fingerprint 9207971629 …; global attributes: title = 'HYCOM v2', the store's sources have 'HYCOM'
MT off            time: the file's MT 44197.291666666664 is 2022-01-02 07:00:00, not the filename's 2022-01-02 06:00:00
experiment        experiment: 023, but this hour's other file is 026
land check        fill value: water_temp probe (8 rows): 2103 land points are not 2**100, 2105 sea points are fill or not finite
```

(2004_153_19 and 2006_177_18 also get "not on the store's MT axis", since store A is 2022; every reason is listed.)

## What works, what does not, what was not tested

Works: everything in the table. Does not work / limits:

- **No real "different file for an already-referenced hour" exists on S3.** The `_CORRUPTED` originals are on
  HYCOM's server only, and S3 has one layout A file per hour. So test 5a simulates a wrong reference (12Z built
  pointing at 13Z), and 5b simulates a rewrite after the fill with an early pin. What this does test: references
  are rewritten, only that hour changes, the old snapshot keeps the old ones, a stale pin makes reads fail, and a
  replacement re-pins. What it does not: a real in-place rewrite of an object by HYCOM between fills.
- **The pin is per batch**, not per file (VirtualiZarr takes one `last_updated_at` per write). With the gate's
  start time it is still correct for every file in the batch; a per-file ETag pin (`set_virtual_refs_arr` accepts
  a string checksum) would be stricter, but is not what VirtualiZarr's writer passes.
- **Experiment check at a real boundary** (010→023 on 2019-01-01, 023→026): the neighbour rule accepts either
  side, but a fill of a whole uncopied stretch that ends at a boundary was not tested. `allow_experiment=True`
  exists for it.
- The **land check reads only `ssh` / depth-0 `water_temp`**, 8 rows. A file wrong only in another variable passes
  it (the layout and attribute checks still apply). The mask matched exactly at the probe in every accepted file.
- `GATE_FINGERPRINTS` comes from 10 sample files. The full scan may find others; they will be rejected, listed,
  and need review before they are added.
- **A fill commit on Source Cooperative costs 18–70 s even for one hour** (locally 0.2–1.5 s). Not from the
  checks: anonymously, `gate_reference` takes 1.5 s and `has_reference` at most 0.12 s. So it is the writes and
  the commit through Source Cooperative, as in the 2022 scratch build (about 24 s per monthly batch). Not
  profiled further. For bulk this is amortized over 744 hours per commit; for single hours, batch them.
- **Not tested:** concurrent fills (the re-check before writing should make the second one fail; not run); fills
  on a store with the production skeleton (the build does not yet write it without a manifest, plan "One-month
  check"); manifest size after many small fill commits, and snapshot expiry.

## How a fill runs in production

1. List the bucket (`gv.list_keys`) and pick the candidate keys: hours the store reports as gaps
   (`gv.store_gaps`), whose files now exist. For a replacement, the keys whose Last-Modified is newer than the
   store's pin, or that HYCOM names.
2. `res = gv.check_fill_candidates(keys, repo.readonly_session("main"))`. Keep the rejected list with its
   reasons; anything not a plain "not a gap" or "empty" needs a person.
3. `repo = icechunk.Repository.open(storage, gv.build_config_override())`, then
   `gv.fill_hours(repo, [r for r in res if r["ok"]], reason="bulk")` (or `"new hour"`; replacements in a separate
   call with `reason="replacement"`). One commit per 744 hours by default.
4. Regenerate the README's known-gaps table from `gv.store_gaps`, upload the README, and keep the gate results
   beside the build's skip list.

**Scale, predicted from test 6 (arithmetic, not measured):** the ~111,600 uncopied files of 2001–2020 at 23
files/s on this hub is about 80 min of gating (the gate's scan is the same scan the build does, so it replaces
it rather than adding to it), plus about 75 commits of 744 hours. The gate needs no write credentials, so it can
run before the Source Cooperative token is fetched; the fill re-checks the branch before each commit.

## Open for Eli

- Where the reviewed `GATE_FINGERPRINTS` / `LON_3Z_VARIANTS` live: constants in `gom_virtual.py` (as now, like
  `CELL_METHODS_FLAGS`), or a reviewed JSON next to it.
- Whether production fills are only "new hour" and "bulk" until HYCOM rewrites something, and whether a
  replacement needs a person's sign-off each time (the code only requires `replacement=True`).
- `HELD_BACK` in `gom_virtual.py` still lists the 5 regenerated 2002 files that HYCOM has now confirmed. Left
  for the phase 2 session to change, to avoid a conflict. Whether they go in at the first build or as the first
  fill is a choice; this test shows either works.
- A viewer catalog entry for the gap-fill test store (`publish_viewer.py` `TEST_ONLY`). Not done: it would
  rewrite `test-repo/hycom/viewer/`, outside this session's allowed prefix.

## For the plan's "Filling gaps after the fact"

> **Tested in #22 (2026-11-19; `claude/notes/gapfill-22.md`).** A gap is filled as a new commit in two steps.
> `check_fill_candidates` (the gate) checks every file against the store first: name, hour on the axis and a gap
> (or an explicit replacement), experiment against the neighbouring hours, size, layout and `_FillValue` (the
> scan), the file's `MT`, `cell_methods`, an attribute fingerprint against reviewed values, coordinates against
> the store (plus the known 3z Longitude variant), and land = 2**100 in a 17–67 kB probe. A rejected file is
> listed with its reasons and nothing is written. `fill_hours` then region-writes references for just those
> hours, rewrites `experiment` and `cell_methods_*`, and commits with the files and reason in the message and
> metadata; references are pinned to the time the gate first saw the files, so a later rewrite by HYCOM makes
> reads fail until the file is gated and filled again as a replacement. Locally, at d = 1, every filled hour was
> identical to h5py, no other hour's references changed (`repo.diff`), the earlier snapshot still showed the
> gaps, and the ncra stand-in was flagged `MT_mean`. A bulk fill of 1,248 hours (2,496 files) took 109 s to gate
> and 24 s to write (4.0 M references, 2 commits), peaking at 2.1 GB with the #21 fix. The same small test ran on Source Cooperative
> (`test-repo/hycom/gapfill-test/`) and read back anonymously. The README's gaps table is generated from the
> store (`store_gaps`).

## Viewer check (2026-11-19)

`test-repo/hycom/gapfill-test/with-gaps` is the same build never filled, in the test viewer catalog, because gridlook
opens only `main`. **Eli checked it in a browser: "viewer shows time steps w no data as I expect"** (2026-11-19).
