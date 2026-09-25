# STATUS — Verified vs. Unverified

This document states only what has been checked by running the code.
"Verified" means a test targeting the actual claim passes on the recorded
checkout. It does not mean the system is generally trustworthy or autonomous.

---

## VERIFIED — in this repo, tests pass

### Bounded multi-step planner + Stage-0 validation (current branch tip)

| Field | Value |
|-------|-------|
| Branch | `feature/bounded-multi-step-planner` |
| Prior baseline SHA | `a195f9cbbb896aad81bf306f1eb286f93469e619` |
| Command (Termux / S25) | `pytest -q` |
| Result | **99 passed in 0.16s** (planner suite; recorded by operator 2026-09-24) |

Covered on that run:

- All prior integration invariants (Gate, ledger, adversarial boundary, CapabilityGovernor)
- BoundedMultiStepPlanner preflight + sequential Gate-only execution
- Empty plan / duplicate IDs / max_steps / REFUSE-stops-plan / executor failure

Stage-0 validation suite is **code + unit tests** on this branch; promote to
"device-verified" only after a fresh Termux run that includes
`tests/test_validation.py` is recorded here with SHA and count.

### Integration suite (adversarial + evidence quality + CapabilityGovernor)

| Field | Value |
|-------|-------|
| Branch | `feature/integration-evidence-quality-adversarial` |
| SHA | `116824cbcc2a66a6dcddc805227adbab676e8fd6` |
| Command | `pytest -q` |
| Result | **89 passed** (Termux) |
| Recorded | 2026-09-24 |

Covered invariants include:

- Ledger append-only hash chain and tamper detection
- FileLedger durable custody path
- Gate ALLOW / DEFER / REFUSE with explicit reasons
- Models cannot self-authorize
- Evidence quality thresholds produce DEFER when below bound
- Hierarchical capabilities require authorized parent
- Step bounds refuse when `step_count` exceeds `max_steps`
- CapabilityGovernor records evidence **before** registry mutation
- Failed ledger write → registry **not** changed
- Adversarial epistemic path does not grant authorization authority
- Mandatory adversarial verification does not silently downgrade

### Persistent evidence ledger (earlier milestone)

FileLedger append + fsync + reload + recompute + verify across process
boundary was implemented and exercised in this lineage.

---

## NOT YET VERIFIED AS INTEGRATED

- Stage 1+ real-world validation (concurrency, physical S25 interruption, soak)
- On-device thermal / NPU / HTP runtime probes as Gate inputs
- Keystore or hardware attestation anchoring
- Full SWAY experiment matrix (P0–P4) with registered predictions
- Validation domains (HAI, BATADAL) wired through the kernel
- Research plugins (Principia, QUASAR, …) behind stable interfaces
- Concurrent multi-writer FileLedger safety
- End-to-end local inference producing ledgered evidence on S25

---

## Version

`__version__ = "0.1.1"`

Version does not advance until a new measured integration claim is recorded
here with SHA, command, and result.

---

## Promotion rule

Target → implemented only after code + tests + measured behavior + known
failures + reproducibility information support the claim.
