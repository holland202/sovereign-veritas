# SOVEREIGN VERITAS COVERING SUITE — Charter — 01

Status: GEN 02 — cure generation. Issued 2026-11-12 by the StegVerse Build
Lane. Supersedes the GEN 01 charter, which shipped as an unfilled template
placeholder (the subject's second finding against GEN 01; see
CURE__RECORD__01.md). The GEN 01 suite is preserved unmodified as the
baseline of record.
ProjectID: LINKEDIN-SOVEREIGN-VERITAS-EVAL
Funding: UNFUNDED

## Purpose

This suite is the StegVerse covering of Sovereign Veritas
(holland202/sovereign-veritas): a governed transition boundary built
around the subject's unmodified workflow, in the subject's own idiom,
reusing the subject's own verdict machinery. It exists because the
subject's published findings (XB-1, EO-1, EO-2) name, precisely, the
execution-boundary cases its decide → execute → record sequence cannot
express, and the covering supplies the missing form: the action and its
record as one object — a durable INTENT admitted before any effect, a
COMPLETION carrying the effected side's attestation, an UNKNOWN held open
instead of silence, and an offline verifier that checks the pair.

GEN 01 built that covering and was independently reproduced by the
subject's author. GEN 02's purpose is narrower and is the whole of this
generation: cure the three defects the author's examination found in the
suite itself — the platform lock that did not exist where the docstring
claimed it, the conformance gate that could not fail on empty members,
and the commercial terms that were in the file before they were in the
message — while changing nothing the reproduction verified. A suite that
asks to be trusted at a boundary has to be exact about its own claims
first; this generation is that exactness applied to GEN 01.

## Level discipline

Three levels are held apart throughout, and a statement at one level is
never evidence at another:

- **The subject's core.** sovereign_veritas is unmodified — byte-identical
  to the public checkout at the pinned commit. The covering imports it;
  it never edits it. Findings about the core are the subject's to fix
  under the subject's own discipline (for example, the Python 3.12
  incompatibility the author isolated in his repository during the
  GEN 01 reproduction).
- **The covering layer.** The suite's own code (transition_ledger.py,
  guarded_workflow.py, verify_transition.py) and its registered cases.
  Claims made here are graded by runs: author runs are labeled as such,
  and conformance of this layer means its checks pass AND its prose
  members carry their stated substance (the GEN 02 vacancy layer).
- **The suite record.** The manifest, the in-suite conformance proof,
  the ledger of this suite's own generations, and the reproduction
  status. The record states what happened; it does not promote an
  author-side run into a verified one. GEN 02 stands AUTHOR-CONFORMANT
  until a non-author reproduction — the subject's own, in the first
  instance — discharges it, exactly as GEN 01's did.

Generation discipline: a defect found in a proven generation is cured in
a new generation, never by editing the proven one's bytes. GEN 01's
defects are therefore still visible in GEN 01, on purpose: the baseline
is the evidence the cure is measured against.
