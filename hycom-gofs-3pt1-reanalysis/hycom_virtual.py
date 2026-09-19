"""Virtual Icechunk references for the HYCOM GOFS 3.1 reanalysis on AWS Open Data.

The source is 63,341 NetCDF 64-bit-offset (CDF-2) files, one 3-hourly time step each,
holding uncompressed big-endian int16 arrays. Nothing here reads a science array. Each
file gives up its header and its `time`/`tau` values in one small ranged GET, every file
is checked against the others, and the byte range of every depth level is then computed
from that file's own header.

Why offsets are never reused between files: the archive has two header layouts 40 bytes
apart (older files spell four standard names `..._at_bottom`), and they are mixed within
experiments. A template built from one file misplaces the data in the other kind.

Shared by the smoke-test and production notebooks so both build the store the same way.
"""

from __future__ import annotations

import hashlib
import json
import re
import struct
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
import xarray as xr

BUCKET = "hycom-gofs-3pt1-reanalysis"
REGION = "us-west-2"
# The prefix written into every virtual reference. Must end in "/".
URL_PREFIX = f"https://{BUCKET}.s3.{REGION}.amazonaws.com/"

FREQ = "3h"
EPOCH = pd.Timestamp("2000-01-01")  # the source's `hours since 2000-01-01 00:00:00`
# Enough to cover the header, the coordinate arrays and `time`/`tau` in either layout.
HEADER_BYTES = 67_000

VARS_4D = ["water_u", "water_v", "water_temp", "salinity"]
VARS_2D = ["water_u_bottom", "water_v_bottom", "water_temp_bottom", "salinity_bottom", "surf_el"]
SCIENCE_VARS = VARS_4D + VARS_2D

TITLE = "HYCOM GOFS 3.1 Global Ocean Reanalysis, GLBv0.08 expt_53.X, 3-hourly, 1994–2015"
EXPERIMENT_ID = "GLBv0.08 expt_53.X"

_FNAME = re.compile(r"hycom_GLBv0\.08_(\d{3})_(\d{10})_t(\d{3})\.nc$")


# --------------------------------------------------------------------- discovery

def source_store():
    """Anonymous obstore handle on the source bucket (listing and header reads)."""
    from obstore.store import S3Store

    return S3Store(BUCKET, region=REGION, skip_signature=True)


def list_files(store, prefix: str | None = None) -> pd.DataFrame:
    """List the bucket. One row per NetCDF file, indexed and sorted by valid time.

    Valid time is the run date (always 12Z) plus the forecast hour in the filename. It is
    used for discovery only; `check_scan` later requires the time stored in each file to
    agree with it.
    """
    import obstore

    rows = []
    for batch in obstore.list(store, prefix=prefix, chunk_size=1000):
        for obj in batch:
            m = _FNAME.search(obj["path"])
            if m is None:
                continue  # the bucket holds one zero-byte "2015/" placeholder key
            expt, run, tau = m.groups()
            run = pd.to_datetime(run, format="%Y%m%d%H")
            rows.append(
                dict(key=obj["path"], size=obj["size"], experiment=int(expt),
                     tau=int(tau), time=run + pd.Timedelta(hours=int(tau)))
            )
    files = pd.DataFrame(rows).set_index("time").sort_index()
    if files.index.has_duplicates:
        raise ValueError(f"duplicate valid times: {files.index[files.index.duplicated()][:5].tolist()}")
    return files


# ------------------------------------------------------------ NetCDF-3 header

_NC_TYPES = {1: ("i1", 1), 2: ("S1", 1), 3: (">i2", 2), 4: (">i4", 4), 5: (">f4", 4), 6: (">f8", 8)}


