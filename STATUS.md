# STATUS — Verified vs. Unverified

> **MAINTENANCE-ONLY (from v0.2.0).** Active development of this repository has ended. Release `v0.2.0`
> (annotated tag on `ecd4de9`) is **NOT PRODUCTION-READY** and **NOT INDEPENDENTLY SECURITY-VALIDATED**.
> From here: security reports and correctness fixes only; no new features. All findings, negative results and
> known limits stay published: see [STATUS.md](STATUS.md) and [docs/RELEASE_NOTES_v0.2.0.md](docs/RELEASE_NOTES_v0.2.0.md).
> Cross-platform legs on the release revision `ecd4de9`: all 6 PASS, including s390x big-endian and ppc64le under QEMU emulation (not IBM hardware), run after the tag (xplat run `37990718927`, attempt 3).
> Issues and breaks are still welcome; the owner will answer them.

---

## OPEN findings (unfixed)

> **Update 2026-10-10 (this branch, not yet merged):** Q1 and Q3 below have candidate fixes (SV-FIX-001, F1 and
> F2) that passed their registered verification: F1 PASS, F2 PASS, one execution in a container, not on the S25,
> same author. See [docs/SV_FIX_001_RESULTS.md](docs/SV_FIX_001_RESULTS.md). The entries below stay as they were
> written. They move to fixed only when the fix is merged, and the record keeps the link to the failure.

- **SV-ATTACK-001 Q1 (2026-10-09): an ALLOW covers parameters changed after the decision.** `EvidenceWorkflow.run()`
  decides on a copy of the action's parameters (`workflow.py` L188), but executes the caller's original,
  mutable `ActionProposal` (L253). A change between the two runs unauthorized parameters, while the ledger
  records the authorized ones. Reproduced in the kernel and on `FakeVehicle` (a `goto` 500 m north, outside
  the fence) by a deterministic hook standing in for a concurrent writer. This shows the window exists, not
  how often it is hit. Container only; not run on the S25. See [docs/SV_ATTACK_001_RESULTS.md](docs/SV_ATTACK_001_RESULTS.md).
  Motivated by John Rodriguez's external-review concern about gate manipulation. The attack design is not
  his, and he has not reviewed it.
- **SV-ATTACK-001 Q3 (2026-10-09): `verify_package.py` does not compare `commands_sent` with the authorized
  parameters.** The package from the run above verifies `CONSISTENT` (exit 0). Separate component, separate
  finding.
- Replay of an earlier approval for a modified action was refused in both forms tested (Q2 PASS).

---

## CREDITED breaks

- **Davorin Popović** — AI-assisted private review/report (2026-10-02) identifying that `execute()` runs before
  the record is written (`evidence_sink.record()`) in `EvidenceWorkflow.run()` at `386716a`, with a reported
  counting-executor probe he stated he had not independently reproduced at that point. His report prompted
  XB-1. (Wording per his review, 2026-10-06.)
  This project pre-registered the cases and reproduced the behaviour (a repeated `record_id` gives 2
  external effects, 1 ledger record), merged as PR #7 (`ae6437a`). Credit is for the report and the
  probe idea; the reproduction, results and any fix are this project's, and he has not reviewed or
  endorsed them. Fix for sequential repeats only: PR #8, merged 2026-10-02 (`73de3f7`); the race and effect-without-record cases remain open. See
  [docs/EXECUTION_BOUNDARY_RESULTS.md](docs/EXECUTION_BOUNDARY_RESULTS.md).
