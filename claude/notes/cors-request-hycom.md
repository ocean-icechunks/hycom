# CORS request for the HYCOM bucket — draft email (2026-09-19)

Status: **drafted, not sent.** Eli sends it. To: help@hycom.org (the registry's contact; the
bucket is managed by COAPS).

Why it is needed: a browser reading a virtual store talks to two hosts. Source Cooperative
sends `access-control-allow-origin: *`; the HYCOM bucket has no CORS configuration at all —
S3 says so itself (`GET /?cors` → `NoSuchCORSConfiguration`, checked 2026-09-19). So the
gridlook viewer draws the axes and the browser blocks every data read. Applying a policy
needs **no rebuild**: the references do not change.

Adapted from Eli's GCS material in `~/nodd-cors/` (used for the NODD buckets) and the
request template in the `virtual-icechunk` skill's `browser-access.md`. Those are GCS
format; this bucket is **S3**, whose format differs, so the JSON below is new. It follows
AWS's documented `put-bucket-cors` schema but **has not been applied by us to any bucket** —
we do not own an S3 bucket to try it on. `noaa-goes16`, in the same AWS open-data registry,
already serves `AllowedOrigin *` / `GET` / `AllowedHeader *`, readable at
`https://noaa-goes16.s3.amazonaws.com/?cors`.

---

**Subject:** Request: enable CORS on the hycom-gofs-3pt1-reanalysis S3 bucket (read-only, one command)

Hello,

Thank you for putting the GOFS 3.1 reanalysis on AWS Open Data. I have published a
cloud-native index of it — an Icechunk store holding only metadata and byte-range
references, so the whole 1994–2015 archive opens in a second as one xarray datacube while
every byte stays in your bucket, unchanged:

https://github.com/ocean-icechunks/hycom

It works well from Python. It also has a browser viewer, which reads the same byte ranges
directly from your bucket with no server in between — and that is blocked, because the
bucket has no CORS configuration. Browsers refuse cross-origin reads unless the bucket
returns CORS headers, so the data is unreadable from any web page even though it is public.
S3 confirms there is none today:

    $ curl "https://hycom-gofs-3pt1-reanalysis.s3.us-west-2.amazonaws.com/?cors"
    <Code>NoSuchCORSConfiguration</Code>

Could you apply this policy? Save as `cors.json`:

```json
{
  "CORSRules": [
    {
      "AllowedOrigins": ["*"],
      "AllowedMethods": ["GET", "HEAD"],
      "AllowedHeaders": ["*"],
      "ExposeHeaders": ["Content-Range", "Content-Length", "Accept-Ranges", "ETag"],
      "MaxAgeSeconds": 3600
    }
  ]
}
```

```sh
aws s3api put-bucket-cors --bucket hycom-gofs-3pt1-reanalysis --cors-configuration file://cors.json
```

(In the S3 console it is Bucket → Permissions → Cross-origin resource sharing; paste only the
`[ { … } ]` array.)

A few things that may help you decide:

- **It grants no new access.** The objects are already publicly readable; anyone can fetch
  them with `curl` today. CORS only tells browsers they may do what every other client
  already can. It is read-only: `GET` and `HEAD`, no write methods.
- **`AllowedHeaders` must admit `Range`.** Readers fetch small byte ranges, not whole 4.8 GB
  files. `"*"` covers it and matches what other open-data buckets use — `noaa-goes16`, for
  example, serves `AllowedOrigin *`, `GET`, `AllowedHeader *`.
- **Nothing else changes** — no objects, no bucket policy, no paths.
- **Egress** is the one real consideration: with `AllowedOrigins: ["*"]`, any web page can
  cause its visitors' browsers to read from the bucket. My understanding is that egress from
  Registry of Open Data buckets is covered by AWS's sponsorship program rather than billed to
  you; if that is not so for this bucket, tell me and I will send a short list of specific
  origins instead.

Once it is applied I can confirm it from outside with two curl requests, and I would be glad
to send you the viewer link.

Thank you,
Eli Holmes
NOAA Fisheries

---

## If they prefer specific origins

Replace `AllowedOrigins` with
`["https://data.source.coop", "http://localhost:5173", "http://localhost:8080"]`
— the published viewer's host, plus gridlook's dev ports (as in `~/nodd-cors/cors-scoped.json`).
S3 does allow one `*` wildcard inside an origin, unlike GCS.

## Verifying afterwards (read-only)

```sh
U="https://hycom-gofs-3pt1-reanalysis.s3.us-west-2.amazonaws.com/2010/hycom_GLBv0.08_536_2010061512_t000.nc"
curl -s "https://hycom-gofs-3pt1-reanalysis.s3.us-west-2.amazonaws.com/?cors"          # the stored policy
curl -s -D - -o /dev/null -X OPTIONS -H "Origin: https://data.source.coop" \
  -H "Access-Control-Request-Method: GET" -H "Access-Control-Request-Headers: range" "$U" | grep -iE "^HTTP|access-control"
curl -s -D - -o /dev/null -H "Origin: https://data.source.coop" -H "Range: bytes=0-99" "$U" | grep -iE "^HTTP|access-control|content-range"
```

Today (2026-09-19): preflight `403 Forbidden` with no CORS headers; ranged GET `206` with
`Content-Range` and **no** `Access-Control-Allow-Origin`. Want: preflight `200` allowing
`range`; ranged GET `206` with `Access-Control-Allow-Origin` and
`Access-Control-Expose-Headers`. The ranged GET is the one that decides. Passing curl proves
the headers, not that the viewer renders — Eli checks that in a browser with the extension
**off**, then the "needs a CORS extension" text in both READMEs and `publish_viewer.py` comes
out.