class _Reader:
    def __init__(self, buf: bytes):
        self.buf, self.pos = buf, 0

    def i4(self) -> int:
        (v,) = struct.unpack_from(">i", self.buf, self.pos)
        self.pos += 4
        return v

    def i8(self) -> int:
        (v,) = struct.unpack_from(">q", self.buf, self.pos)
        self.pos += 8
        return v

    def name(self) -> str:
        n = self.i4()
        v = self.buf[self.pos:self.pos + n].decode()
        self.pos += (n + 3) // 4 * 4
        return v

    def values(self, nc_type: int, n: int):
        dtype, size = _NC_TYPES[nc_type]
        raw = self.buf[self.pos:self.pos + n * size]
        self.pos += (n * size + 3) // 4 * 4
        if nc_type == 2:
            return raw.decode("latin1")
        arr = np.frombuffer(raw, dtype)
        return arr[0] if n == 1 else arr  # keeps the source dtype (float32 scale_factor)

    def attrs(self) -> dict:
        self.i4()  # NC_ATTRIBUTE tag, or 0 when absent
        out = {}
        for _ in range(self.i4()):
            key = self.name()
            nc_type, n = self.i4(), self.i4()
            out[key] = self.values(nc_type, n)
        return out


def parse_header(buf: bytes) -> dict:
    """Parse a NetCDF classic (CDF-1) or 64-bit-offset (CDF-2) header.

    Returns dims, global attributes and, per variable, its dims, shape, dtype, attributes,
    `vsize` and `begin` — the absolute byte offset of its data. Reads no data.
    """
    if buf[:3] != b"CDF" or buf[3] not in (1, 2):
        raise ValueError(f"not a NetCDF-3 file: magic {buf[:4]!r}")
    version = buf[3]
    r = _Reader(buf)
    r.pos = 4
    numrecs = r.i4()
    r.i4()  # NC_DIMENSION tag
    dims = [(r.name(), r.i4()) for _ in range(r.i4())]
    gattrs = r.attrs()
    r.i4()  # NC_VARIABLE tag
    variables = {}
    for _ in range(r.i4()):
        name = r.name()
        dimids = [r.i4() for _ in range(r.i4())]
        attrs = r.attrs()
        nc_type, vsize = r.i4(), r.i4()
        begin = r.i8() if version == 2 else r.i4()
        variables[name] = dict(
            dims=[dims[i][0] for i in dimids],
            # the record dimension has length 0 in the header; its real length is numrecs
            shape=[dims[i][1] or numrecs for i in dimids],
            dtype=_NC_TYPES[nc_type][0], vsize=vsize, begin=begin, attrs=attrs,
        )
    return dict(version=version, numrecs=numrecs, dims=dims, attrs=gattrs,
                variables=variables, header_len=r.pos)


def _jsonable(x):
    if isinstance(x, np.ndarray):
        return x.tolist()
    if isinstance(x, np.generic):
        return x.item()
    return x


def _schema_fingerprint(header: dict) -> str:
    """Hash of everything that must be identical in every file.

    Left out, because they legitimately vary: byte offsets (`begin`); `tau:time_origin`,
    which is the run date; and the four bottom `standard_name`s, whose spelling is the
    whole difference between the two header layouts.
    """
    skip = {("tau", "time_origin")} | {(v, "standard_name") for v in VARS_2D if v.endswith("_bottom")}
    doc = dict(
        version=header["version"], numrecs=header["numrecs"], dims=header["dims"],
        attrs={k: _jsonable(v) for k, v in header["attrs"].items()},
        variables={
            name: dict(dims=v["dims"], shape=v["shape"], dtype=v["dtype"], vsize=v["vsize"],
                       attrs={k: _jsonable(a) for k, a in v["attrs"].items() if (name, k) not in skip})
            for name, v in header["variables"].items()
        },
    )
    return hashlib.md5(json.dumps(doc, sort_keys=True).encode()).hexdigest()


# ------------------------------------------------------------------ header scan

def read_header(store, key: str) -> tuple[dict, bytes]:
    import obstore

    buf = bytes(obstore.get_range(store, key, start=0, length=HEADER_BYTES))
    return parse_header(buf), buf


