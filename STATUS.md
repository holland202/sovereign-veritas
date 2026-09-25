# STATUS — Verified vs. Unverified

This document states only what has been checked by running the code.
"Verified" means a test targeting the actual claim passes on the recorded
checkout. It does not mean the system is generally trustworthy or autonomous.

---

## VERIFIED — in this repo, tests pass

### Planner + Stage-0 validation (Termux / S25)

| Field | Value |
|-------|-------|
| Branch | `feature/bounded-multi-step-planner` |
| SHA | `2d109f01ee8d7ab3846a895e2febcb830892fc25` |
| Command | `pytest -q` |
| Result | **104 passed in 0.25s** |
| Host | Galaxy S25 / Termux |
| Recorded | 2026-09-24 (operator) |

Includes: integration kernel, BoundedMultiStepPlanner, Stage-0 ValidationSuite.

### Integration suite (earlier)

| Field | Value |
|-------|-------|
| Branch | `feature/integration-evidence-quality-adversarial` |
| SHA | `a195f9cbbb896aad81bf306f1eb286f93469e619` |
| Result | **89 passed** (Termux) |

---

## IMPLEMENTED, NOT YET DEVICE-CHARACTERIZED

### Stage-1 concurrency harness

- Module: `sovereign_veritas.concurrency.ConcurrencyProbe`
- Unit tests exercise the harness (single-process baseline + multi-process run)
- **No concurrency-safety claim.** Record a full `ConcurrencyReport.to_dict()`
  from a real multi-process Termux run before any STATUS promotion.

---

## NOT YET VERIFIED AS INTEGRATED

- Stage 2+ (physical interruption, soak, distribution shift, motivated adversary)
- On-device thermal / NPU / HTP as Gate inputs
- Concurrent multi-writer **safety** (only characterization harness exists)
- Full SWAY P0–P4 measured results
- HAI / BATADAL wired through this kernel
- End-to-end local inference → ledgered evidence on S25

---

## Version

`__version__ = "0.1.1"`

---

## Promotion rule

Target → implemented only after code + tests + measured behavior + known
failures + reproducibility information support the claim.
