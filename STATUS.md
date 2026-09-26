# STATUS — Verified vs. Unverified

---

## VERIFIED — automated tests

**213 passed** @ 2033088 (Termux / S25, 16.01 s). Measured thermal status on the S25: at rest `normal` -> ALLOW; after 30 s all-core load `hot` (cpu_core 103.8 °C) -> DEFER; both packages 19 of 19 checks, the verifier recomputing the status. Limits uncalibrated (policy `s25-uncalibrated-v0`). See `docs/EVIDENCE_PACKAGE.md`.

Integration (2026-09-26, docs/INTEGRATION.md): **242 passed** (container). Every verifier guard
switched off in turn fails a test: 22 of 22, after two survivors (`artifact_digest`,
`provenance_chain`) got the tests they lacked. New packages carry evidence-ledger evidence states;
finding F1: `compute_budget` and `power_status` are defaults the Gate counts as healthy (now tagged
`DEFAULTED`, Gate unchanged). vacuity_lint: 0 findings. CI job `red-team` runs all three.

Published and signed (2026-09-26): the measured pair, `sv_package_118a02b75646` (ALLOW at rest) and
`sv_package_45c6ad182584` (DEFER under load). From a fresh clone: 20 of 20 each, `SIGNED:holland202`;
0 of 807 signed rewrites of the DEFER package verify. Not yet witnessed. CI re-checks every published
package and witness entry on each push (223 passed; Windows 215 + 8 skipped).

Earlier: **185 passed** on `main` = `feature/local-inference-measurement`, code as at 5b64d8e (Termux / S25, Python 3.14.6, 12.59 s).

Evidence package, all three layers, on the published S25 package from a fresh clone of GitHub only
(container x86_64): 20 of 20 checks, `CONSISTENT`, `authenticity=SIGNED:holland202`,
`freshness=LATEST_WITNESSED(1)`. Signed: 0 of 796 single-field rewrites verify (S25). An older signed
package after a newer one is witnessed: `STALE` (container). Freshness holds only while `main`'s history
is not rewritten; the `protect-main` ruleset blocks force pushes and deletions (a test force push
was rejected by GitHub, GH013, 2026-09-26). See `docs/EVIDENCE_PACKAGE.md`.

CI (GitHub Actions run 36236747944 @ `197b0b0`, 2026-09-26): all 9 jobs pass. The S25's gate
digest `ab816905…2d65` appears in every job's log, so the Gate's 4608 decisions are identical on
Android/aarch64 (device), Linux, macOS and Windows, Python 3.10-3.14. Windows skips exactly the 8
anchored-ledger tests (no POSIX `fcntl`); the signature and witness tests run there.

| Job | pytest | gate digest = S25's | fresh package verifies |
|---|---|---|---|
| macOS, Python 3.10 / 3.12 / 3.14 | 185 passed | yes | yes |
| Linux, Python 3.10 / 3.12 / 3.14 | 185 passed | yes | yes |
| Windows, Python 3.10 / 3.12 / 3.14 | 177 passed, 8 skipped | yes | yes |

Earlier: **157 passed** on `feature/local-inference-measurement` @ ed042e7 (Termux / S25, Python 3.14.6, 9.31 s).
Fresh clones of ed042e7 in a container: 157 passed on Python 3.10, 3.11, 3.12 and 3.13.

Earlier: **141 passed** on `feature/bounded-multi-step-planner` @ 9308ce3 (Termux / S25, Python 3.14.6, 7.29 s).

Gate constraint (`tools/gate_constraint.py --mutants`): DIGEST identical on S25 aarch64 and container x86_64;
19/19 mutants killed. See `docs/GATE_CONSTRAINT.md`. Digest also identical on Python 3.10 (container).

Evidence package (`docs/EVIDENCE_PACKAGE.md`): a package made on the S25 passes 16/16 independent
checks (CONSISTENT); 0 of 17157 truncated and 0 of 200 bit-flipped copies of it accepted (S25).

---

## MEASURED — Stage-1 concurrency (frozen)

Concurrent writers UNSUPPORTED (chain broken, fail closed). Single writer SUPPORTED.

---

## MEASURED — Stage-2 software durability

clean recover · torn line fail closed.

---

## MEASURED — Physical SIGKILL (n=3 valid)

| Run | recovered_ok | count | notes |
|-----|--------------|-------|-------|
| #1 | true | 2226 | manifest running |
| #2 | true | 2810 | manifest running |
| #3 | true | 1127 | manifest running; dir `03b` |
| #4–#5 | pending | — | — |

Ctrl+C attempt discarded (`clean_stop`).  
**claim:** 3/3 valid measured SIGKILL recoveries verified. Not a reliability rate; not power-loss.

See `docs/PHYSICAL_DURABILITY_RUNS.md`.

---

## Version

`__version__ = "0.1.1"`