def _scan_one(store, key: str) -> dict:
    header, buf = read_header(store, key)
    v = header["variables"]
    if v["tau"]["begin"] + 8 > len(buf):
        raise ValueError(f"{key}: time/tau lie beyond the {HEADER_BYTES} bytes fetched")
    (time_hours,) = struct.unpack_from(">d", buf, v["time"]["begin"])
    (tau_hours,) = struct.unpack_from(">d", buf, v["tau"]["begin"])
    last = max(v.values(), key=lambda x: x["begin"])
    row = dict(
        key=key, header_len=header["header_len"], numrecs=header["numrecs"],
        schema=_schema_fingerprint(header),
        coords_md5=hashlib.md5(buf[v["depth"]["begin"]:v["time"]["begin"]]).hexdigest(),
        time_in_file=EPOCH + pd.Timedelta(hours=time_hours), tau_in_file=tau_hours,
        implied_size=last["begin"] + last["vsize"],
    )
    row.update({f"begin_{name}": v[name]["begin"] for name in SCIENCE_VARS})
    return row


def scan_headers(store, files: pd.DataFrame, max_workers: int = 64, attempts: int = 4) -> pd.DataFrame:
    """One ranged GET per file. Returns per-file offsets and the facts `check_scan` needs.

    Tens of thousands of requests will meet the odd dropped connection, so a failed read is
    retried. A file that still fails raises: a header we could not read is never guessed.
    """
    import time

    def one(key: str) -> dict:
        for attempt in range(attempts):
            try:
                return _scan_one(store, key)
            except ValueError:
                raise  # the file itself is wrong; retrying will not help
            except Exception:
                if attempt == attempts - 1:
                    raise
                time.sleep(2 ** attempt)

    with ThreadPoolExecutor(max_workers) as pool:
        rows = list(pool.map(one, files["key"]))
    return pd.DataFrame(rows, index=files.index)


def check_scan(files: pd.DataFrame, scan: pd.DataFrame) -> None:
    """Refuse to build unless every file agrees with every other. Raises with the offenders.

    - one record per file, so each variable is a single contiguous byte range;
    - one schema (dims, shapes, dtypes, attributes) and byte-identical coordinates;
    - the file size implied by the header equals the size S3 reports;
    - the time and tau stored in the file equal the ones in its filename.
    """
    problems = {
        "numrecs != 1": scan["numrecs"] != 1,
        "schema differs from the first file": scan["schema"] != scan["schema"].iloc[0],
        "coordinates differ from the first file": scan["coords_md5"] != scan["coords_md5"].iloc[0],
        "header-implied size != S3 size": scan["implied_size"] != files["size"],
        "time in file != time in filename": scan["time_in_file"] != scan.index,
        "tau in file != tau in filename": scan["tau_in_file"] != files["tau"],
    }
    bad = {k: scan.loc[m, "key"].tolist() for k, m in problems.items() if m.any()}
    if bad:
        lines = [f"{k}: {len(v)} file(s), e.g. {v[:3]}" for k, v in bad.items()]
        raise ValueError("source files are not homogeneous:\n  " + "\n  ".join(lines))


# ------------------------------------------------------------------- metadata

# Metadata-only repairs for CF compliance. Standard names were checked against CF
# standard-name table v94 and the units against UDUNITS. No array value changes.
CF_REPAIRS = {
    "water_u_bottom": {"standard_name": "eastward_sea_water_velocity_at_sea_floor"},
    "water_v_bottom": {"standard_name": "northward_sea_water_velocity_at_sea_floor"},
    # CF-1.11 s3.1.2: say whether a temperature is a point on the scale or a difference
    "water_temp": {"units_metadata": "temperature: on_scale"},
    "water_temp_bottom": {"standard_name": "sea_water_temperature_at_sea_floor",
                          "units_metadata": "temperature: on_scale"},
    "salinity": {"standard_name": "sea_water_salinity", "long_name": "Sea Water Salinity",
                 "units": "1e-3", "source_units": "psu"},
    "salinity_bottom": {"standard_name": "sea_water_salinity_at_sea_floor",
                        "long_name": "Sea Water Salinity at Sea Floor",
                        "units": "1e-3", "source_units": "psu"},
    # `sea_surface_elevation` is only an alias in the CF table
    "surf_el": {"standard_name": "sea_surface_height_above_geoid"},
}


def science_attrs(header: dict, name: str) -> tuple[dict, dict]:
    """(attrs, encoding) for one science variable: the source's, plus `CF_REPAIRS`."""
    attrs = dict(header["variables"][name]["attrs"])
    encoding = {k: attrs.pop(k) for k in ("_FillValue", "scale_factor", "add_offset")}
    attrs.update(CF_REPAIRS.get(name, {}))
    return {k: _jsonable(v) for k, v in attrs.items()}, encoding