- **Nicholas Kouns** (@nicholaskouns-create) — [issue #5](https://github.com/holland202/sovereign-veritas/issues/5)
  (2026-09-28): two unpublished implementation defects at `8f098e8`.
  (1) `vehicle_check` fail-opened on NaN / Infinity (IEEE comparisons never fired; Gate
  replayed ALLOW; verifier CONSISTENT). (2) `consumer.py` accepted a non-canonical witness
  prefix (`0001\t…` after anchoring `1 …`) because the anchor hashed the *parsed* pairs, not
  the exact entry-line bytes. Fixed in `2902a2c`. Evidence under `evidence/attacks/issue-005/`;
  registration and results in [docs/ISSUE_5_RESPONSE.md](docs/ISSUE_5_RESPONSE.md).
  Public reconstruction of the break and the revision: https://spring-palm-cedar-willow.grok.me/
  ("Threefold"). Signature against the published key still refused the poisoned file.
- **Nicholas Kouns** (@nicholaskouns-create) — [issue #4](https://github.com/holland202/sovereign-veritas/issues/4)
  (2026-09-26): eleven accepted breaks of treating sv.gate/0 as a verifier of reality and a gate
  on action. B4 and B11 fixed; the rest assigned to sv.gate/1. See [docs/ISSUE_4_RESPONSE.md](docs/ISSUE_4_RESPONSE.md).

---

## CREDITED reproductions

- **Amos Tipton**, Founder & Chief Architect of HYBRID WAYSS, with AI assistance using OpenAI tools — two
  reproduction bundles (2026-10-04) at `d37779c` and `2c825b8`, stored unedited under
  [docs/external/](docs/external/amos-tipton_2026-10-04_reproduction_README.md) with his permission. Recorded
  hashes and results matched this repository. He identified that the published truncation figure used a package
  unavailable in the repository at the time, and that the corruption tool exercised ordinary JSON parsing and
  direct verification rather than the hardened parser and signature/witness path. The run also found that two
  published packages took an action under ALLOW with DEFAULTED inputs, and confirmed, with no skipped tests, the
  PR #35 fix to `verifier_mutants.py`. These were bounded reproduction runs against the referenced
  implementation: **not an endorsement, not a certification, not an independent implementation and not
  comprehensive validation.**

---

## VERIFIED — automated tests

**Latest (2026-10-09): P-001 close-out, v0.2.0. EXPERIMENTAL — NOT PRODUCTION-READY, NOT INDEPENDENTLY SECURITY-VALIDATED.**
- **W1:** `tools/consumer.py accept` requires `--signature --allowed-signers --identity` and accepts only signed `sv.package/1`.
- **W2:** new packages carry `contract: {id: "sv.gate/0", conformance_digest}`. The verifier checks it against its own pinned `TRUSTED_CONTRACTS`. Legacy `sv.package/0` stays byte-identical and can be inspected with `--legacy` (`CONTRACT LEGACY_UNBOUND`).
- **A08:** the state file is written atomically. That is atomic replacement, not power-loss durability.
- **Gate decisions are unchanged:** 4,690 vectors, digest `44823d0f…0628`.

Evidence and test results:
- Frozen acceptance: `coordination/p001/ACCEPTANCE.md` @ `1c16e66`.
- [docs/P001_ACCEPTANCE_REPORT.md](docs/P001_ACCEPTANCE_REPORT.md): A01–A08 and B01–B08 PASS, three planted mutants killed (C06).
- [docs/RELEASE_NOTES_v0.2.0.md](docs/RELEASE_NOTES_v0.2.0.md).

Negative findings merged with this release, kept as findings:
- **PV-1 (#54):** a DEFAULTED→OPERATOR relabel verifies, and verifies SIGNED when signed. No field names a declarer.
- **AMB-1 (#55):** impostor gates reproduce all 4,690 vectors; the worst gives a false ALLOW on 1,235 of 10,000 inputs. The 800 extra vectors are not adopted.

Also merged: **VK-1 (#61)**, a hardware negative outside the kernel (`tools/accel/vk1/`). llama.cpp Vulkan on the Adreno 830 gives wrong output, and correct Vulkan inference is NOT DEMONSTRATED. Its perplexity cells are void because their control failed. The raw device results are committed and re-derive the pinned digest.

Still open:
- **W3:** an all-DEFAULTED package still gets ALLOW.
- XB-1 X4/X5, EO-1, concurrent consumers and first use.

Self-tested by Claude (Opus 5.5) under Chad Holland's direction. Chad reviewed the outcome summary, not every line. Container and GitHub CI only. S25: NOT VALIDATED for this release.

**Earlier (2026-10-05): RL-1, who released a key** ([docs/RL1_RESULTS.md](docs/RL1_RESULTS.md)). A `release()` record
holds only what the caller wrote: a script passing `by="human:chad"` gives the same entry as any other caller (3 of 3
as registered; `--sabotage` exits 1 because of L1; a no-op sabotage exits 0). The docstring says release is "meant for
a human"; OBS-1's own system releases automatically with `by="system"` (3 sites). No change made: the options are
contract changes. Self-tested by Claude (Opus 5.5), direction only. Container only. S25: NOT VALIDATED.

**Latest (2026-09-30, later): adversarial review of `595446c`** ([docs/REVIEW_595446C.md](docs/REVIEW_595446C.md)).
Nothing was falsely accepted. Five input classes crashed the verifier with exit 1 (indistinguishable from "checks failed"):
non-object top level, `provenance.chain` as a string, ~100,000-deep nesting, `min_coverage` = ±10**400 (a crash my own
`595446c` fix introduced) and 10**400 in vehicle request or telemetry fields. Malformed input is now COULD NOT LOOK (exit 2).
Out-of-range values now fail their check. 15 regression tests; 428 passed; mutants 27 of 27 killed; attack harness all HELD;
`nonfinite_probe.py` now also tries ±10**400 and True/False: 0 fail-open, 0 crash over 8 packages. Container only. S25: NOT VALIDATED.

**Latest (2026-09-30): the issue #5 class, searched everywhere** ([docs/NONFINITE_PROBE.md](docs/NONFINITE_PROBE.md)).
A differential probe over every numeric field of the 8 stored packages found 3 fail-open cases (NaN or
−Infinity in `failed_probes`, −Infinity in `min_coverage` verified CONSISTENT) and 1 crash (`rounds` =
Infinity). Writing the regression test found a fourth: `rounds` = 10¹² ran effectively forever. All four
are fixed; the probe now reports 0 and 0; 413 passed and verifier mutants 27 of 27 killed (container). S25: NOT VALIDATED.

**Latest (2026-09-28): Issue #5 closed** (commit `2902a2c`). Non-finite telemetry and
non-canonical witness prefixes are refused. Registration: [docs/ISSUE_5_RESPONSE.md](docs/ISSUE_5_RESPONSE.md).

**Latest (2026-09-26 evening): 364 passed** (container); verifier mutants 26 of 26 killed; vacuity_lint
0 findings; the Gate's conformance digest unchanged (`44823d0f…0628`). What the day added, each with
its registration and results in the named doc:

- A local model proposes an action on the S25 (docs/MODEL_ACTION.md): B1-B5, B7, B8 confirmed with
  Qwen2.5-1.5B; run 1 answered by a stale TinyLlama server, kept, and caught since by
  `model_file_named`; replies depend on llama-server's prompt cache, now turned off per request.
  Five run-2 packages signed and witnessed (entries 2-6).
- Across chip vendors (docs/PLATFORM_TESTS.md): Intel instruction set changes the reply; the S25 CPU
  reproduces the Intel SSE build byte for byte; the Adreno Vulkan path silently corrupts output
  (every run on the phone needs `--device none` or the Vulkan backend removed); Qualcomm's OpenCL
  path works; an NVIDIA-hosted model found that the verifier ignored unknown keys, and sv.package/0
  is now closed (`schema_closed`). AMD, Broadcom, Cerebras: not tested (no hardware or key).
- A simulated drone (docs/VEHICLE_ACTION.md): V1-V11 in ArduCopter SITL; a slow GPS spoof walks the
  vehicle 61 m outside its fence with every check passing (V11); a cross-check against an
  independent position (a stand-in, not a sensor) refuses it (V12), and flaps at its threshold
  (V12c refuted); the V13 latch removes the flapping. V14 (docs/V14_CORRIDOR_RESULTS.md): the check runs
  only at request time, so a spoof started after the ALLOW is unbounded in a model (117.5 m); re-run every
  reading it bounds the breach at about 31 m, if the second source is independent and LAND does not
  navigate by GNSS. Simulation only; not for GNSS-contested use.
- Issue #4 (docs/ISSUE_4_RESPONSE.md): all eleven breaks accepted; B4 and B11 fixed; the rest
  assigned to sv.gate/1.
- Issue #5 (docs/ISSUE_5_RESPONSE.md): two implementation defects accepted and fixed (non-finite
  checker, non-canonical witness anchor). Credit: Nicholas Kouns.

Open: V14i (the in-flight monitor on SITL); sv.gate/1 and sv.package/1 (issue #4); B6b and a second-author implementation; G1 (record
the server's devices in model packages).

**213 passed** @ 2033088 (Termux / S25, 16.01 s). Measured thermal status on the S25: at rest `normal` -> ALLOW; after 30 s all-core load `hot` (cpu_core 103.8 °C) -> DEFER; both packages 19 of 19 checks, the verifier recomputing the status. Limits uncalibrated (policy `s25-uncalibrated-v0`). See `docs/EVIDENCE_PACKAGE.md`.

Gate contract (2026-09-26, CONTRACT.md, docs/GATE_CONTRACT.md): **261 passed** (container). The kernel
and the verifier match all 4690 vectors (conformance digest `44823d0f…0628`); 22 of 23 rules are
pinned by a vector and the 23rd cannot be reached. Same digest on the S25 (261 passed, Termux) and all 9 CI jobs. Quality is now read only from numbers (F2: `true`
used to pass a quality floor); the 4608-case digest is unchanged. No outside implementation yet.

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

`__version__ = "0.2.0"`. Until v0.2.0, `__init__.py` said 0.1.1 and `pyproject.toml` said 0.1.0; both now agree.
