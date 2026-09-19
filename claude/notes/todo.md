# To do — written 2026-09-19 as Eli signed off

Everything here is unfinished by choice, not broken. All repos are on `main`, clean, pushed;
no PRs are open. Items span several repos because the session did; each says where it lives.
Cross items off here as they are done.

## Waiting on Eli (nobody else can do these)

- [ ] **Send the CORS request for the HYCOM bucket** to help@hycom.org. Draft, S3 policy and
      the curl checks to run afterwards: [cors-request-hycom.md](cors-request-hycom.md). Check
      the sentence about egress being covered by AWS's open-data sponsorship first — it was not
      verified for this bucket. Until the bucket has a policy, the HYCOM viewer draws data only
      with a CORS-disabling extension.
- [ ] **Authorize the GitHub CLI for the `noaa-nwfsc` org** so `cefi-icechunks` can be reached:
      `gh auth refresh -h github.com`, approve the org in the browser. Then its README gets the
      "icechunk 1.x will not work" note (it uses `http_storage` twice), and its deprecated
      `{prefix: None}` virtual-chunk authorization could move to `HttpAccess`.
- [ ] **Commit or discard the working-copy README in `~/globcolour-Icechunks`.** Its
      `http_storage` code exists only there, uncommitted, so it could not get the note.
- [ ] **Watch <https://github.com/ocean-icechunks/noaa_oisst/issues/2>** (filed for Alex
      Kerney): `daily/time` stored as 16,452 one-value chunks, and `monthly` metadata copied
      from `daily` with `valid_max` not rescaled. It also tells him a README and viewer now sit
      beside his store. If he fixes the store, `~/icechunks/noaa-oisst/README.md` needs its
      caveats and its 7 s open time revisited, then re-mirroring.
- [ ] Decide on two offers not taken up: the **NOAA disclaimer** section at the bottom of this
      repo's root README, and a **self-refresh check** in published viewers (compare
      `build-info.json`, reload once) so a republish does not need a hard reload.

## Could be picked up by a session

- [ ] **The next HYCOM dataset.** None chosen. Same order as the first: plan → local smoke
      test → scratch test under `ocean-icechunks/test-repo/hycom/` with its viewer and README →
      production → READMEs in the standard format → mirror from merged `main`. Add the store to
      `DATASETS` in `publish_viewer.py`; lift the generic parts of `hycom_virtual.py` (header
      parser, scan, `check_scan`) to the repo root once it is clear what is shared.
- [ ] **A Learn pass on the `virtual-icechunk` skill** in `~/agent-skills`. The input is
      written: `~/agent-skills/claude/notes/inbound-from-hycom-2026-09.md`. Two places where the
      skill is wrong (`to_icechunk(encoding=…)` does not exist in VirtualiZarr 2.7.3; `chunks={}`
      breaks down at millions of chunks) and several new patterns. That repo wants an issue, a
      branch, a PR and a squash merge. `~/agent-skills` itself is 2 commits behind origin —
      another session had it open; pull there first.
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
      mirrored files. Its handoff has the detail. `git pull` also fails in that checkout
      ("Cannot rebase onto multiple branches") — use `git fetch && git merge --ff-only origin/main`.
- [ ] `~/pace-icechunks` is 2 commits behind origin with one uncommitted file of Eli's; a
      fast-forward is safe. Its mirrored README on Source Cooperative is current.

## Settled today, for the record

Rich Signell's Medium post: Eli confirmed the title and year (2024) used in both READMEs.
`tau`/`experiment` stay auxiliary coordinates. One viewer per root. Store READMEs use the
standard format and carry the icechunk 1.x note.
