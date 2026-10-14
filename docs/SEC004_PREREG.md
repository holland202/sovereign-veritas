# SEC-004 — File reservation stale-completion / release race (preregistration)

**Status: REGISTERED, UNRUN.** This document is committed before the SEC-004 probe and before any results are produced. This is a security investigation of an existing open issue, not a claim of a newly discovered exploit. Repository remains **maintenance-only, experimental, not production-ready, not independently security-validated**.

## Motivation and existing evidence

- RK-3 already records that a late holder can cause two effects if a new holder is released before the old effect lands. This experiment does **not** re-claim RK-3's known finding.
- `docs/RK3_RESULTS.md` explicitly lists races involving `release()` and late `complete()` as untested.
- In `FileReservations._move()`, token equality is checked before a later `_write()`; `FileReservations.release()` checks `UNKNOWN`, writes a RELEASED entry and renames the active path; `reserve()` claims the active path with `O_EXCL`. These are separate filesystem operations, not one transaction.
- `MemoryReservations` holds a lock across each operation, whereas `FileReservations` has no shared lock across the sequence. This is a code-based hypothesis, not a measured outcome.

## Frozen target identity at registration

Source repository: `holland202/sovereign-veritas`, `main` at the creation of the `security/sec-004-release-race` branch. Git blob object identifiers (SHA-1, **not** SHA-256 of the raw file contents):

| Target | Git blob |
|---|---|
| `sovereign_veritas/idempotency.py` | `071fc3fe64672c6cdbe7a3fe6e6406554c03a574` |
| `tests/test_idempotency.py` | `aa977253933cd6b0155cd923f5e06c4eb6586d63` |
| `docs/RK3_RESULTS.md` | `acddf169a76cdd07a1d52c5628eb626a6dfa5308` |
| `docs/OBS1_RESULTS.md` | `8a294a7dc5332b8c4777f6e9bc8d85df6381c7a3` |

The probe must check these blob identities (or record their equivalent source bytes with SHA-256) before running, otherwise **INCONCLUSIVE**. The exact source commit must be recorded in results.

## Question and threat model

**Can a completion bearing an old, once-valid token overwrite a freshly reserved record when completion pauses after checking its token, while a release and fresh reserve occur?**

Only local `FileReservations` and `MemoryReservations` objects, a temporary directory, and in-process threads are involved. A simulated operator releases only a lease-expired `UNKNOWN` key. No external services, real actuators, vehicles, security scanning, or network targets. The pre-existing time-of-check/time-of-write behavior is the target, not a simulated external executor.

## Registered cases

- **C0 — Sequential memory control:** reserve K with a zero-second lease (old token), release UNKNOWN, reserve a new token, call `complete(K, token=old)`. Expect the new reservation to remain IN_FLIGHT; one `late_complete` with old and new tokens. A completion using the new token then reaches COMPLETED.
- **C1 — Sequential file control:** same sequence against two separate `FileReservations` objects pointing to one fresh temporary directory; same expected state and late-event behavior. This proves the late-event path works *without* the race.
- **C2 — File-store forced interleaving:** reserve K, zero lease. Start `complete(K, token=old)` in thread A. A harness-only hook stops thread A *at its first `_write` of COMPLETED*, after the existing token check and read but before writing any files. Thread B (main thread, a separate store object) releases the expired UNKNOWN K, then reserves K again and confirms new token / IN_FLIGHT from a fresh reader. Unblock A and wait for completion. Read the final active record, released history and late-event log from a fresh `FileReservations`. No production source edits.
- **C3 — Refusal control:** COMPLETED keys cannot be released. The refusal must leave existing record bytes unchanged.

The interleaving is established by events/barriers, not randomized timing. It must abort cleanly on timeout and report INCONCLUSIVE rather than hanging. The hook must capture and attest that the old write was reached only after the old token was accepted; if that cannot be demonstrated, C2 is INCONCLUSIVE.

## Predictions made before implementing the probe

- **P0:** C0 preserves the new token and reports one late event; the final state after new-holder completion is COMPLETED.
- **P1:** C1 does likewise. The final state and event log must be read from a separate fresh store object.
- **P2 (expected security failure):** Under C2 the old COMPLETED `_write` overwrites the new active reservation. The observed active token becomes **old**, not new, and the active state becomes COMPLETED despite the fresh reservation having been IN_FLIGHT before A resumed. This would be a failure of reservation ownership isolation, **not** by itself proof that a second real external effect occurred.
- **P3:** Under C2, the stale completion is **not** recorded as a `late_complete` event at the time of the old write, because the token check happened before the release.
- **P4:** C3 refuses release and preserves the original record.
- **P5 anti-vacuity:** The harness must demonstrate two distinguishable snapshots in C2: the new token held before A resumes, and the post-A value. If either is missing, or the supposedly paused A writes early, the result is INCONCLUSIVE.

A refutation of P2 or P3 must be kept. An outcome matching these predictions is **not a security PASS**; it would be an observed security failure. If the new token survives and the old completion becomes a late event, the tested boundary resists this particular schedule.

## Verdict rule

- **SECURITY FAIL** if C0/C1/C3/P5 controls hold and C2 ends with the stale token replacing the fresh token (regardless of whether all predictions match).
- **BOUNDED SECURITY PASS** if controls hold, C2 preserves the new token and records/otherwise safely rejects the stale completion, without unauthorized replacement.
- **INCONCLUSIVE** for any source identity mismatch, synchronization failure, timeout, missing raw observations, or control failure.
- Any other result is **UNEXPECTED**, investigated without editing this registration.

The probe prints its case observations, predictions, decision, and exit code. A probe returning 0 only means its **measurement harness ran and recorded a scored outcome**, not that the security boundary passed. External automation must read the named verdict rather than treating process exit=0 as safety.

## Controls and required evidence

- Make the probe a separate follow-up commit; do not modify `sovereign_veritas/` or existing tests.
- Record Python/platform, Git commit, target blob identities, the probe's source hash, exact shell command, execution and wait durations, and unedited stdout/stderr.
- Record random token values *within the private local experiment bundle* for correlation (these are synthetic reservation tokens only, not external credentials), state, histories, file bytes/digests, and observed race ordering.
- Results are appended in a separately dated file with any deviations, and negatives preserved. No silent revision of preregistration.
- Run in a temporary local directory only. Initial test is Linux x86_64/container or CI; **Android ARM64 is NOT VALIDATED** until explicitly run there.
- No claim of production exploitability, cross-process or cross-filesystem generality, or actual external effect without separate tests.

## Freeze point

SEC-004 registration exists before the probe, independent of the result. Next step is a separate harness commit and bounded runner. This document remains unchanged after the run; corrections go into an amendment.
