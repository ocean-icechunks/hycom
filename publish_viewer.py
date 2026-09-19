#!/usr/bin/env python3
"""Build the gridlook browser viewer and publish it beside the HYCOM Icechunk stores.

gridlook (https://github.com/eeholmes/gridlook, a fork of
https://github.com/d70-t/gridlook) is a WebGL viewer for cloud-hosted Zarr and
Icechunk stores. Its production build is a folder of plain static files with
relative paths, so it runs from any prefix that serves files over HTTPS. The
store to open goes in the URL *fragment* (after ``#``), which the host never
sees, so one build serves any store::

    https://data.source.coop/ocean-icechunks/hycom/viewer/index.html#icechunk+https://data.source.coop/ocean-icechunks/hycom/hycom-gofs-3pt1-reanalysis::varname=water_temp

Same script as in https://github.com/fish-pace/icechunks, with this repo's
``PRODUCTS``. What Source Cooperative needs from a static site (checked there
2026-09-17): content types are served as uploaded and never inferred, so they
are set explicitly here; there is no directory index, so links name
``index.html``; and the edge 403s the default ``Python-urllib`` User-Agent.

The GOFS 3.1 reanalysis will NOT draw in an ordinary browser
------------------------------------------------------------
A virtual store needs CORS on two hosts: the repository (Source Cooperative,
wide open) and wherever the referenced bytes live. The HYCOM bucket,
``hycom-gofs-3pt1-reanalysis.s3.us-west-2.amazonaws.com``, answers a ranged GET
with 206 and **no** ``Access-Control-Allow-Origin``, and its OPTIONS preflight
is 403 (checked 2026-09-18). So the viewer loads, lists the variables and draws
the coordinates -- real chunks in the Icechunk repository -- and the browser
then blocks every science array.

Nothing published here can waive that: CORS is enforced by the browser. The
fix is a CORS policy on the bucket, which only its owner (COAPS /
help@hycom.org) can apply; no rebuild would be needed. Until then the viewer
works for anyone running a CORS-disabling browser extension.

Also expect it to be slow: every frame is one whole 29 MB level, fetched from
us-west-2, because the source files are unchunked.

Usage
-----
    git clone https://github.com/eeholmes/gridlook ~/gridlook && (cd ~/gridlook && npm ci)
    python publish_viewer.py --product hycom-test --build ~/gridlook --dry-run
    python publish_viewer.py --product hycom-test --build ~/gridlook

``--product`` is required, so nothing is uploaded anywhere by default. Build
once and pass ``--dist`` for the next product. ``--prune`` deletes objects under
the viewer prefix that the new build lacks, and never touches anything outside
it. The build is ``vite build --sourcemap false`` with a capped heap, because
``npm run build`` adds ``vue-tsc`` and source maps and is OOM-killed on a small
machine.

Credentials: the short-lived Source Cooperative token, through
``icechunk_utils.get_source_credentials``. Log in first::

    source-coop login --duration 1d --port 8400
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from icechunk_utils import get_source_credentials

PUBLIC = "https://data.source.coop"

# One viewer build serves every HYCOM store: the store rides in the URL fragment. Add a
# dataset here and it appears in both viewers' links and in the dataset picker.
# `view` opens on the first time step at the surface. No camera position: these grids are
# global, so gridlook's default framing is as good as a computed one. To set one, drag the
# globe and copy `px/py/alt/lat/lon` out of the address bar.
DATASETS = {
    "hycom-gofs-3pt1-reanalysis": "HYCOM GOFS 3.1 Global Ocean Reanalysis, GLBv0.08 expt_53.X",
}
_VIEW = "dimIndices_time=0::dimIndices_depth=0"
# Offered as links for every store. They are the GOFS 3.1 names; a dataset with different
# variables is still reachable through the viewer's own variable picker.
_VARIABLES = ("water_temp", "salinity", "surf_el", "water_u", "water_v")


def _product(root: str, title: str) -> dict:
    return {
        "bucket": "ocean-icechunks",
        "viewer_prefix": f"{root}/viewer",
        "stores": {name: {"url": f"{PUBLIC}/ocean-icechunks/{root}/{name}", "title": label, "view": _VIEW}
                   for name, label in DATASETS.items()},
        "variables": _VARIABLES,
        # Without this the published viewer offers gridlook's 70 demo datasets.
        "catalog": {"path": "static/catalog-extended.json", "title": title},
    }


# `hycom-test` is the scratch area the smoke-test notebooks write to; `hycom` holds the
# published stores. Same layout under each root.
PRODUCTS = {
    "hycom-test": _product("test-repo/hycom", "HYCOM - smoke tests"),
    "hycom": _product("hycom", "HYCOM virtual Icechunk stores"),
}
DEFAULT_DIST = Path("/tmp/gridlook-dist")

# Browsers refuse ES modules served with the wrong type, and refuse to
# stream-compile wasm unless it is application/wasm. Do not rely on the
# platform's mimetypes table for these.
CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript",
    ".mjs": "text/javascript",
    ".css": "text/css",
    ".json": "application/json",
    ".geojson": "application/geo+json",
    ".wasm": "application/wasm",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".ttf": "font/ttf",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".ico": "image/x-icon",
    ".txt": "text/plain; charset=utf-8",
}


def _stores(product: dict) -> dict[str, dict[str, str]]:
    """Normalize `stores` / `store_url` to {label: {url, title, view}}."""
    raw = product.get("stores") or {"": product["store_url"]}
    out = {}
    for label, entry in raw.items():
        if isinstance(entry, str):
            entry = {"url": entry}
        out[label] = {"title": label, "view": "", **entry}
    return out


def store_fragment(entry: dict, var: str | None = None) -> str:
    """The part after `#`: the store, an optional variable, then the view."""
    name = f"::varname={var}" if var else ""
    view = f"::{entry['view']}" if entry.get("view") else ""
    return f"icechunk+{entry['url']}{name}{view}"


def viewer_urls(product: dict, prefix: str) -> dict[str, str]:
    """One link per store, or per store and variable if the product names any."""
    base = f"{PUBLIC}/{product['bucket']}/{prefix}/index.html"
    variables = product.get("variables")
    stores = _stores(product)
    if not variables:
        return {label: f"{base}#{store_fragment(entry)}"
                for label, entry in stores.items()}
    return {
        f"{label} {var}".strip(): f"{base}#{store_fragment(entry, var)}"
        for label, entry in stores.items()
        for var in variables
    }


def write_catalog(product: dict, dist: Path) -> str | None:
    """Replace gridlook's default catalog with one listing only this product.

    gridlook reads `static/catalog-extended.json` on load and offers its entries
    in the dataset picker. Its shipped copy is 70 unrelated demo datasets, which
    is noise beside a single product. Each published viewer therefore gets a
    catalog of its own stores instead.

    Written into the build output, never into the gridlook checkout: the
    checkout stays clean, every build stays traceable to a gridlook commit
    (`build-info.json`), and no other product's viewer is affected.

    A catalog entry's `url` becomes the location hash verbatim, so it carries
    the variable and the opening view with it.
    """
    spec = product.get("catalog")
    if not spec:
        return None
    variables = product.get("variables")
    var = variables[0] if variables else None
    catalog = {
        "type": "gridlook_catalog",
        "title": spec["title"],
        "datasets": [
            {
                "title": entry["title"],
                "url": store_fragment(entry, var),
                "format": "Icechunk",
                "access": "direct",
                "grid": "regular",
                "crs": "EPSG:4326",
            }
            for entry in _stores(product).values()
        ],
    }
    path = dist / spec["path"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(catalog, indent=2) + "\n")
    return spec["path"]


def build(gridlook: Path, dist: Path) -> None:
    gridlook = gridlook.expanduser().resolve()
    if not (gridlook / "package.json").exists():
        sys.exit(f"{gridlook} is not a gridlook checkout (no package.json)")
    if not (gridlook / "node_modules").exists():
        subprocess.run(["npm", "ci"], cwd=gridlook, check=True)
    env = dict(os.environ, NODE_OPTIONS="--max-old-space-size=1500")
    cmd = ["npx", "vite", "build", "--outDir", str(dist), "--emptyOutDir",
           "--sourcemap", "false"]
    print("$", " ".join(cmd), f"  (in {gridlook})")
    subprocess.run(cmd, cwd=gridlook, env=env, check=True)
    write_build_info(gridlook, dist)


def write_build_info(gridlook: Path, dist: Path) -> None:
    """Record which gridlook commit is live, so the published copy is traceable."""
    def git(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=gridlook, capture_output=True,
                              text=True).stdout.strip()
    info = {
        "gridlook_remote": git("remote", "get-url", "origin"),
        "gridlook_commit": git("rev-parse", "HEAD"),
        "gridlook_dirty": bool(git("status", "--porcelain", "--untracked-files=no")),
        "built_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    (dist / "build-info.json").write_text(json.dumps(info, indent=2) + "\n")


def plan(dist: Path) -> list[tuple[Path, str, str, str]]:
    """(local file, relative key, content type, cache control) for every file."""
    if not (dist / "index.html").exists():
        sys.exit(f"{dist} has no index.html -- build first (--build)")
    rows = []
    for path in sorted(p for p in dist.rglob("*") if p.is_file()):
        rel = path.relative_to(dist).as_posix()
        ctype = (CONTENT_TYPES.get(path.suffix.lower())
                 or mimetypes.guess_type(path.name)[0]
                 or "application/octet-stream")
        if rel == "index.html":
            cache = "no-cache"
        elif rel.startswith("assets/"):
            cache = "public, max-age=31536000, immutable"
        else:
            cache = "public, max-age=300"
        rows.append((path, rel, ctype, cache))
    return rows


def s3_client():
    import boto3

    creds, expiration = get_source_credentials()
    print(f"  Source Cooperative token valid until {expiration.isoformat()}")
    return boto3.client(
        "s3",
        endpoint_url=creds["endpoint_url"],
        region_name=creds["region_name"],
        aws_access_key_id=creds["aws_access_key_id"],
        aws_secret_access_key=creds["aws_secret_access_key"],
        aws_session_token=creds.get("aws_session_token"),
    )


def upload(rows, bucket: str, prefix: str, prune: bool) -> None:
    s3 = s3_client()
    # Assets first, index.html last: a visitor never gets a page whose assets
    # are not up yet.
    for path, rel, ctype, cache in sorted(rows, key=lambda r: r[1] == "index.html"):
        s3.upload_file(
            Filename=str(path), Bucket=bucket, Key=f"{prefix}/{rel}",
            ExtraArgs={"ContentType": ctype, "CacheControl": cache},
        )
        print(f"  put {rel}")
    if prune:
        keep = {f"{prefix}/{rel}" for _, rel, _, _ in rows}
        pages = s3.get_paginator("list_objects_v2").paginate(
            Bucket=bucket, Prefix=f"{prefix}/")
        for page in pages:
            for obj in page.get("Contents", []):
                if obj["Key"] not in keep:
                    s3.delete_object(Bucket=bucket, Key=obj["Key"])
                    print(f"  removed stale {obj['Key'][len(prefix) + 1:]}")


def verify(bucket: str, prefix: str) -> None:
    """Anonymous check that the page is public and served with the right type."""
    url = f"{PUBLIC}/{bucket}/{prefix}/index.html?cb={os.getpid()}"
    # Source Cooperative's edge 403s the default Python-urllib User-Agent.
    req = urllib.request.Request(url, method="HEAD",
                                 headers={"User-Agent": "gridlook-publisher"})
    with urllib.request.urlopen(req) as r:
        print(f"  {r.status} {r.headers['Content-Type']}  "
              f"cache-control: {r.headers.get('Cache-Control', '(not echoed)')}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--product", required=True, choices=sorted(PRODUCTS),
                    help="which repo and store to publish the viewer for")
    ap.add_argument("--build", type=Path, metavar="GRIDLOOK_DIR",
                    help="gridlook checkout to build before uploading")
    ap.add_argument("--dist", type=Path, default=DEFAULT_DIST,
                    help=f"build output folder (default {DEFAULT_DIST})")
    ap.add_argument("--prefix", default=None,
                    help="prefix for the viewer (default: the product's viewer_prefix)")
    ap.add_argument("--dry-run", action="store_true",
                    help="list what would be uploaded; upload nothing")
    ap.add_argument("--prune", action="store_true",
                    help="delete objects under the prefix that this build lacks")
    args = ap.parse_args()
    product = PRODUCTS[args.product]
    prefix = (args.prefix or product["viewer_prefix"]).strip("/")
    bucket = product["bucket"]

    if args.build:
        build(args.build, args.dist)
    # Before plan(), so the catalog is part of the upload set.
    written = write_catalog(product, args.dist)
    if written:
        print(f"wrote {written} listing {len(_stores(product))} stores")
    rows = plan(args.dist)
    size = sum(p.stat().st_size for p, *_ in rows)
    print(f"{len(rows)} files, {size / 2**20:.1f} MB -> s3://{bucket}/{prefix}/")

    if args.dry_run:
        for _, rel, ctype, cache in rows:
            print(f"  {rel:55s} {ctype:28s} {cache}")
    else:
        upload(rows, bucket, prefix, args.prune)
        verify(bucket, prefix)

    print("\nViewer links:")
    for var, url in viewer_urls(product, prefix).items():
        print(f"  {var}: {url}")


if __name__ == "__main__":
    main()
