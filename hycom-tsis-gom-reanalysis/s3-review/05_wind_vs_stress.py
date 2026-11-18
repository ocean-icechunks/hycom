"""Are 028's surface_e_stress/surface_n_stress the same quantity as the wnd_ewd/wnd_nwd of
earlier experiments, under a new name? Compare attributes, the 027 NCO history, and values.

Reads one hour from each of 010, 023, 027 and 028 on S3 (whole 2d variables: 12.9 MB each),
open-water points only, and prints magnitude statistics, plus the 1.2 * 1.3e-3 * |U| * U
bulk-formula check of stress against wind for the same hour.
Writes out/wind-vs-stress.txt when run as  python 05_wind_vs_stress.py | tee out/wind-vs-stress.txt
"""
import sys
import numpy as np

sys.path.insert(0, "../audit")
from common import h5open  # noqa: E402

S3 = "https://hycom-tsis-gom-reanalysis.s3.us-west-2.amazonaws.com/data/"
FILES = {
    "010": "2010/010_archv.2010_032_12_2d.nc",
    "023": "2022/023_archv.2022_032_12_2d.nc",
    "027": "2024/027_archv.2024_200_12_2d.nc",
    "028 (2024)": "2024/028_archv.2024_300_12_2d.nc",
    "028 (2025)": "2025/028_archv.2025_032_12_2d.nc",
}


def stats(a):
    a = a[np.isfinite(a) & (np.abs(a) < 1e20)]
    return f"n={a.size:>8d} mean={a.mean():+8.4f} |mean|={np.abs(a).mean():8.4f} p1={np.percentile(a, 1):+8.4f} p99={np.percentile(a, 99):+8.4f}"


for label, key in FILES.items():
    with h5open(S3 + key) as h:
        print(f"== {label}: {key}")
        if label == "027":
            print("  history:", h.attrs["history"].decode()[:400].replace("\n", " | "))
            print("  appended:", h.attrs["history_of_appended_files"].decode()[:900].replace("\n", " | "))
        for v in ("wnd_ewd", "wnd_nwd", "surface_e_stress", "surface_n_stress"):
            if v in h:
                d = h[v]
                print(f"  {v:17s} units={d.attrs.get('units')} long_name={d.attrs.get('long_name')}")
                print(f"  {'':17s} {stats(d[0].astype('f8'))}")
        if "wnd_ewd" in h:
            u, w = h["wnd_ewd"][0].astype("f8"), h["wnd_nwd"][0].astype("f8")
            ok = np.isfinite(u) & (np.abs(u) < 1e20)
            spd = np.hypot(u, w)[ok]
            print(f"  wind speed: mean={spd.mean():.2f} m/s; bulk stress 1.2*1.3e-3*|U|*U would be |tau| ~ {np.mean(1.56e-3 * spd**2):.4f} Pa")
