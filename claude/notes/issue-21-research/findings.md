# Issue #21: memory growth across monthly batches — findings (2026-11-19)

Investigated by a separate agent session on branch `gom-memory-21` (merged into `gom-layout-a-plan`). Script:
`mem_experiment.py` (this directory). Raw logs and per-batch JSON were in the session scratchpad and were not kept;
the numbers below are copied from them. The two library facts at the heart of the root cause were re-checked in the
installed sources afterwards (see "Root cause").

**Setup.** This hub (4 cores, 31 GB cap, shared with another build running at the same time). Python 3.13, icechunk
2.3.1, virtualizarr 2.8.0, xarray 2026.9.0. 2022 at d = 1, local repository, `async.concurrency` 128. A skeleton over
the year, then one region write + commit per month, as `year_test.py`. The 2022 scan pickle was reused. Batches are
2.15–2.39 M references.

**What is measured.** `rss_end`: current RSS (`/proc/self/statm`) at the end of a batch. `peak`: peak RSS *within
that batch* (VmHWM reset with `/proc/self/clear_refs` = 5 at the start of the batch). `ru_maxrss`, which the year test
logged, is the whole-process peak; it can only rise, so it could not separate retained memory from a growing transient.

## Runs (d = 1, 2022, one process at a time)

"cache 0" = `CachingConfig(num_chunk_refs=0)`. Manifests = all files under `manifests/` on disk.

| Run | Switches | Months | Current RSS after each batch, GB | Peak within each batch, GB | Max peak | Manifests on disk |
|---|---|---|---|---|---|---|
| base6 | none (as year_test.py) | 6 | 2.69 3.23 3.65 4.39 4.86 4.80 | 2.81 3.36 3.77 4.52 5.00 4.97 | 5.00 | 142.7 MB, 129 files, 10.25 B/ref |
| gc6 | `--gc` | 6 | 1.91 2.45 3.13 3.54 3.64 3.69 | 2.72 2.58 3.26 3.67 3.84 3.85 | 3.85 | 142.6 MB, 129, 10.24 |
| cache0 | cache 0 | 6 | 2.47 2.87 2.92 3.24 3.61 3.92 | 2.60 2.99 3.08 3.40 3.79 4.08 | 4.08 | 142.4 MB, 129, 10.22 |
| cache0_gc6 | cache 0, `--gc` | 6 | 1.75 2.02 2.46 2.44 2.48 2.45 | 2.56 2.15 2.59 2.63 2.64 2.62 | 2.64 | 142.6 MB, 129, 10.24 |
| override_gc6 | `--build-override --gc` (the change) | 6 | 1.78 2.07 2.46 2.44 2.47 2.46 | 2.59 2.20 2.59 2.61 2.66 2.61 | 2.66 | 142.7 MB, 129, 10.25 |
| trim6 | `--malloc-trim` | 6 | 1.80 2.42 3.43 4.17 3.63 3.97 | 2.77 3.31 4.41 5.13 4.94 5.09 | 5.13 | 142.7 MB, 129, 10.25 |
| gc_trim6 | `--gc --malloc-trim` | 6 | 1.01 1.35 1.99 2.43 2.50 2.50 | 2.75 2.52 3.32 3.73 3.88 3.84 | 3.88 | 142.4 MB, 129, 10.22 |
| cache0_gc_trim | cache 0, `--gc --malloc-trim` | 6 | 0.85 1.06 1.27 1.29 1.29 1.29 | 2.60 2.23 2.65 2.63 2.64 2.62 | 2.65 | 142.4 MB, 129, 10.22 |
| delsess6 | `--del-session` | 6 | 2.56 3.22 4.29 4.52 4.83 5.13 | 2.68 3.35 4.41 4.65 5.00 5.30 | 5.30 | 142.3 MB, 129, 10.22 |
| reopen2_6 | `--reopen-every 2` | 6 | 2.66 3.21 3.02 3.41 3.05 3.59 | 2.79 3.33 3.14 3.54 3.18 3.62 | 3.62 | 142.6 MB, 129, 10.24 |
| split744_6 | `--split-hours 744` | 6 | 2.53 3.44 4.32 5.03 5.03 5.07 | 2.78 3.56 4.44 5.15 5.06 5.10 | 5.15 | 139.5 MB, 118, 10.02 |
| split8760_6 | `--split-hours 8760` | 6 | 2.66 3.09 4.03 4.30 4.03 4.33 | 2.78 3.40 4.51 5.09 4.93 5.20 | 5.20 | 306.9 MB, 74, 22.04 |
| fresh6 | `--fresh-process` | 6 | 1.86 1.71 2.97 2.94 2.64 2.94 | 1.99 1.83 3.10 3.06 2.76 3.06 | 3.10 | 142.4 MB, 129, 10.22 |
| gc12 | `--gc` | 12 | 1.95 2.40 3.22 3.60 3.73 3.68 3.72 3.72 3.72 3.72 3.72 3.72 | 2.76 2.53 3.35 3.73 3.89 3.85 3.90 3.90 3.90 3.96 3.96 3.96 | 3.96 | 315.9 MB, 261, 11.25 |
| fix12 | cache 0, `--gc` | 12 | 1.77 2.07 2.48 2.45 2.48 2.45 2.48 2.49 2.49 2.47 2.48 2.49 | 2.59 2.20 2.64 2.62 2.65 2.62 2.67 2.67 2.67 2.67 2.67 2.67 | 2.67 | 316.2 MB, 261, 11.26 |

