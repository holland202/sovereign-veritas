# STATUS — Verified vs. Unverified

This document states only what has been checked by running the code.
"Verified" means a test targeting the actual claim passes on the recorded
checkout. It does not mean the system is generally trustworthy or autonomous.

---

## VERIFIED — in this repo, tests pass

### Integration suite (adversarial + evidence quality + CapabilityGovernor)

| Field | Value |
|-------|-------|
| Branch | `feature/integration-evidence-quality-adversarial` |
| SHA | `116824cbcc2a66a6dcddc805227adbab676e8fd6` |
| Command | `pytest -q` |
| Result | **89 passed in 0.17s** |
| Working tree | clean |
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
boundary was implemented and exercised in this lineage (see commit history
from `360e02b` / `dfdeee7`).

---

## NOT YET VERIFIED AS INTEGRATED

These exist as design targets, partial code, or external modules. They are
**not** claimed as integrated production capability:

- On-device thermal / NPU / HTP runtime probes as Gate inputs
- Keystore or hardware attestation anchoring
- Independently attested third-party evidence packages
- Multi-step governed planner (bounded sequence of atomic Gate actions)
- Full SWAY experiment matrix (P0–P4) with registered predictions
- Validation domains (HAI, BATADAL) wired through the kernel
- Research plugins (Principia, QUASAR, …) behind stable interfaces
- Scale testing beyond current ledger sizes

---

## Version

`__version__ = "0.1.1"`

Version does not advance until a new measured integration claim is recorded
here with SHA, command, and result.

---

## Promotion rule

Target → implemented only after code + tests + measured behavior + known
failures + reproducibility information support the claim.
