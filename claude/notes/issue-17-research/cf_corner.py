"""Run: python -I cf_corner.py <out_dir> <dir with topo/regional.{depth,mask}.nc>, then
compliance-checker -t cf:1.11 -c normal -v <out_dir>/{source,repaired}.nc  (6.1.0: repaired passes, 2026-11-19).

CF check of the plan's repairs (issue #17): a 2-hour, 2-depth, 4x4 corner of real 2022 data,
written (1) with the source attributes as HYCOM has them and (2) with repairs R1-R18 applied."""
import sys, numpy as np, pandas as pd, xarray as xr, fsspec, h5py
OUT, TOPO = sys.argv[1], sys.argv[2]
P = "https://hycom-tsis-gom-reanalysis.s3.us-west-2.amazonaws.com/data/2022/023_archv.2022_100_"
HOURS = ["12", "13"]; Y, X, Z = slice(800, 804), slice(1000, 1004), slice(0, 2)
INTERNAL = {"_Netcdf4Coordinates", "_Netcdf4Dimid", "CLASS", "NAME", "DIMENSION_LIST", "REFERENCE_LIST", "_FillValue"}
def attrs(d):
    out = {}
    for k, v in d.attrs.items():
        if k in INTERNAL: continue
        out[k] = v.decode() if isinstance(v, bytes) else (v.tolist() if getattr(v, "ndim", 0) else v)
    return out
data, vattrs, coords = {}, {}, {}
for h in HOURS:
    for kind in ("2d", "3z"):
        with fsspec.open(P + h + "_" + kind + ".nc", "rb", block_size=2**20) as fh, h5py.File(fh) as f:
            gattrs = {k: (v.decode() if isinstance(v, bytes) else v) for k, v in f.attrs.items()}
            for n, d in f.items():
                if n in ("MT", "Date", "Latitude", "Longitude", "Depth"):
                    coords[n] = (d[:], attrs(d)); continue
                a = d[0, Z, Y, X] if d.ndim == 4 else d[0, Y, X]
                data.setdefault(n, []).append(a); vattrs[n] = (attrs(d), d.ndim)
lat = coords["Latitude"][0][Y]; lon = coords["Longitude"][0][X]; dep = coords["Depth"][0][Z]
t = pd.to_datetime(["2022-04-10 12:00", "2022-04-10 13:00"]); ep = pd.Timestamp("1900-12-31")
mt = ((t - ep) / pd.Timedelta("1D")).to_numpy("f8"); date = np.array([20220410 + 12/24, 20220410 + 13/24])
topo = {n: xr.open_dataset(f"{TOPO}/regional.{f}.nc", engine="scipy", decode_times=False)[n].values[Y, X]
        for n, f in [("bathy", "depth"), ("mask", "mask")]}
FILL = np.float32(1.267651e30)

def build(repaired):
    c = {k: dict(v[1]) for k, v in coords.items()}
    if repaired:
        c["MT"]["standard_name"] = "time"                                   # R2
        c["MT"]["units_metadata"] = "leap_seconds: unknown"                 # R19 (CF-1.11 s4.4, as GOFS)
        c["Date"].pop("units"); c["Date"]["source_units"] = "day as %Y%m%d.%f"   # R4
        c["Date"]["long_name"] = "date (YYYYMMDD.fraction of day)"
        c["Latitude"]["long_name"] = "Latitude"; c["Longitude"]["long_name"] = "Longitude"  # R6
    ds = xr.Dataset(coords={
        "MT": ("MT", mt, c["MT"]), "Depth": ("Depth", dep, c["Depth"]),
        "Latitude": ("Latitude", lat, c["Latitude"]), "Longitude": ("Longitude", lon, c["Longitude"]),
        "Date": ("MT", date, c["Date"])})
    for n, arrs in data.items():
        a, nd = dict(vattrs[n][0]), vattrs[n][1]
        if repaired:
            a.pop("valid_range", None)                                       # R7
            a.pop("coordinates", None)    # R20: xarray writes it from the dataset coords (Date, experiment)
            if n == "ssh": a["standard_name"] = "sea_surface_height_above_geoid"   # R9
            if n == "salinity": a.update(units="1e-3", source_units="psu", long_name="Sea Water Salinity")  # R10
            if n == "water_temp": a["units_metadata"] = "temperature: on_scale"   # R11
        dims = ("MT", "Depth", "Latitude", "Longitude") if nd == 4 else ("MT", "Latitude", "Longitude")
        ds[n] = (dims, np.stack(arrs), a); ds[n].encoding = {"_FillValue": FILL}
    if repaired:
        ds["experiment"] = ("MT", np.array([23, 23], "i2"), {"long_name": "HYCOM experiment the source file came from",
            "flag_values": np.array([0, 10, 23, 26], "i2"),
            "flag_meanings": "no_source_file expt_010 expt_023 expt_026"})   # R12
        ds = ds.set_coords("experiment")
        ds["bathy"] = (("Latitude", "Longitude"), topo["bathy"], {"long_name": "Depth for the GOMb0.01 HYCOM grid",
            "units": "m", "positive": "down", "standard_name": "sea_floor_depth_below_geoid", "comment": "0 on land"})  # R13
        ds["mask"] = (("Latitude", "Longitude"), topo["mask"].astype("i1"), {"long_name": "Mask for the GOMb0.01 HYCOM grid",
            "standard_name": "sea_binary_mask", "flag_values": np.array([0, 1], "i1"), "flag_meanings": "land sea"})  # R14
        ds.attrs = dict(gattrs); ds.attrs.pop("_NCProperties", None)        # R17
        ds.attrs.update(Conventions="CF-1.11", source_Conventions="CF-1.0",                     # R15
                        title="HYCOM-TSIS GOMb0.01 Gulf of Mexico reanalysis, hourly", source_title="HYCOM",  # R16
                        references="https://www.hycom.org/data/gomb0pt01/gom-reanalysis",
                        source_data="s3://hycom-tsis-gom-reanalysis (us-west-2), NetCDF-4",
                        comment="Virtual Icechunk store (CF check corner).")  # R18
    else:
        ds.attrs = {k: v for k, v in gattrs.items() if k != "_NCProperties"}
    for v in ("MT", "Depth", "Latitude", "Longitude", "Date"):
        ds[v].encoding["_FillValue"] = None                                  # R5 (and as xarray would otherwise add)
    return ds
for name, rep in [("source", False), ("repaired", True)]:
    ds = build(rep); p = f"{OUT}/{name}.nc"; ds.to_netcdf(p); print("wrote", p)