def global_attrs(header: dict) -> dict:
    attrs = {k: _jsonable(v) for k, v in header["attrs"].items()}
    attrs.update(
        title=TITLE,
        experiment_id=EXPERIMENT_ID,
        Conventions="CF-1.11",
        source_Conventions=attrs["Conventions"],
        references="https://www.hycom.org/dataserver/gofs-3pt1/reanalysis "
                   "https://registry.opendata.aws/hycom-gofs-3pt1-reanalysis/",
        source_data=f"s3://{BUCKET} ({REGION}), NetCDF 64-bit offset, one file per time step",
        comment="Virtual Icechunk store: Zarr metadata and byte-range references only. The "
                "arrays stay in the source NetCDF files and are read from there. Time steps "
                "with no source file are present on the time axis and read as missing; "
                "`tau` is NaN and `experiment` is 0 at those steps.",
    )
    return attrs


# ---------------------------------------------------------------- the dataset

def time_axis(files: pd.DataFrame) -> pd.DatetimeIndex:
    """The regular 3-hourly axis spanning `files`, including the steps that have no file."""
    return pd.date_range(files.index.min(), files.index.max(), freq=FREQ)


def _coords(header: dict, buf: bytes) -> dict:
    out = {}
    for name in ("depth", "lat", "lon"):
        v = header["variables"][name]
        values = np.frombuffer(buf, v["dtype"], count=v["shape"][0], offset=v["begin"]).astype("f8")
        out[name] = xr.Variable(name, values, {k: _jsonable(a) for k, a in v["attrs"].items()},
                                # CF s2.5.1: a coordinate variable must not have a _FillValue
                                encoding={"_FillValue": None})
    return out


def loaded_variables(files: pd.DataFrame, header: dict, buf: bytes, times: pd.DatetimeIndex) -> xr.Dataset:
    """Everything that is materialized: the coordinates, including `tau` and `experiment`."""
    present = files.reindex(times)
    time = xr.Variable("time", times, {"long_name": "Valid Time", "axis": "T", "standard_name": "time",
                                       "units_metadata": "leap_seconds: unknown"})  # CF-1.11 s4.4
    # One chunk for the whole axis: the default would write one tiny chunk per time step.
    time.encoding = {"units": "hours since 2000-01-01 00:00:00", "calendar": "standard",
                     "dtype": "float64", "chunks": (len(times),), "_FillValue": None}
    tau = xr.Variable("time", present["tau"].to_numpy("f8"), {
        "long_name": "Tau: hours since the analysis that this time step was run from",
        "standard_name": "forecast_period", "units": "hours",
        "NAVO_code": _jsonable(header["variables"]["tau"]["attrs"]["NAVO_code"]),
        "comment": "0 is the analysis, 3-21 are forecast hours. NaN where the archive has no "
                   "file for this time step, so `tau.notnull()` selects the steps that exist.",
    })
    tau.encoding = {"chunks": (len(times),), "_FillValue": np.nan}
    expts = sorted(files["experiment"].unique())
    experiment = xr.Variable("time", present["experiment"].fillna(0).to_numpy("i2"), {
        "long_name": "HYCOM experiment the source file came from (53.X written 53X, as in the filenames)",
        "flag_values": np.array([0] + expts, "i2"),
        "flag_meanings": " ".join(["no_source_file"] + [f"expt_{e // 10}.{e % 10}" for e in expts]),
    })
    experiment.encoding = {"chunks": (len(times),), "_FillValue": None}
    # Auxiliary coordinates along `time`, which is how CF treats a forecast period: they
    # then travel with every variable, so `da.tau` works on a DataArray on its own.
    return xr.Dataset(coords={"time": time, **_coords(header, buf), "tau": tau, "experiment": experiment})


