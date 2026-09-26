"""Ranged-GET rates from S3 for the request sizes a split GOMb0.01 store would issue.

The GOMb0.01 files are not on S3 yet, so this uses the GOFS 3.1 bucket (us-west-2, same region
as the hub) as a stand-in: same service, same kind of 4-5 GB uncompressed file. Each request
goes to a different file, as a point time series would. Anonymous, public bucket.
"""
import asyncio, time, aiohttp, subprocess
B = "https://hycom-gofs-3pt1-reanalysis.s3.us-west-2.amazonaws.com/2010/"
keys = [l.split()[-1] for l in subprocess.run(["aws", "s3", "ls", "--no-sign-request", "s3://hycom-gofs-3pt1-reanalysis/2010/"],
        capture_output=True, text=True).stdout.splitlines() if l.endswith(".nc")][:400]
async def run(N, n, total):
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=N)) as s:
        async def one(i):
            async with s.get(B + keys[i % len(keys)], headers={"Range": f"bytes={100_000_000 + i*4096}-{100_000_000 + i*4096 + n - 1}"}) as r:
                await r.read(); return r.status
        t = time.perf_counter(); st = await asyncio.gather(*[one(i) for i in range(total)]); dt = time.perf_counter() - t
    c = {}; [c.__setitem__(x, c.get(x, 0) + 1) for x in st]
    print(f"N={N:3d} {n/1e3:6.0f} KB x {total}: {dt:5.1f}s {total/dt:7.1f} req/s {total*n/dt/1e6:7.1f} MB/s {c}", flush=True)
print(len(keys), "files")
for N in [1, 16, 64, 128]:
    for n in [8_404, 445_412, 810_040]:
        asyncio.run(run(N, n, 40 if N == 1 else 400))
