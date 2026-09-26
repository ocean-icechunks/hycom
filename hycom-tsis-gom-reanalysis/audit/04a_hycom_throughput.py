"""Ranged-GET rates from data.hycom.org, and its 403 response to bursts on one file.

Relevant only if a store ever pointed at HYCOM's own server; the plan is S3 (see 04b).
Stays at <= 8 connections, the limit HYCOM asks for. The same-file runs deliberately provoke
the 403 described in report F2, so do not re-run them casually. Results of the 2026-09-25
runs are recorded in out/hycom-throughput.txt.
"""
import asyncio, time, aiohttp
from common import PREFIX

def url(day, hour, kind): return PREFIX + f"2010/010_archv.2010_{day:03d}_{hour:02d}_{kind}.nc"

async def run(N, n, total, start, same_file, kind):
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=N)) as s:
        async def one(i):
            u = url(2, 0, kind) if same_file else url(100 + i // 24, i % 24, kind)
            a = start + (i * n if same_file else 0)
            async with s.get(u, headers={"Range": f"bytes={a}-{a + n - 1}"}) as r:
                await r.read(); return r.status
        t = time.perf_counter(); st = await asyncio.gather(*[one(i) for i in range(total)]); dt = time.perf_counter() - t
    c = {}; [c.__setitem__(x, c.get(x, 0) + 1) for x in st]
    print(f"N={N} {kind} {total} x {n / 1e3:.0f} KB same_file={same_file}: {dt:.1f}s {total / dt:.1f} req/s {total * n / dt / 1e6:.1f} MB/s {c}", flush=True)

for N in [1, 4, 8]:  # different files: one per hour, as a point time series reads
    asyncio.run(run(N, 8404, 48, 64643 + 700 * 8404, False, "2d"))   # one row of ssh
    asyncio.run(run(N, 810040, 24, 53474, False, "3z"))              # one depth level of a 3z chunk
    asyncio.run(run(N, 445412, 24, 64643, False, "2d"))              # one 53-row band of ssh
    time.sleep(2)
for N in [2, 4, 6, 6, 7, 7, 8, 8]:  # 40 depth levels of ONE 3z file, as a profile read does
    asyncio.run(run(N, 810040, 40, 40555474, True, "3z")); time.sleep(3)