def _manifest_array(name: str, header: dict, files: pd.DataFrame, scan: pd.DataFrame,
                    times: pd.DatetimeIndex):
    """One science variable as a ManifestArray: one chunk per (time, depth level).

    Uncompressed C-order data means a level is a contiguous byte range, so the chunk for
    level k of a file starts at `begin + k * level_bytes`. Steps with no file get no
    reference at all and read back as the fill value.
    """
    from virtualizarr.manifests import ChunkManifest, ManifestArray
    from virtualizarr.manifests.utils import create_v3_array_metadata

    v = header["variables"][name]
    dims, (ny, nx) = v["dims"], v["shape"][-2:]
    nz = v["shape"][1] if len(dims) == 4 else 1
    level_bytes = ny * nx * np.dtype(v["dtype"]).itemsize
    assert v["vsize"] == nz * level_bytes, (name, v["vsize"], nz, level_bytes)

    nt = len(times)
    where = times.get_indexer(files.index)  # row of each file on the regular axis
    assert (where >= 0).all()
    paths = np.full((nt, nz), "", dtype=np.dtypes.StringDType())
    offsets = np.zeros((nt, nz), "uint64")
    lengths = np.zeros((nt, nz), "uint64")
    paths[where, :] = (URL_PREFIX + files["key"]).to_numpy(str)[:, None]
    offsets[where, :] = (scan[f"begin_{name}"].to_numpy("uint64")[:, None]
                         + np.arange(nz, dtype="uint64")[None, :] * np.uint64(level_bytes))
    lengths[where, :] = level_bytes

    grid = (nt, nz, 1, 1) if len(dims) == 4 else (nt, 1, 1)
    attrs, encoding = science_attrs(header, name)
    metadata = create_v3_array_metadata(
        shape=(nt, *v["shape"][1:]),
        chunk_shape=(1, 1, ny, nx) if len(dims) == 4 else (1, ny, nx),
        # Zarr v3 dtypes carry no byte order; the `bytes` codec does. Declaring ">i2" here
        # instead makes VirtualiZarr 2.7.3 refuse every later region/append write with
        # "inconsistent dtypes: int16 vs >i2", because the array reopens as native int16.
        data_type=np.dtype(v["dtype"]).newbyteorder("="),
        codecs=[{"name": "bytes", "configuration": {"endian": "big"}}],  # no compressor
        fill_value=_jsonable(encoding["_FillValue"]),
        dimension_names=dims,
    )
    manifest = ChunkManifest.from_arrays(
        paths=paths.reshape(grid), offsets=offsets.reshape(grid), lengths=lengths.reshape(grid))
    return xr.Variable(dims, ManifestArray(metadata=metadata, chunkmanifest=manifest),
                       attrs=attrs, encoding={k: _jsonable(x) for k, x in encoding.items()})


def virtual_variables(files: pd.DataFrame, scan: pd.DataFrame, header: dict,
                      times: pd.DatetimeIndex) -> xr.Dataset:
    """The nine science variables over `times`, referencing whichever of `files` fall in it."""
    inside = (files.index >= times[0]) & (files.index <= times[-1])
    files, scan = files[inside], scan[inside]
    return xr.Dataset({name: _manifest_array(name, header, files, scan, times) for name in SCIENCE_VARS})


# ------------------------------------------------------------------ icechunk

def repository_config(time_chunks_per_manifest: int = 2920):
    """Repository config: the virtual chunk container, and manifests split along time.

    2920 time steps is one non-leap year. It is a starting point to be measured, not a
    constant; it partitions Icechunk's own metadata and does nothing to the source chunks.
    """
    import icechunk

    config = icechunk.RepositoryConfig.default()
    config.set_virtual_chunk_container(
        icechunk.VirtualChunkContainer(url_prefix=URL_PREFIX, store=icechunk.http_store()))
    config.manifest = icechunk.ManifestConfig(
        splitting=icechunk.ManifestSplittingConfig.from_dict({
            icechunk.ManifestSplitCondition.AnyArray(): {
                icechunk.ManifestSplitDimCondition.DimensionName("time"): time_chunks_per_manifest}
        })
    )
    return config


def reader_authorization():
    """What a reader passes as `authorize_virtual_chunk_access`: anonymous HTTPS."""
    import icechunk

    return {URL_PREFIX: icechunk.credentials.HttpAccess}
