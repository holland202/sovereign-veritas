# Threat model — Sovereign Veritas (as of `dfcbee1`, 2026-10-07; T31–T32 added from HV-1)

**Status:** self-tested. Written by Claude (Opus 5.5) from this repository's code, tests and results; no outside
reviewer has checked it. Each row names its evidence. A row is only as strong as that evidence, and most of the evidence
comes from the same author's tests. Companion document: `docs/PRODUCTION_GAP_ANALYSIS.md`.

## 1. What is protected, and what is claimed

| ID | Objective (the project's claim, in its own terms) | Holds today? |
|---|---|---|
| O1 | Fail closed: the Gate never ALLOWs when declared evidence is insufficient under `CONTRACT.md` | within the contract: 4690 vectors, a 4608-case lattice, 19 of 19 planted Gate bugs caught. Outside it, `ports/go` fails open on input types the contract does not define (`docs/DIFFERENTIAL_RESULTS.md`) |
| O2 | A package that verifies CONSISTENT agrees with itself and with the documented Gate | yes, within the closed schema. The field sweep pins which fields can be rewritten undetected (`tests/test_field_sweep.py`) |
| O3 | `authenticity=SIGNED:<id>` means the named identity's key signed these exact bytes | narrower than it reads: a key listed **today** for that identity, by name or (now visibly) by pattern. No signing time, no revocation (`docs/KL1_RE1_RESULTS.md`) |
| O4 | `LATEST_WITNESSED(n)` means newest among packages the author logged | yes, for order. No time, unsigned log, and only a log the relying party pulled itself |
| O5 | A consumer does not act twice on one package or accept a rolled-back log | yes after the RP-1, K1, F3 and F4 fixes, and also for byte-rewritten copies (`tests/test_metamorphic.py`). Unprotected on first use |
| O6 | An action executes at most once per intent, never without a durable record | **not** in `EvidenceWorkflow` without idempotency keys (XB-1 X4/X5 open). With keys, it holds if callers fix the key at intent (RK-2). In the EX-1 prototype it holds in every tested crash case, but the prototype is not joined to the workflow |
| O7 | A ledgered revocation reaches the decision | only when the workflow is given `capability_registry` (custody fix `ca8ba8b`). Otherwise the passed object decides |

## 2. Actors

| ID | Actor | Can do | In model? |
|---|---|---|---|
| A1 | honest but mistaken integrator or orchestrator | calls APIs in the wrong order, omits evidence, reuses ids | yes (EX-1 fixes 1–3, F2b, the planner assert) |
| A2 | malicious package producer | writes any bytes; reseals every digest | yes |
| A3 | holder of a leaked signing key | signs anything as the listed identity | yes, as a stated limit (KL-P8) |
| A4 | whoever controls the witness log host or transport | serves rollbacks, rewrites, huge logs | partly: rollback after first use; size (RE-P4/P5) |
| A5 | lying executor | issues valid receipts for effects that did not happen | yes (EX-1 X6) |
| A6 | lying observer | records false confirmations | **no** |
| A7 | local attacker with filesystem write access | edits journals, state files, allowed-signers, `PATH` | partly: edits are detected (journal chain, admission on read), whole rewrites are not; `PATH` is trusted |
| A8 | network attacker between the source and the relying party | substitutes or replays packages | yes: covered by signature and witness checks when used |
| A9 | resource-exhaustion attacker | very large or deep inputs | yes (RE-1) |
| A10 | misconfiguration | pattern principals, unpinned dependencies | partly (KL-P5 fixed; `docs/SUPPLY_CHAIN.md`) |
| A11 | compromised CI or supply chain | moves an action tag; poisons a dependency | documented, not mitigated |

## 3. Trust boundaries and assumptions

- **Untrusted input:** package files, witness logs, receipts, journal contents read back from disk, executor return values.
- **Trusted by assumption, not checked:**
  - the relying party's allowed-signers file;
  - the system's `ssh-keygen`;
  - the Python runtime;
  - the filesystem's `fsync` (power loss is not tested on hardware);
  - the process's `PATH`.
- **Never trusted for security:** clocks (every timestamp is declared; `at.source` in journal events says "local clock
  (not trusted)"); `verifier_id`; DEFAULTED runtime values, although the Gate still counts them as healthy (open, F1).

## 4. Threats

Status: **MITIGATED** (a fix with a test that fails without it), **LIMIT** (stated by design, still true), **OPEN** (a
defect or gap without a fix), **NOT TESTED**. The evidence status is in brackets.

| ID | Threat | Actor | Status | Evidence | Residual |
|---|---|---|---|---|---|
| T1 | parser differential through duplicate keys | A2 | MITIGATED [MEASURED] | DK, `loads_bounded` | — |
| T2 | NaN, Infinity or overflowing numbers verify or crash | A2 | MITIGATED [MEASURED] | `48ab26a`; review F6a/F6b (`c7a9ee8`) | `EvidenceRecord`/`FileLedger` still accept NaN (sv.gate/1) |
| T3 | nesting depth (crash, or a platform-dependent verdict) | A2 | MITIGATED [MEASURED] | depth 64; early exit (RE-P3) | — |
| T4 | input size exhausts memory or time | A9 | **OPEN** [MEASURED] | a 100 MB package verifies CONSISTENT, 401 MB peak (RE-P1) | no size cap (EXPERIMENT FIRST) |
| T5 | exhaustion reported as "a check failed" or REFUSED | A9 | MITIGATED [MEASURED] | RE-P2/P5 fix, `tests/test_kl1_re1.py` | Android's memory killer acts first (not tested) |
| T6 | rewrite of unbound fields (timestamps, uncertainty, record ids, ...) | A2 | LIMIT [MEASURED] | `tests/test_field_sweep.py` UNBOUND pin; 405 of 796 single-field rewrites verify unsigned | closed by a signature, not by consistency |
| T7 | fully consistent rewrite, unsigned | A2 | LIMIT [MEASURED] | every package's `known_limitations` | — |
| T8 | leaked key signs forgeries | A3 | LIMIT [MEASURED] | KL-P8 | no revocation in force (T10) |
| T9 | rotation or expiry makes genuine old packages fail like forgeries | — | LIMIT [MEASURED] | KL-P2/P3; SSHSIG has no signing time (KL-P7) | needs a witness clock (EXPERIMENT FIRST) |
| T10 | revocation lists ignored | A3 | **OPEN** [MEASURED] | KL-P4: still SIGNED; `ssh-keygen -r` would refuse | `--revocation-list` (EXPERIMENT FIRST) |
| T11 | pattern principal names an identity the signer was not listed under | A10 | MITIGATED [MEASURED] | KL-P5 fix; 8 listing cases | pattern entries are still accepted, only labelled |
| T12 | signature reused across purposes (package ↔ receipt) | A2/A5 | MITIGATED [MEASURED] | KL-P6; EX-1 X5 `wrong_namespace` | — |
| T13 | replay to a consumer, including byte-rewritten copies | A8 | MITIGATED [MEASURED] | RP-1 fix; metamorphic tests | first use |
| T14 | witness rollback or rewrite | A4 | MITIGATED after first use [MEASURED] | consumer anchor tests | first use; the log is unsigned |
| T15 | a crashed consumer blocks every later one | A9 | MITIGATED [MEASURED] | K1 (`7a1f08b`) | — |
| T16 | double accept through a symlinked state file; silent authentication skip | A1/A7 | MITIGATED [MEASURED] | F4, F3 (`c7a9ee8`) | — |
| T17 | two effects through a repeated `record_id` | A1 | MITIGATED for sequential repeats [MEASURED] | PR #8; F2 across ledger instances (`c7a9ee8`) | a two-thread race without keys (XB-1 X4) |
| T18 | an effect with no record | A1 | **OPEN** in `EvidenceWorkflow` [MEASURED]; removed in the EX-1 prototype [MEASURED] | EX-1 X3: `effects=1 ledger_records=0`, 2 of 2 | join the journal to the workflow (X9, registered, unrun) |
| T19 | a lying executor's receipt reads as confirmation | A5 | LIMIT [MEASURED] | EX-1 X6: EFFECT_ATTESTED alone, EFFECT_DISPUTED with an observer | requires an independent observer |
| T20 | a caller writes a transition without its evidence (journal) | A1 | MITIGATED in the prototype [MEASURED] | EX-1 fixes 1–3, 23 of 24 mutants killed | the actor is declared, not authenticated |
| T21 | journal rewritten wholesale | A7 | LIMIT [MEASURED] | the chain is unkeyed; a forged-signature receipt reads as valid on disk (pinned limit test) | keyed or witnessed journal (EXPERIMENT FIRST) |
| T22 | a revocation does not reach the decision | A1 | MITIGATED when a registry is passed [MEASURED] | custody R1–R3 | callers who pass no registry |
| T23 | DEFAULTED runtime values counted as healthy | A1 | **OPEN** [MEASURED] | `docs/INTEGRATION.md` F1 | sv.gate/1 |
| T24 | a slow GPS spoof inside the checks | external | **OPEN** for GNSS-contested use [MEASURED in simulation] | V11 (61 m); V12/V14 are models | not for contested environments |
| T25 | supply chain: moved action tag, unpinned dependency | A11 | **OPEN** [OBSERVED] | `docs/SUPPLY_CHAIN.md` | pin to SHAs (owner) |
| T26 | `python -O` strips a safety `assert` | A1 | MITIGATED [MEASURED] | planner fix | none other found by bandit |
| T27 | Windows: the anchored ledger executed, then refused | platform | MITIGATED (refusal now comes first) [MEASURED, CI] | `test_f2_without_flock_the_refusal_comes_before_the_effect` | the anchored ledger is still POSIX-only |
| T28 | declared timestamps and `verifier_id` | A2 | LIMIT [MEASURED] | field sweep; `known_limitations` | — |
| T29 | out-of-contract inputs fail open in a port | A2 | OPEN for `ports/go` [MEASURED] | 2 fail-open DISAGREE cases | sv.gate/1 rule 0 (EXPERIMENT FIRST) |
| T30 | a lying observer confirms an effect that did not happen | A6 | NOT TESTED | — | out of model |
| T31 | an adapter turns copies, stale readings or one spoofed modality into `independent_corroboration` | external spoofer; A1 (the adapter) | **OPEN** outside the Gate [MEASURED in simulation] | HV-1: false ALLOW `naive` 4980/8000 `copy_spoof`, 1664/4003 `stale`; `provenance` 2108/8000 `common_mode`; `diverse` 4/8000 `common_mode`, where honest odometry error passed the margin (`docs/HV1_RESULTS.md`) | the Gate decided correctly on its inputs in every traced trial. Adapter contract (HV-1b, EXPERIMENT FIRST) |
| T32 | a dissenting reading raises an evidence-quality number, and the action passes | A1 (the adapter) | **OPEN** for quality computed from available readings [MEASURED in simulation] | HV-1 `legal_release copy_spoof`: `naive` ALLOW 979/979 with the dissenting attorney reading present, 0/1021 without it | provenance-based adapters 0/979; quality from distinct, fresh, authenticated sources |

## 5. Ranked residual risk (what I would fix first)

1. **T18:** the user-facing workflow can still produce an effect with no record. The fix exists only in a prototype.
2. **T23:** defaults count as healthy. It is silent, and it affects every package made without explicit runtime values.
3. **T10/T9:** key compromise cannot be handled without losing every old package (no revocation, no signing time).
4. **T4:** no input size cap. Any verifier or consumer can be made to use 4× the input size in memory.
5. **T25:** CI runs code from movable tags, including one third-party action, with the repository's token.
6. **T21/T20:** journal integrity rests on an unkeyed chain and declared actors.
7. **T24/T29/T31/T32:** contract-external inputs, physical-world spoofing and adapter-side laundering are outside the
   decision's reach. The Gate decides on what an adapter gives it.

## 6. Not modelled

- Hardware faults and power loss.
- Android storage semantics.
- Multi-host deployments.
- Side channels.
- A malicious Python runtime or `ssh-keygen`.
- Social engineering of the key holder.
- Legal or regulatory evidentiary standards: CONSISTENT is not "admissible".
