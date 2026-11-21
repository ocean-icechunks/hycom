# To do — written 2026-09-19 as Eli signed off; re-checked 2026-11-21

Everything here is unfinished by choice, not broken. Items span several repos; each says where it lives.
Cross items off here as they are done. **GOM (GOMb0.01/GOMe0.01) work is not tracked here**: it is in the
handoff and [plan-issue-17.md](plan-issue-17.md).

## Waiting on Eli (nobody else can do these)

- [ ] **Send the CORS request for the GOFS 3.1 bucket** to help@hycom.org. Draft, S3 policy and
      the curl checks to run afterwards: [cors-request-hycom.md](cors-request-hycom.md). Check
      the sentence about egress being covered by AWS's open-data sponsorship first — it was not
      verified for this bucket. Until the bucket has a policy, the GOFS 3.1 viewer draws data only
      with a CORS-disabling extension. (The GOM bucket already sends CORS headers.)
- [ ] **Authorize the GitHub CLI for the `noaa-nwfsc` org** so `cefi-icechunks` can be reached:
      `gh auth refresh -h github.com`, approve the org in the browser. Then its README gets the
      "icechunk 1.x will not work" note (it uses `http_storage` twice), and its deprecated
      `{prefix: None}` virtual-chunk authorization could move to `HttpAccess`.
- [ ] **Commit or discard the working copy in `~/globcolour-Icechunks`.** Still uncommitted on
      2026-11-21: `README.md` and `copernicus-icechunk-sc.ipynb` modified, plus an untracked
      `copernicus-icechunk-sc-parallel.ipynb`. Its `http_storage` code exists only there, so it could not get the note.
- [ ] Decide on two offers not taken up: the **NOAA disclaimer** section at the bottom of this
      repo's root README, and a **self-refresh check** in published viewers (compare
      `build-info.json`, reload once) so a republish does not need a hard reload.

## Could be picked up by a session

- [ ] **`~/icechunks/noaa-oisst/README.md`: revisit after ocean-icechunks/noaa_oisst#2 was fixed.** Alex Kerney
      closed the issue as completed on 2026-10-09 (time rechunked, `monthly` metadata fixed). The README's
      caveats and its 7 s open time were written against the old store, so they need re-measuring, then re-mirroring.
- [ ] **Issue #9 (this repo): a performance section for GOFS 3.1** — map, regional subset, point time series, with
      time, bytes downloaded and what optimal chunking would give. Open since 2026-09-25, not started.
- [ ] **A Learn pass on the `virtual-icechunk` skill** with the September input,
      `docs/design/inbound-from-hycom-2026-09.md` in ocean-icechunks/ocean-icechunks-skills
      (`~/ocean-icechunks-skills`). ocean-icechunks-skills#20 (the GOMb0.01 lessons) was closed on 2026-11-19;
      whether the September items went in with it was not checked. Two places the skill was wrong
      (`to_icechunk(encoding=…)` does not exist in VirtualiZarr 2.7.3; `chunks={}` breaks down at millions of chunks).
      That repo wants an issue, a branch and a PR.
- [ ] **gridlook: take the default dataset from the first catalog entry** instead of the
      hard-coded OGS store (`DEFAULT_DATASET` in `HashGlobeView.vue`). It would retire the
      default-hash workaround in both `publish_viewer.py` copies. No issue filed; noted in
      `~/gridlook/claude/handoff.md`.
- [ ] **Report the VirtualiZarr dtype check upstream.** `check_same_dtypes` compares numpy
      dtypes, so an array declared `>i2` cannot take a later `region=` or `append_dim=` write
      ("inconsistent dtypes: int16 vs >i2"). Worked around here by declaring native `int16`
      with a `bytes(endian=big)` codec. Details in [smoke-test-findings.md](smoke-test-findings.md).
- [ ] **`~/icechunks`: a committed `mirror_docs.py`.** The README mirrors there were refreshed
      by hand twice with throwaway scripts; only the READMEs were compared, not the other
      mirrored files. Its handoff has the detail.
- [ ] `~/pace-icechunks` is 2 commits behind origin with an untracked `untitled.txt` (2026-11-21); a
      fast-forward is safe.

## Settled, for the record

Rich Signell's Medium post: Eli confirmed the title and year (2024) used in both READMEs.
`tau`/`experiment` stay auxiliary coordinates. One viewer per root. Store READMEs use the
standard format and carry the icechunk 1.x note.
