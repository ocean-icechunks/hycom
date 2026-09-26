# HYCOM-TSIS GOMb0.01 reanalysis — are the NetCDFs ready for a virtual Icechunk store?

Issue: ocean-icechunks/hycom#8. Audit run 2026-09-25 against
`https://data.hycom.org/datasets/GOMb0.01/reanalysis/data/`, the same files the THREDDS server
at tds.hycom.org publishes. The files are to be copied to S3 (planned bucket
`hycom-tsis-gom-reanalysis`) before any store is built. The question this
report answers is whether they need **reprocessing** on the way there.

## For the file team

1. **The files are good as they are.** Experiments 010, 023 and 026 (2001-01-16 to
   2024-04-28) need no reprocessing. That includes the 3z files: their chunking will be handled
   by how the Icechunk stores are structured, not by rewriting data.
2. **Experiment 027 needs reprocessing** (2024-04-01 19Z to 2024-09-01 18Z, 3,672 hours, hourly
   and daily). It was written with a different chunk layout from the rest, and a variable cannot
   change chunk layout partway through a virtualized store. Rewrite it to the others' chunking, uncompressed:
   - 2d: `MT/1,Latitude/1537,Longitude/2101`
   - 3z: `MT/1,Depth/10,Latitude/385,Longitude/526`

   See [Why experiment 027 must be reprocessed](#why-experiment-027-must-be-reprocessed).
3. **Put one year on S3 first.** One complete year of hourly 2d and 3z files, from experiment
   010 (for example 2010: 8,760 hours, about 0.7 TB of 2d and 23 TB of 3z), is enough to test
   the store designs below against the real bucket. The rest of the archive can follow while
   that testing runs.
4. **When copying:**
   - Leave out the 18 empty 3z files (F5) and the stray files (F9).
   - Decide which experiment covers the 653 hours where 026 and 027 overlap (F6).
   - Do not compress anything.
   - Treat files as frozen once they are on S3: put a replacement under a new key rather than
     overwriting (F8).

## The files

Read from the file headers (2010 files; every sampled file has the same grid, including
experiment 027's).

- **Format: NetCDF-4, i.e. HDF5.** The sampled files were written by six different netCDF-C and
  HDF5 versions (netCDF 4.7.3 to 4.9.4, HDF5 1.10.6 to 1.14.4, as recorded in `_NCProperties`).
  Within experiments 010–026 the version made no difference to the layout: the 023 and 026 2d
  files have the same byte offsets as 010's despite different libraries. Unlike NetCDF-3, HDF5 stores each variable in chunks, and these files are chunked. There is no
  compression and no shuffle filter; data are little-endian float32.
- **HDF5 chunking, per variable**, in dimension order (time `MT`, depth `Depth`, `Latitude`,
  `Longitude`):

  | Files | Variables | Chunk shape | Size | Chunks per variable per hour |
  |---|---|---|---|---|
  | `_2d.nc`, experiments 010 / 023 / 026 | 6 | {1 × 1537 × 2101} | 12.9 MB | 1: the whole map |
  | `_3z.nc`, experiments 010 / 023 / 026 | 5 | {1 × 10 × 385 × 526} | 8.1 MB | 64: 4 depth groups × 16 tiles |
  | `_2d.nc`, experiment 027 | 6 | {1 × 769 × 1051} | 3.2 MB | 4: 2 × 2 tiles ; chunking changed |
  | `_3z.nc`, experiment 027 | 5 | {1 × 7 × 308 × 421} | 3.6 MB | 150: 6 depth groups × 25 tiles ; chunking changed |

  The coordinates `Latitude`, `Longitude` and `Depth` are stored contiguously. `MT` and `Date`
  are chunked at 512, of which each file uses one element.

- **Horizontal grid: 1/100°.**
  - Longitude runs from 98°W to 77°W in 0.01° steps, **2,101 points**.
  - Latitude runs from 18.09°N to 31.96°N, **1,537 points**. The spacing is 0.0085–0.0095°,
    narrowing northward, which matches HYCOM's Mercator grid (about 0.01° × cos(latitude)).
- **Vertical: 40 fixed depths**, 0 m to 5,000 m: 0, 2, 4, 6, 8, 10, 12, 15, 20, 25, 30, 35, 40,
  45, 50, 60, 70, 80, 90, 100, 125, 150, 200, 250, 300, 350, 400, 500, 600, 700, 800, 900,
  1,000, 1,250, 1,500, 2,000, 2,500, 3,000, 4,000, 5,000. The "41 hybrid layers" on HYCOM's
  product page are the model's own vertical grid. The distributed 3z files are interpolated from
  those layers to these depths, as HYCOM's tutorial notebook also says. A store built from these
  files has 40 depths, not 41 layers.
- **Time: one hour per file**, two files per hour (2d and 3z).
- **Eleven variables**, all float32 and uncompressed, each stored separately:
  - `_2d.nc`: `ssh`, `mixed_layer_thickness`, `u_barotropic_velocity`,
    `v_barotropic_velocity`, `wnd_ewd`, `wnd_nwd`
  - `_3z.nc`: `u`, `v`, `w_velocity`, `water_temp`, `salinity`
- **Sizes.** One horizontal map, meaning one variable at one hour and one depth, is
  1,537 × 2,101 × 4 bytes = **12.9 MB**.
  - A 2d file (77.6 MB) is 6 such maps.
  - A 3z variable at one hour is 40 maps, 516 MB; a 3z file (2.59 GB) is 5 of those.
  - Over 207,000 hours that is about 16 TB of 2d and 539 TB of 3z.

In this report, a **source chunk** is the HDF5 chunk as stored in a file. A **virtual chunk**
is the piece of it that one reference in the store points at. Both are parts of a single
variable at a single hour.

## Store design: what the files allow

The files are
uncompressed, so a virtualized store can reference either a whole source chunk, or any contiguous piece of
one ("the offset trick"). A reference must be one contiguous byte range in one file. So a store
can cut the files' chunks into smaller pieces, but it can never join pieces into a bigger one.
Both were tested end to end, and reading back through Icechunk gave values identical to h5py
(`05_split_and_time.py`). This provides a few decisions regarding how the Icechunk stores are structured. 

### 2d: the whole map, 12.9 MB

Each 2d variable at one hour is a single contiguous 12.9 MB chunk, a good chunk size, and the
store can reference it whole: one reference per variable per hour. Maps and
subsets are cheap. A point time series has to fetch all 12.9 MB for each hour. From S3 that is an
estimated 7 min per variable per year, against 15 s if the maps were cut into 53-row bands (latitude bands). The
band option stays available if point time series turn out to matter (`05_split_and_time.py`
measured both). This decision can be made during performance testing during icechunk creation.

### 3z: one of four options, to be decided by testing

A 12.9 MB chunk holding one depth's full map is **not possible** for 3z. In these HDF5 files one
depth's map is spread over 16 tiles/chunks, and each tile stores its 10 depths together:

```
one tile (1 of 16) on disk:  [depth 0 | depth 1 | ... | depth 9]   8.1 MB
                               810 KB
```

The virtual chunk can be all 10 depths of a tile, or any whole number of depths dividing 10:

| Virtual chunk (per variable, per hour) | Size | References, full record | One depth's map | One point at one depth, per hour |
|---|---|---|---|---|
| {1 × 10 × 385 × 526}, as stored | 8.1 MB | 66 M | 16 reads, 130 MB fetched for 12.9 MB wanted (10×) | 8.1 MB |
| {1 × 5 × 385 × 526} | 4.1 MB | 133 M | 16 reads, 65 MB (5×) | 4.1 MB |
| {1 × 2 × 385 × 526} | 1.6 MB | 332 M | 16 reads, 26 MB (2×) | 1.6 MB |
| {1 × 1 × 385 × 526} | 810 KB | 663 M | 16 reads, 12.9 MB (no waste) | 810 KB |

The trade is data wasted per read against the number of references. 663 M references is 63
times the GOFS 3.1 store, and untested (see
[Reference counts](#reference-counts-compared-with-gofs-31)). Once files are on S3, conduct a one-year test to decide
the icechunk chunking above.

### Other constraints on the design

- **2d and 3z can share one group.** Zarr chunk shapes belong to each variable, so a 2d
  variable at {1 × 1537 × 2101} and a 3z variable at {1 × 1 × 385 × 526} sit side by side on one
  lat, lon and time axis. This was tested with two hours, reading back correctly
  (`08_one_group.py`). The constraint is per variable: one variable needs one chunk grid
  through the whole record. That is the problem with experiment 027, not the difference between
  2d and 3z.
- **Offsets must come from each file's own header.** Most files share identical byte offsets,
  but not all (F4), as in the GOFS 3.1 build. On S3 that scan is cheap: 1 read per 2d file and 6
  per 3z file.
- **The time axis should come from the filenames**, not from `MT` (F11).
- **Pin checksums at build time** (F8).

### Why experiment 027 must be reprocessed

Experiment 027 (`experiment = "02.3"`) has the same grid, variables and 40 depths as the rest,
but it was written with a different chunk grid. When creating a virtualized Zarr store (or Icechunk), the 
variables must share the chunk layout. This constraint may be solved in later versions of VirtualiZarr, but if 
there are no technical reasons to have changed the chunk layout, it is best to return to the 2001-2023 layout. In anycase, for S3 now, the 027 files will need to be reprocessed to have the same chunk layout.

| | 010 / 023 / 026 | 027 |
|---|---|---|
| 2d chunk | {1 × 1537 × 2101} | {1 × 769 × 1051} |
| 3z chunk | {1 × 10 × 385 × 526} | {1 × 7 × 308 × 421} |


Reprocessing involves about 0.3 TB of 2d files and 10 TB of 3z files. Rewrite scripts should be straight-forward. For example `nccopy -c "<chunks>"` with no `-d`. The 027 2d files were also assembled with NCO (`ncks -A` of the winds, `_nc3_strict`), so check
that the variable order and attributes come out consistent.

## Findings

### F1. Byte offsets vary between otherwise identical files

Every file sampled has the same variables, shapes, chunking and codec within its experiment.
The byte offsets, though, differ in some files, because the header's length varies:

- The 3z files of experiments 023 and 026 at 2024-001 are 2,468 bytes longer, because extra
  `valid_range` attributes are stored on the coordinates.
- The 2003 2d file repaired in September 2026 is 12 bytes longer, having been written by a
  different netCDF-C.
- The 2005 3z file repaired in April 2026 is 6,353 bytes shorter.
- Experiment 027's 2d offsets differ even within that experiment.

This is the GOFS 3.1 lesson again: a template taken from one file misplaces data in others.
**Icechunk preperation scripts much scan every file's header+**. `06_header_cost.py` measured the cost: 1 read of 64 KiB per 2d file,
and 6 per 3z file, because each variable's chunk index sits just before its data. For
experiment 027 it is 6 and 17. Over the whole archive that is roughly 1.5 M small reads, which
takes minutes once data are on S3.

### F2. Eighteen 3z files are empty, and six 3z hours are missing

Three runs of six hours in experiment 010 have 3z files of 49 KB (one is 239 bytes). Their data
variables have a time dimension of length **0**:

- 2002-12-13 00–05Z
- 2006-06-26 18–23Z
- 2014-12-01 12–17Z

A further 6 3z hours have no file at all: 2011-05-28 00–05Z. The 2d files exist for all of
these hours. Leave the empty files out of the S3 copy, or skip them in the build; either way,
those 24 hours read as fill values in the 3z store. They are listed in
`out/problem-files.csv`.

### F3. Experiments 026 and 027 overlap for 653 hours

From 2024-04-01 19Z to 2024-04-28 23Z every hour has both a `026_` and a `027_` file, for 2d and
3z. Experiment 026 is version `01.0` and was written in December 2024. Experiment 027 is
version `02.3`, written in September 2025, and runs on to 2024-09-01 18Z. HYCOM should say
which one is authoritative for the overlap. The store can hold only one per hour.

### F4. The record starts 2001-01-16, not 2001-01-01

No file exists before `010_archv.2001_016_00`, although the product page and HYCOM's tutorial
notebook both say 1 January 2001. It ends at 2024-09-01 18Z, not 2024-08-31. In total there are
207,115 hourly 2d times and 207,091 3z times.

### F5. HYCOM is still editing the archive

1,609 2d files (2003-09-27 to 2004-06-01) were rewritten on 4–10 September 2026, and 627 3z
files in March–June 2026. The 2005 3z file sampled from the April batch was produced with
`ncra` from the neighbouring hours: `history` records it, and every variable gained
`cell_methods = "MT: mean"`. It is an interpolated stand-in, not model output. How many of the
627 are like it was not checked.

Two consequences:

1. **The icechunk must be rebuilt when updated files are pushed to S3.** Icechunk has a versioning mechanism.
2. **Build with a checksum pin anyway.** `07_checksum_pin.py` confirmed that Icechunk's
   per-reference checksum works for these files. A store written with
   `to_icechunk(…, last_updated_at=<build time>)` fails with *"the checksum of the object owning
   the virtual chunk has changed"* when a file is newer than the pin, and reads normally
   otherwise. This was tested against data.hycom.org's `Last-Modified`; S3 supplies the same
   header.

The interpolated hours are worth listing in the store's documentation. `cell_methods` or
`history` identifies them without reading any data.

### F6. Stray files in the year directories

- 2016 has sixteen `u.y2016_d300.nc` … `u.y2016_d315.nc` files (493 MB each).
- 2012 has `010_archv.2012_138_00_3z.nc_COPY`.

Neither matches the naming pattern. Leave them out of the S3 copy?

### F7. Smaller inconsistencies (do not block a build)

- **The HDF5 dataset fill value differs.** It is 9.96921e36 in the 027 2d files, the 2026
  repairs and the daily files, and 1.267651e30 elsewhere. The CF `_FillValue` attribute is the
  same float32 value (2^100) in every file sampled, and that attribute is what the store uses.
- **`MT:calendar`** is `gregorian` in 027 and `standard` elsewhere.
- **`Conventions`** is `CF-1.6` in 027 and `CF-1.0` elsewhere.
- **`long_name`** carries the experiment version: `[01.0H]` or `[02.3H]`.

**Make sure to repair the metadata to ensure CF-compliant icechunk stores.** We have scripts and CF-compliance checkers.

### F8. The 3z files store time at reduced precision

For the same hour, `MT` in the 3z file differs from the 2d file's. At 2010-04-10 01Z the 2d file
has 39912.04166667 days, exactly 01:00. The 3z file has 39912.04296875 days, which is 01:01:52:
the value has passed through float32. Experiment 027's 3z files round it to three decimals
instead (45125.208). `Date` shows the same. Latitude and longitude are identical in the two
files. I suggest we build the time axis from the filenames, as the GOFS 3.1 build did, not from each file's
`MT` or determine some other way to get a consistent time. The two agree to the hour (`08_one_group.py`).

## Expected performance from S3

These are estimates until the one-year test runs on the real bucket. The rates come from
ranged GETs to the GOFS 3.1 bucket (S3 us-west-2), from a hub in the same region, with requests
spread over different files (`04b_s3_throughput.py`). At 64 concurrent requests the measured
rates were:

| Request size | Rate |
|---|---|
| 445 KB | about 580 requests/s |
| 810 KB | about 430 requests/s |
| 12.9 MB (a whole map) | about 300 MB/s |

The estimates below are those raw rates. Icechunk's own read path came in at roughly half the
raw rate against data.hycom.org, so allow up to double. Readers outside AWS, or in another
region, will see much less.

| Task (one variable) | 2d, whole map (chosen) | 2d, 53-row bands | 3z, 10 depths per chunk | 3z, 1 depth per chunk |
|---|---|---|---|---|
| point time series, 1 year (8,760 h) | ~7 min (113 GB read) | ~15 s | ~3.5 min (71 GB read) | ~20 s |
| point time series, full record (207k h) | ~2.5 h (2.7 TB read) | ~6 min | ~1.5 h (1.7 TB read) | ~8 min |
| 200 × 200 box, one hour | ~0.3 s | < 0.2 s | < 0.5 s (32 MB read) | < 0.2 s |
| 200 × 200 box, every hour of a year | ~7 min (113 GB read) | ~1 min | ~14 min (280 GB read) | ~1.5 min |
| full map, one hour (one depth for 3z) | < 1 s | < 1 s | ~1 s (130 MB read) | < 1 s |

The box is the one used in every test here: rows 600–800 and columns 1000–1200, 23.7–25.5°N,
88–86°W. In 2d it covers 5 of the 53-row bands. In 3z it straddles 4 tiles,
so the 10-depth chunking fetches 4 × 8.1 MB per hour; a box inside a single tile costs a
quarter of that.

### Reference counts compared with GOFS 3.1

The local test measured 7.3 bytes per reference in the manifests. Its offsets were more regular
than the full archive's will be, so treat the sizes as rough.

| | References, full record | Manifests at ~7 B/ref |
|---|---|---|
| 2d, whole map | 6 × 207k ≈ 1.2 M | ~10 MB |
| 3z, 10 depths per chunk | 5 × 64 × 207k ≈ 66 M | ~0.5 GB |
| 3z, 5 depths per chunk | 5 × 128 × 207k ≈ 133 M | ~1 GB |
| 3z, 2 depths per chunk | 5 × 320 × 207k ≈ 332 M | ~2.4 GB |
| 3z, 1 depth per chunk | 5 × 640 × 207k ≈ 663 M | ~5 GB |

663 M references is 63 times the GOFS 3.1 store (10.45 M). Only a factor of 3.3 of that comes
from hourly rather than 3-hourly output. The rest comes from the file chunking:

| | Time steps | References per time step | Total |
|---|---|---|---|
| GOFS 3.1 | 63,341 (3-hourly) | 165: 4 variables × 40 depths + 5 surface/bottom fields, one per whole global map | 10.45 M |
| GOMb0.01 3z, 1 depth per chunk | 207,091 (hourly) | 3,200: 5 variables × 40 depths × 16 tiles | 663 M |
| GOMb0.01 3z, 10 depths per chunk | 207,091 | 320: 5 variables × 64 source chunks | 66 M |

The GOFS files are NetCDF-3 with no internal chunking, so one depth of one variable is a single
29 MB reference. These files already cut every depth into 16 tiles, and splitting to one depth
per chunk keeps all 16. Nothing this large has been built here, which is what the one-year test
is for.

## Also available: daily means

`data/daily_netcdf/<year>/gomb1_daily_<year>_<doy>_{2d,3z}.nc` holds daily means for every year,
made with `ncra` from the hourly files (weights 0.92 on the two end hours). They share the
hourly files' layout; the 2024 files have experiment 027's chunk grid. With 24 times fewer time
steps, a daily store would make long point time series about 24 times cheaper. It would also
have far fewer references: about 28 M for 3z at one depth per chunk. It is worth considering as a
second store, and the same 027 reprocessing applies to it.

The audit only reads: no file was changed.

## Method

Each numbered script writes to `out/`, and can be re-run from a Python 3.12 venv built from
`requirements.txt` alone. `02`, `06` and `07` were re-run that way.

| Script | What it does | Output |
|---|---|---|
| `01_inventory.py` | the 25 directory listings, one request at a time | `inventory.csv.gz` (415,571 rows) |
| `02_inventory_summary.py` | experiments, coverage, duplicates, gaps, edits, odd names; offline | `inventory-summary.txt`, `problem-files.csv` |
| `03_sample_layouts.py` | HDF5 layout of 45 files: first, middle, last and one random file of each experiment and kind, each 2026 edit batch, an empty file, and four daily files; compared with a 2009 reference | `sample-layouts.txt`, `layout-diffs.txt` |
| `04a_hycom_throughput.py` | data.hycom.org rates at 1, 4 and 8 connections, and the 403 bursts | `hycom-throughput.txt` (recorded, not re-run) |
| `04b_s3_throughput.py` | the same request sizes on S3 (GOFS bucket) | `s3-throughput.txt` |
| `05_split_and_time.py` | a local Icechunk store with split references, values checked against h5py, timed | `split-timing.txt` |
| `06_header_cost.py` | reads needed per file to find every chunk offset | `header-cost.txt` |
| `07_checksum_pin.py` | Icechunk's checksum pin against a real `Last-Modified` | `checksum-pin.txt` |
| `08_one_group.py` | 2d and 3z variables with different chunk shapes in one group, read back and checked | `one-group.txt` |

All reads went to data.hycom.org at 8 or fewer connections, as HYCOM asks. Most were single
requests.

## Limitations

- **Layouts were sampled, not scanned.** 45 files of 415,571 were read. A per-file header scan,
  which the build needs anyway, is the complete check. Run it on S3.
- **The S3 rates are a stand-in.** They come from another bucket, from inside the same AWS
  region; the GOMb0.01 bucket does not exist yet.
- **The Icechunk timings are from data.hycom.org** and vary a lot between runs (the band box
  took 7.5 s in one run and 12.7 s in another).
- **Every full-record figure is an extrapolation.** None of the 3z chunkings has been built
  beyond one hour; the one-year test on S3 is what settles them.
- **The interpolated (ncra) repairs were confirmed in one file only.**
- **The CEFI audit this was modelled on** (noaa-nwfsc/cefi-icechunks#7) was read from a local
  clone. The GitHub CLI token is not authorized for that organization's SSO.

