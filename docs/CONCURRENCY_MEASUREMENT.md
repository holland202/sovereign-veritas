# Concurrency measurement log

## Architectural distinction

**Concurrency failure ≠ evidence-system failure.**

The shared `FileLedger` does not safely serialize multiple writers. Its
integrity checks *did* detect the resulting corruption and refused to load
it (fail closed).

```
Single writer
    ↓
tested / supported behavior

Multiple concurrent writers
    ↓
UNSUPPORTED
    ↓
chain corruption observed
    ↓
reload
    ↓
FAIL CLOSED
```

The unit suite (107 passed) remains valid. This experiment is a separate
empirical result; it does not invalidate those tests.

---

## Stage-1 baseline (frozen)

> **4 × 50 concurrent writers caused chain corruption; reload failed closed.**

Any multi-writer design (options B or C below) must be re-measured against
this exact baseline before a safety or improvement claim.

### 2026-09-24 — Termux / Galaxy S25

Command (home path; `/tmp` PermissionError on this device):

```bash
python -c "
from pathlib import Path
from sovereign_veritas.concurrency import ConcurrencyProbe
import json
r = ConcurrencyProbe(Path('./runtime-concurrency-test')).run(
    process_count=4, records_per_process=50)
print(json.dumps(r.to_dict(), indent=2))
"
```

| Field | Value |
|-------|-------|
| process_count | 4 |
| records_per_process | 50 |
| expected_unique_ids | 200 |
| total_succeeded | 100 |
| unique_ids_on_disk | 100 |
| reload_ok | false |
| reload_error | `ValueError: ledger chain broken at index 2` |
| file_size_bytes | 44298 |
| claim_level | `concurrency_characterization` |

Workers 2 and 3: 50/50 success.  
Workers 0 and 1: 0 success — `FileLedger` init raised chain-broken after concurrent writes.

---

## Engineering options (not yet chosen)

### A — Single-writer policy (current default)

Minimal architectural change.

```
Writer
  ↓
FileLedger
```

Other processes must not write the same path. Documented in `FileLedger`
and STATUS. No code change required beyond the support-boundary text.

### B — flock serialization

```
Process A ─┐
Process B ─┬─ flock ─ FileLedger
Process C ─┘
```

The lock must protect the **entire** sequence:

`load → verify → previous_digest → append → flush/fsync → in-memory state`

not merely the final file write. After implementation, **re-run the same
4 × 50 probe** and compare to the Stage-1 baseline above. Do not declare
victory from code review alone.

### C — Per-process ledgers + merge

Each worker writes its own ledger; a merge/verify tool produces a single
chain. More machinery; may suit distributed local workers. Same rule:
re-measure against the Stage-1 baseline before any safety claim.

---

## Rule

Do not quietly implement B or C and claim success.  
Measure against the frozen baseline first.
