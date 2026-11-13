# Porting into and out of this repo

This repo is the v0.2.x maintenance line of Sovereign Veritas (MIT). The owner also keeps a separate, non-public
development line. On 2026-11-12, a manual comparison of the two found that a security fix made here on 2026-11-02
(the SEC-005 reservation lock) had not been carried to the development line. No process either repo ran would
have caught that. This file is that process.

## The rule

Every fix or finding that lands here gets an explicit **ported / won't-port** decision for the development line,
in the same PR where it lands or in the next working session. "Won't port" is a fine answer; silence is the
defect. Decisions about the development line are recorded in that line. Changes ported **into** this repo are
recorded below, each with the PR that carried it.

## Ported into this repo

| Date | Change | Where it landed here |
|---|---|---|
| 2026-11-13 | Workflow actions pinned to commit SHAs; dependabot for GitHub Actions | #110 |

## Record corrections (W9)

**2026-11-13.** The first version of this file (#110, commit `7254f39`) described the non-public development line
in detail: its version, licence, a commit, internal work IDs and file names, and a probe outcome. That breaks the
owner's rule that the public and private lines stay separate, so those details were removed from this file. The
decisions they recorded live in the development line. The earlier text is still in this repo's git history; it
was not rewritten. That version also said that "for 27 days" neither line carried the other's fixes. That counts
from the 2026-10-16 split. The lock itself took 10 days (2026-11-02 to 2026-11-12) to reach the development line,
which is the gap this process exists to close.

## Provenance

File and initial decisions written by Claude (Anthropic, Fable 5) at Chad Holland's direction (2026-11-12,
direction only), from a measured comparison of both repos. Narrowed to public scope by Claude (Anthropic, Opus 5.5)
at Chad Holland's direction (2026-11-13). Human validation: not performed. Human responsibility: Chad Holland.
Review level: direction only.
