# HYCOM GOMb0.01 gap-fill test — Icechunk

**[💻 Data access (code)](#how-to-open-it)** · **[📦 Source code](https://github.com/ocean-icechunks/hycom)**

**A scratch store for testing**, not a published dataset; it may be rewritten or deleted at any time. It tests
filling time gaps after a build (ocean-icechunks/hycom#22): three days of the
[HYCOM-TSIS GOMb0.01 reanalysis](https://www.hycom.org/data/gomb0pt01/gom-reanalysis), 2022-01-01 00Z to
2022-01-03 23Z, built with ten hours left out on purpose and then filled back, one commit per fill. Each fill
file was first checked by a gate (layout, fill value, attributes, coordinates, experiment, time). The arrays stay
in `s3://hycom-tsis-gom-reanalysis` (us-west-2). The store is the same as the 2022 test store in
`test-repo/hycom/hycom-tsis-gom-reanalysis`: group **`hourly`**, names as in the HYCOM files, 3-D fields one
depth of one 385 × 526 tile per chunk.

## How to open it

Python >= 3.12, `pip install "icechunk>=2.3" "xarray>=2026.9" "zarr>=3.4"`. No credentials are needed.

```python
import icechunk, xarray as xr, zarr

zarr.config.set({"async.concurrency": 128})   # the default of 10 is slow against object storage

url = "https://data.source.coop/ocean-icechunks/test-repo/hycom/gapfill-test/store"
repo = icechunk.Repository.open(icechunk.http_storage(url))
# The data is read from the HYCOM bucket; each virtual prefix has to be authorized, even anonymously.
auth = {p: icechunk.credentials.HttpAccess for p in repo.config.virtual_chunk_containers}
repo = repo.reopen(authorize_virtual_chunk_access=auth)
ds = xr.open_zarr(repo.readonly_session("main").store, group="hourly", consolidated=False, chunks=None)

# Each fill is a commit; its metadata lists the files and the reason.
for c in repo.ancestry(branch="main"):
    print(c.id, c.message.splitlines()[0], c.metadata.get("fill_reason", ""))

# The store as built, before any fill: the gaps read as NaN and the flags say "no source file" (2).
built = [c for c in repo.ancestry(branch="main") if c.message.startswith("references for")][0].id
old = xr.open_zarr(repo.readonly_session(snapshot_id=built).store, group="hourly", consolidated=False, chunks=None)
print(old.cell_methods_3z.values[48:54], ds.cell_methods_3z.values[48:54])   # 2022-01-03 00-05Z: 2 before, 0 after
```

## The gaps and the fills

| Gap left out at build | Hours | Filled by |
|---|---|---|
| 3z only | 2022-01-02 06Z | commit 1 |
| 2d only | 2022-01-02 12Z | commit 2 |
| 2d and 3z | 2022-01-02 18Z | commit 3 |
| 3z, six consecutive hours | 2022-01-03 00–05Z | commit 4 |

After the fills the store has no gaps. `fill-log.json` beside this README has each fill's gate results (the
checks passed, the files' Last-Modified, the pin) and the commits.

- **Land and gaps read as NaN.** The store declares the fill value that is actually on land (2**100).
- `experiment`, `cell_methods_2d` and `cell_methods_3z` are rewritten by each fill for its hours.
- The references a fill writes are pinned to the time the gate first looked at the file, so a file HYCOM rewrites
  later fails to read until it is checked and filled again (as a replacement).
