# Where sovereign-veritas stands against OVERT 1.1

**What this is:** a reading, not a conformance claim. sovereign-veritas is **not** an OVERT implementation
and is **not** OVERT-conformant. It is a single-author research prototype. This page is here because
anyone who knows OVERT will ask how the two relate.

OVERT 1.1 (Observable Verification Evidence for Runtime Trust) is an open standard published by Glacis
Technologies, Inc. on 11 June 2026. It is maintained at overt.is, and its specification text is licensed
CC BY 4.0. On 5 October 2026, Glacis announced that Utah's Office of Artificial Intelligence Policy will
require OVERT-conformant signed receipts from designated vendors in its AI Learning Laboratory. The section
numbers below refer to the OVERT 1.1 Markdown source, sha256
`f25c106b3881ec0bf77dc102bb138322896bcb016495f433786a5362b6e0edda`, read 2026-10-05. Read by Claude (Opus
5.5, Anthropic) at Chad Holland's direction; not reviewed by Glacis or anyone else.

## Assurance level, honestly

OVERT §4.1.1 maps deployment architecture to a maximum Attestation Assurance Level (AAL). AAL-4 requires an
independent attestation provider: a notary not controlled by the operator. sovereign-veritas has no notary.
Packages are signed with the author's own SSH key (`tools/sign_package.py`). The witness log is a file in this
repository, which the author controls (`witness/packages.log`, protected only by the `protect-main` ruleset).
Under §4.1.1 that architecture is at most AAL-3 ("machine-generated but operator-controlled"), and arguably
AAL-2, since no notary of any kind is present. OVERT says self-attestation is not compliant.

## Concept map

| OVERT 1.1 | sovereign-veritas | Same idea? |
|---|---|---|
| Receipt per control evaluation, signed at the event (ATT-3) | Evidence package per Gate decision, optional detached signature | Similar purpose. No epochs, no notary counter-signature, no provisional/full phases |
| Transparency log: RFC 6962 Merkle tree, inclusion and consistency proofs (ATT-4) | Append-only witness log in git; `LATEST_WITNESSED` / `STALE` / `NOT_WITNESSED` | Weaker: proves order among logged packages, not time; no Merkle proofs, no independent monitors |
| Replay: epoch binding, monotonic sequence, liveness nonce (§4.5, §18.8) | Witness log for freshness; `tools/consumer.py` refuses a package it has already accepted | Weaker: no time binding; consumer races are measured and published (RP-1) |
| Fail-open must be declared, with exposure windows reported (RES-5) | The Gate fails closed by design: DEFER / REFUSE on missing or unknown input | Different choice; OVERT leaves it to the operator, but requires a declaration |
| Verifiability classification of denominators (§4.6) | Evidence states (OPERATOR, DEFAULTED, ABSENT, DERIVED …) per runtime field | Related. **Known gaps:** the Gate does not read the tags (F1, PR-1), and an OPERATOR tag is not witnessed (PV-1, PR #54) |
| Conformance does not establish "the accuracy of recorded facts" or "completeness of observation" (governance §7) | CONSISTENT is not true; the record does not observe external effects (EO-1, XB-1) | The same limit, stated by both |
| S3P: exact bound on the *evaluator-judged* violation rate (§19, Annex B.7–B.8) | No sampling evaluator | Not applicable here. See Principia note 067 below |

## What this repository's results say about receipts in general

Several measured results here are about *any* signed decision record, not only this one:

- A record can be internally consistent, and even signed, while carrying a dishonest label (PV-1).
- A control can run and produce records while ignoring the evidence it was given (F1 / PR-1: 24 of 24 relabels
  left the decision unchanged).
- A record of execution is not an observation of the effect (EO-1).

OVERT's architecture addresses parts of this differently: through independent measurement of the attester
binary, evaluator version binding, and verdict reproducibility.

## The one candidate gap we found, tested elsewhere

S3P's bound is exact for the judged rate, but it does not cover the true rate when the evaluator can miss. An
always-pass evaluator gets the tightest bound in every epoch. We found no requirement in OVERT 1.1 that an
evaluator be shown, per epoch, to detect known violations. That was one search of the full text for sensitivity,
recall, false negatives, canaries, seeded or known positives, positive controls and detection probability.
A canary-corrected bound, registered, simulated and partly refuted, is in Principia-Artificialis note 067:
https://github.com/holland202/principia-artificialis/pull/21. It is a candidate, not a confirmed gap: a
registered Protocol Profile could specify something the standard text does not.

## Provenance

AI participation: Claude (Opus 5.5, Anthropic) read the standard and wrote this page. Human validation: Chad
Holland directed it on 2026-10-05; he reviewed summaries, not this page line by line. Chad is responsible
for the final artifact. Nothing here is endorsed by Glacis, CHAI or the AIGovOps Foundation.
