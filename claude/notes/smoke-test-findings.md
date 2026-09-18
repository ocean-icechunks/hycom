# What the local smoke test taught (2026-09-18)

`hycom-smoke-test-local.ipynb`, run in a venv built from `requirements.txt` alone
(icechunk 2.2.2, virtualizarr 2.7.3, zarr 3.4.0, xarray 2026.7.0, obstore 0.11.1,
Python 3.12.12), hub in us-west-2. 93 s end to end. It passed: raw `int16` identical to
netCDF4-C's `#mode=bytes` reader for six files covering both header layouts, the first and
last files and the 53.0→53.1 boundary; the missing step reads all-NaN in 0.28 s; IOOS
compliance-checker `cf:1.11` reports "All tests passed".

## Things that look wrong in the code and are deliberate

- **Science arrays are declared native `int16` with a `bytes(endian=big)` codec, not
  `>i2`.** Zarr v3 dtypes carry no byte order. Declaring `>i2` works for the first write and
  then VirtualiZarr 2.7.3 refuses every `region=` or `append_dim=` write with
  `inconsistent dtypes: int16 vs >i2`, because the stored array reopens as native. Arguably
  an upstream bug in `check_same_dtypes` (it compares numpy dtypes, not Zarr ones); not yet
  reported. Reads are correct either way — the codec does the byte swap.
- **`to_icechunk` has no `encoding=` argument in VirtualiZarr 2.7.3**, although the
  `virtual-icechunk` skill's snippet passes one. Loaded variables go through
  `Dataset.to_zarr`, so the one-chunk `time` is set with `var.encoding["chunks"]`. Worth
  feeding back to the skill.
- **The store is written as a skeleton plus `region={"time": slice(a, b)}` batches**, not by
  appending. The skeleton holds the full-length coordinates and science arrays with no
  references; each batch is a dataset of the nine virtual variables only. This suits a
  regular axis, is restartable in any order, and keeps the loaded coordinates in one chunk
  (appending would add a chunk per batch). Production plan: one batch per year.
- **`tau` and `experiment` are auxiliary coordinates, not data variables.** Decided during
  the smoke test, not by Eli — flagged to them. CF treats a forecast period as an auxiliary
  coordinate, and as coordinates they travel with every DataArray (`da.tau`).
- **The present-only view is `ds.isel(time=ds.tau.notnull().values)`.** The `.values`
  matters: with `chunks={}` `tau` is a dask array and xarray raises on a lazy boolean
  indexer. The `sel(time=ds.time[...])` form first proposed to Eli fails for that reason.
  Use the working form in the README.
- **Decoded values are float64, not the source's float32.** Zarr attributes are JSON, so
  `scale_factor` loses its float32 type and xarray promotes. The value is kept exactly as the
  source has it (0.0010000000474974513), not tidied to 0.001. Consequence for users: a
  decoded level is 117 MB, not 58; `mask_and_scale=False` gives the raw `int16`.

## CF check: two artefacts of exporting Zarr to NetCDF, not store defects

The checker reads NetCDF, so the notebook exports a tiny corner. Two errors on the first run
came from that export: xarray adds `_FillValue` to float coordinates unless the encoding
says `None` (now set in the store too), and JSON attributes have no dtype, so `flag_values`
exported as int64 against an int16 variable (cast in the export cell). Two real
recommendations were adopted: `units_metadata = "temperature: on_scale"` on the temperature
variables and `"leap_seconds: unknown"` on `time` (CF-1.11 §3.1.2, §4.4).

## Timings (in-region, `async.concurrency = 64`, local repo) — observations

| read | time |
|---|---|
| open four groups | 0.10 s |
| one level, global (1 chunk, 29 MB) | 0.42 s |
| full-depth profile at a point (40 chunks, 1.2 GB) | 5.6 s |
| 16-step surface series at a point (15 chunks) | 2.8 s |
| full bucket listing | 12 s |
| 29 header reads | 0.2 s |

Any selection inside a level fetches the whole 29 MB level. A single-level point series over
the record is 1.85 TB.

## Not yet tested

The full 63,341-file header scan; manifest size and open time at ~10.5 M references (the
2920-steps-per-manifest split is a guess); any write to Source Cooperative; reads from
outside us-west-2; reconciling the 931 missing steps with hycom.org's FAQ.
