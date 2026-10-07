# Production gap analysis — Sovereign Veritas (as of `dfcbee1`, 2026-10-07)

**Verdict: Research profile. Not ready for the Controlled Service profile.** Five blockers stand in the way (section 2).
Nothing here makes the project look further along than its evidence: where a property holds only in a prototype, or only
in this container, it says so. Written by Claude (Opus 5.5), **self-tested**: no outside reviewer has checked this
assessment. Threats are numbered as in `docs/THREAT_MODEL.md`.

## 1. Readiness matrix

| Property | Status | Evidence | Remaining gap |
|---|---|---|---|
| Gate decides per its contract | MEASURED, multi-platform | 4690 vectors (kernel and verifier CONFORM), 4608-case lattice digest identical on S25 and CI, 19 of 19 planted Gate bugs caught, contract rules switched off: 22 of 23 fail a vector | the vectors are generated from the kernel (a regression pin, not an independent oracle); the supplement is a derived oracle |
| Second implementation | REPRODUCED (same vendor) | `ports/rust`: a Claude subagent, contract-only, conformed on its first run; `ports/go` conforms | not independent judgment; Go fails open off-contract |
| Package integrity and closed schema | MEASURED | `verify_package.py` with 28 guards; verifier mutants all killed (CI, `b7d072b`) | unbound fields are pinned, not closed (T6) |
| Authenticity | MEASURED, narrow | KL-1 8 of 8; KL-P5 fixed | no revocation, no signing time, no release or root key (T9, T10) |
| Freshness | MEASURED (order only) | witness and consumer tests | unsigned log, no clock, first use |
| Relying-party consumer | MEASURED | RP-1, K1, F3, F4 fixes; metamorphic replay | first use; stdlib JSON parse with no size cap (T4) |
| Execution boundary (`EvidenceWorkflow`) | **NOT SUPPORTED** for at-most-once without keys | XB-1 X4/X5 open; EX-1 X3 baseline: an effect with no record in 2 of 2 crash cases | join to the journal (X9) |
| Execution boundary (EX-1 prototype) | MEASURED, self-tested | crash campaign 22 of 22 with effects ≤ 1; fuzz 0 violations in 2000 and 20000 sequences after fixes; 105 tests; mutants 23 of 24 + 1 equivalent; Windows CI pass | not used by the workflow; actors declared; chain unkeyed; no independent review yet (a blind same-vendor review is running) |
| Effect truth | MODEL_DEPENDENT | receipts attest the executor's claim; an observer can dispute | there is no real observer integration |
| Custody (revocation reaches the decision) | MEASURED | R1–R3 | only when a registry is passed |
| Runtime evidence states | MEASURED, open defect | `evidence_states` | DEFAULTED counted healthy (T23) |
| Resource bounds | MEASURED, partly fixed | RE-1: no size cap; MemoryError → COULD NOT LOOK; depth early exit | size cap (T4) |
| Cross-platform | MEASURED in CI | Linux, macOS, Windows × 3.10/3.12/3.14 | the anchored ledger is POSIX-only; no Windows desktop run; S25 runs are older than this week's changes |
| Supply chain | OBSERVED | `docs/SUPPLY_CHAIN.md`: no runtime dependencies; scanners fire on planted defects | action tags, unpinned test dependencies (T25) |
| Vehicle use | MODEL_DEPENDENT (simulation) | V11 spoof: 61 m outside the fence; V12/V14 models | not for GNSS-contested use; no hardware |
| Independent reproduction | NOT ESTABLISHED for this week's work | Amos Tipton's bounded reproductions of earlier commits (STATUS) | nothing after 2026-10-04 was reproduced by anyone else |

## 2. Production blockers (each must be closed before the Controlled Service profile)

1. **B1, T18: effect without record in the path users run.** The fix exists only in `ExecutionCoordinator`. Join it to
   `EvidenceWorkflow` and run X9 as registered.
2. **B2, T23: DEFAULTED values count as healthy.** A package made with defaults can ALLOW on values nobody declared.
3. **B3, T9/T10: no key lifecycle.** A compromised key cannot be revoked without making every genuine old package fail the
   same way a forgery does. Revocation-list support plus a witness clock or signed checkpoints.
4. **B4, T4: no input size cap** on the verifier and consumer.
5. **B5: no independent review or reproduction of the execution boundary, KL-1, RE-1 or the custody fixes.** All of it is
   self-tested. Same-vendor agents provide separation of context, not independence.