Every run: 0.35–0.47 GB after loading inputs, 0.86–0.93 GB after the skeleton. Batch times about 17 s per 31-day
month, with or without the cache. In base6 most of each month's increase arrives during `commit` (January 1.90 → 2.69
GB), and RSS after `del batch` equals RSS after commit every month.

## Hypotheses (from #21)

- **H1, reference cycles: confirmed.** `batch.vz.to_icechunk(...)` makes xarray cache the VirtualiZarr accessor on the
  Dataset (`_CachedAccessor` stores it in `obj._cache`, `xarray/core/extensions.py`). The accessor keeps the Dataset
  (`self.ds = ds`, `virtualizarr/accessor.py`). After write + commit + `del batch`, all 22 ManifestArray/ChunkManifest
  objects were still alive. A batch that was built but never written was freed at once. `gc.collect()` found 126
  objects each month; under `DEBUG_SAVEALL` they are the Dataset, Variables, ManifestArrays, ChunkManifests and the
  accessor. After the skeleton it found 300–505 objects and freed 0.4–0.7 GB. With gc alone, growth stops once the
  Icechunk cache is full (gc12: plateau at 3.72 GB). RSS barely drops at the `gc.collect()` call itself, because glibc
  keeps the freed heap and reuses it.
- **H2, sessions kept alive: no effect.** Deleting the session gave 5.13 GB at 6 months. Reopening every 2 months gave
  3.59 GB, but that run also calls `gc.collect()` and starts each new Repository with an empty cache, so it mixes H1
  and H3.
- **H3, Icechunk caches: confirmed.** The icechunk 2.3.1 defaults are `num_snapshot_nodes` 500,000, `num_chunk_refs`
  15,000,000, and 0 for the other three settings (the `CachingConfig` docstring in the installed
  `icechunk/_icechunk_python.pyi`, and `repr(icechunk.CachingConfig())`). At d = 1 the chunk-reference cache held about
  1.2 GB that the build never reads back: gc alone gives a 3.72 GB plateau, gc + cache 0 gives 2.49 GB. Because the
  cache has a cap, the year-test curve flattened. Inferred, not checked in the Icechunk source: the cache fills with the
  manifests each commit loads and writes.
- **H4, manifest splits: no memory effect, but a disk effect.** 744- and 8760-hour splits grew in memory like 730.
  8760-hour splits wrote 22 B/ref. With 730-hour splits there were 129 manifest files after 6 months, where about 66 are
  needed. Inferred: each commit rewrites the whole split it touches, and the superseded manifests stay on disk as
  history. So the 11 B/ref of the year test counts old manifests, not a larger final store. **Not measured:** the final
  snapshot's manifest size, and what expiring snapshots plus Icechunk GC would remove. Check before the production upload.
- **H5, allocator: real, but not a leak.** `malloc_trim(0)` gives back 0.8–1.3 GB every batch. That memory is freed but
  kept by glibc, and it does not grow. With the fix, end RSS is 2.45 GB without the trim and 1.29 GB with it; the peak is
  the same either way. The trim is not needed.
- **H6, the scan: ruled out.** RSS was 0.35–0.47 GB after loading all inputs.
- **Control, one month per fresh process:** each process started at 0.36 GB and peaked at 2.0–3.1 GB with the default
  cache, which confirms that the growth happens inside a process.

## Root cause

Two causes, both measured. The per-month Dataset written through `batch.vz` survives `del` until the cyclic GC runs.
And the Repository's chunk-reference cache (default 15 M references) grows to about 1.2 GB at d = 1. With `gc.collect()`
after every batch and no chunk-reference cache on the build's Repository object, memory stayed flat from March to
December: 2.5 GB current, 2.7 GB peak. The year test without the fix reached 6.04 GB.

## The change

- `gom_virtual.build_config_override()` returns `RepositoryConfig(caching=CachingConfig(num_chunk_refs=0))`.
- The build creates the repository with the normal config and calls `save_config()`. It then reopens through
  `Repository.open(storage, gv.build_config_override())`, and calls `gc.collect()` after `del skeleton` and after every
  `del batch`. This is in `year_test.py` and `scratch_store_2022.py`.
- **Do not put the zero cache into the config passed to `Repository.create`.** `create` persists its config (checked),
  so readers would lose the cache too. Opening the build with only the override keeps the persisted manifest split and
  virtual chunk container, and a plain reopen still shows the default cache. That path was measured: override_gc6, flat
  at 2.46 GB.
- A fresh process per year is not needed for memory. Flat memory over 23 years in one process is predicted, not measured.

## Not measured

- d = 2 and d = 10 with the fix.
- More than 12 months in one process.
- A small nonzero cache against 0. There was no sign that one would be faster.
- The final snapshot's manifest size, and what snapshot expiry would remove (H4).
- `tracemalloc` is a switch in the script but was not used.
- The edited `year_test.py` was compiled, not rerun.
- The skeleton's 0.84 GB per year (see the plan) is a separate, known problem.
