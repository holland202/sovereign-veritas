# STATUS — Verified vs. Unverified

This document states only what has been checked by running the code.
"Verified" means a test targeting the actual claim passes on the recorded
checkout. It does not mean the system is generally trustworthy or autonomous.

---

## VERIFIED — in this repo, tests pass

### Planner + Stage-0 validation + concurrency harness (Termux / S25)

| Field | Value |
|-------|-------|
| Branch | `feature/bounded-multi-step-planner` |
| SHA (104-pass tip) | `2d109f01ee8d7ab3846a895e2febcb830892fc25` |
| SHA (107-pass tip) | `7798251c62393700f2129576ac6afc4d7eb705f5` |
| Command | `pytest -q` |
| Result | **107 passed in 0.71s** |
| Host | Galaxy S25 / Termux |
| Recorded | 2026-09-24 (operator) |

Includes: integration kernel, BoundedMultiStepPlanner, Stage-0 ValidationSuite,
Stage-1 ConcurrencyProbe harness tests.

### Integration suite (earlier)

| Field | Value |
|-------|-------|
| Branch | `feature/integration-evidence-quality-adversarial` |
| SHA | `a195f9cbbb896aad81bf306f1eb286f93469e619` |
| Result | **89 passed** (Termux) |

---

## MEASURED — Stage-1 concurrency characterization (Termux / S25)

**Not a safety claim.** This is measured multi-process behavior.

| Field | Value |
|-------|-------|
| Host | Galaxy S25 / Termux |
| Path | `./runtime-concurrency-test` (home-writable; `/tmp` denied) |
| process_count | 4 |
| records_per_process | 50 |
| expected_unique_ids | 200 |
| total_succeeded | 100 |
| total_errors | 4 (workers 0–1 init failures) |
| unique_ids_on_disk | 100 |
| reload_ok | **false** |
| reload_error | `ValueError: ledger chain broken at index 2` |
| file_size_bytes | 44298 |
| claim_level | `concurrency_characterization` |

### Interpretation (bounded)

1. Concurrent appends without serialization **broke the hash chain**.
2. Reload **failed closed** (did not silently accept a broken chain).
3. Two workers completed 50/50; two workers saw a broken chain on open and wrote nothing further.
4. Lost/unaccounted identity slots: 100 of 200 expected unique IDs.

**Allowed claim:** Under these parameters on this device, multi-process FileLedger
append is **not** safe; the suite detected the damage.

**Not claimed:** locking correctness, loss-free interleaving, or that any fix
exists until implemented and re-measured.

---

## NOT YET VERIFIED AS INTEGRATED

- FileLedger multi-writer **serialization / locking** (known gap; measurement above)
- Stage 2+ (physical interruption, soak, distribution shift, motivated adversary)
- On-device thermal / NPU / HTP as Gate inputs
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
