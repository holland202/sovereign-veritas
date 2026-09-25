# STATUS — Verified vs. Unverified

This document states only what has been checked by running the code.

---

## VERIFIED — automated tests (Termux / S25)

| Field | Value |
|-------|-------|
| Branch | `feature/bounded-multi-step-planner` |
| SHA | `43fc64e432ae1831786edfff81aeaf0c381b4cf7` (docs baseline) |
| Result | **107 passed** (prior tip; durability adds tests on later tip) |
| Host | Galaxy S25 / Termux |

---

## MEASURED — Stage-1 concurrency (frozen)

| Metric | Baseline | Control (docstring-only tip) |
|--------|----------|------------------------------|
| 4 × 50 expected | 200 | 200 |
| succeeded / unique IDs | 100 / 100 | 100 / 100 |
| reload_ok | false | false |
| error | chain broken at index 2 | chain broken at index 2 |
| file_size_bytes | 44298 | 44298 |

**Contract:** single-writer SUPPORTED; concurrent writers UNSUPPORTED; corruption → FAIL CLOSED.  
**Option A in force.** Options B/C require re-measure against this baseline.

---

## IMPLEMENTED — Stage-2 durability harness

- Module: `sovereign_veritas.durability.DurabilityProbe`
- Modes: `clean` (recover), `torn_last_line` (fail closed)
- claim_level: `durability_characterization` only
- **Not** physical power-cycle until operator records a real interruption

---

## NOT YET VERIFIED

- Physical S25 power/process interruption durability
- Long-running soak (1h / 6h / 24h)
- flock / multi-writer (B) or per-process merge (C)
- Distribution shift, motivated adversary, real-task end-to-end

---

## Version

`__version__ = "0.1.1"`
