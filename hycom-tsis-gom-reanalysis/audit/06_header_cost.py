"""How many 64 KiB reads h5py needs to find every chunk's byte range, and where they are.
A per-file header scan (needed because offsets vary, report F4) costs this per file. Writes out/header-cost.txt."""
import functools
from common import PREFIX
import h5py

with open("out/header-cost.txt", "w") as out:
    for p in ["2010/010_archv.2010_100_00_2d.nc", "2010/010_archv.2010_100_00_3z.nc",
              "2024/027_archv.2024_169_07_2d.nc", "2024/027_archv.2024_169_07_3z.nc"]:
        # h5py hides the file object, so reopen with an instrumented one
        import fsspec, requests
        size = int(requests.get(PREFIX + p, headers={"Range": "bytes=0-0"}).headers["content-range"].split("/")[1])
        fo = fsspec.filesystem("https").open(PREFIX + p, size=size, block_size=2**16, cache_type="blockcache")
        seen = []
        orig = fo.cache._fetch_block
        def wrapped(n, _o=orig): seen.append(n); return _o(n)
        fo.cache._fetch_block_cached = functools.lru_cache(64)(wrapped)
        with h5py.File(fo) as hh:
            for d in hh.values():
                if isinstance(d, h5py.Dataset) and d.chunks:
                    for i in range(d.id.get_num_chunks()): d.id.get_chunk_info(i)
        line = f"{p:40s} size {size:>11d}: {len(set(seen)):2d} reads at MB " + ", ".join(f"{b * 65536 / 1e6:.0f}" for b in sorted(set(seen)))
        print(line); print(line, file=out)