Also needed for High-Assurance, though not for Controlled Service:
- a keyed or witnessed journal (T21);
- authenticated observers (T30);
- SHA-pinned CI (T25);
- sv.gate/1 rule 0 for out-of-contract input (T29);
- device validation on the target hardware;
- an outside red team.

## 3. Deployment profiles

| Profile | Meant for | Entry criteria | Met? |
|---|---|---|---|
| **Research** | the author and reviewers on their own machines; no real effects | fail-closed Gate under contract; honest labels; failures kept; CI green | **yes**, provided the red-team job is green at the head (it was red at `b7d072b`; both causes are fixed in `f5c7c19`; the test matrix is green at `28391d1`) |
| **Controlled Service** | one operator, real but reversible effects, a human reconciles every uncertain outcome | B1–B5 closed; runbook for EFFECT_UNCONFIRMED; size cap; key rotation drill rehearsed; S25 re-validated at the deployed commit | **no**: B1–B5 open |
| **High-Assurance Candidate** | irreversible or safety-relevant effects | Controlled Service, plus keyed journal, authenticated observers, independent implementation **by another party**, outside red team, hardware fault testing, signed releases with a root key | **no** |

## 4. Readiness gates

| Gate | Criterion | State |
|---|---|---|
| G1 | every registered prediction has a result, and refutations are kept | met for EX-1 (X7 REFUTED kept), KL-1, RE-1, JG-2 Record 2 |
| G2 | every test can fail (mutants or planted defects) | met for the verifier (28 guards), the Gate (19 planted bugs, 22 of 23 rules), EX-1 (23 of 24 + 1 equivalent), KL-1 and RE-1 (sabotage), supply-chain scanners (planted). **Not** measured for the whole suite |
| G3 | CI green on every platform at the head | at `28391d1` all 12 test jobs (Linux x86 and arm, macOS, Windows × Python 3.10/3.12/3.14) and `port-go` passed; the red-team job was still running when this was written; `dfcbee1` pending |
| G4 | no open High in the threat model | **not met**: T18, T23, T10, T4 |
| G5 | independent reproduction of the safety-relevant claims | **not met** |
| G6 | the deployment target validated at the deployed commit | **not met**: the S25 runs predate this week |

## 5. Definition of done (for any change to the execution or evidence path)

- [ ] Registered before building (committed **and pushed**), with a refutation criterion per prediction.
- [ ] An anti-vacuity control per instrument (sabotage or planted defect) that is shown to fail.
- [ ] Failures first in the results; refutations and instrument defects kept with their raw output.
- [ ] Numbers in prose copied from output files.
- [ ] Mutation check of the new tests; every survivor explained or killed.
- [ ] Full suite, the vacuity scan, and the contract check run locally; CI green on every platform at the pushed head.
- [ ] The threat model and this matrix updated; STATUS entry; no README claim stronger than its evidence.
- [ ] Provenance stated (model, human review level actually performed).

## 6. The independent verification gap (deliverable L)

Everything this week (custody, K1, review fixes, differential testing, EX-1, KL-1, RE-1, supply chain) was:
- designed, built, run and judged by one model;
- reviewed only by same-vendor agents with a fresh context (the 48ab26a review; the EX-1 blind review, in progress);
- not reproduced by a person.

The cheapest real independence available:
1. Chad Holland runs `tools/ex1_campaign.py`, `tools/kl1_probe.py` and the test suite on the S25 at the pushed head.
2. An outside reviewer (one of the people credited in STATUS) attacks `execution.py` with the threat model as a map.
3. A second fuzzer for the journal, written by someone who has not read `tools/ex1_fuzz.py`.

## 7. Contradictions found in the documentation (reported, not edited: escalation rule)

1. **README "What has been measured" ends with `Reproduction by anyone else | none yet`.** The same table cites an
   outside reproduction (Amos Tipton's, in the damaged-copies row), and `STATUS.md` lists his two bounded reproductions
   under CREDITED reproductions. Both cannot stand as written. Which wording is right is the owner's call. My reading:
   "bounded reproduction of earlier commits by one person, not of this week's work".
2. **README `Verifier guards switched off one at a time | 27 of 27`** predates the 28th guard (`capability_matches_registry`,
   `ca8ba8b`). CI's verifier-mutants step passed at `b7d072b`, but I have not copied its count into the README, because the
   rule is that numbers come from output I quote.
