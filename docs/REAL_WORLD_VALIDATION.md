# Real-World Validation

**Status:** Stage 0 implemented and device-tested. Stage 1 harness implemented
(characterization only).

## Claim discipline

| Evidence level | What you may claim |
|----------------|--------------------|
| Unit/integration tests | Implemented behavior passes specified tests |
| Fault injection (Stage 0) | Specified synthetic fault model rejected/contained |
| Concurrency characterization (Stage 1) | Measured multi-process outcomes under stated parameters |
| Device soak | Measured behavior under stated workload/window |
| Distribution shift | Measured performance on held-out shifts |
| Motivated red-team | Behavior under documented attack set |
| Real-task evaluation | Measured usefulness on stated task |

Passing one row does **not** upgrade the claim to the next row.

**Concurrency safety is never inferred from a green unit suite.**

## Stage 0 — Deterministic fault injection (implemented)

Module: `sovereign_veritas.validation.ValidationSuite`

Checks: ledger restart, torn persistence, duplicate writer identity, hostile
persistence.

Allowed claim: specified synthetic fault model rejected/contained.

## Stage 1 — Concurrency characterization (harness implemented)

Module: `sovereign_veritas.concurrency.ConcurrencyProbe`

Spawns N processes that append unique `record_id`s to one FileLedger path.
Report fields include per-worker success/error counts, `reload_ok`,
`final_record_count`, `unique_ids_on_disk`, file size.

Allowed claim:

> Measured multi-process append behavior under the stated process_count and
> records_per_process.

**Not** claimed: concurrency-safety, locking correctness, or loss-free
interleaving. A clean reload is a data point, not a guarantee.

Recommended device experiment:

```bash
python -c "
from pathlib import Path
from sovereign_veritas.concurrency import ConcurrencyProbe
import json
r = ConcurrencyProbe(Path('/tmp/sv-conc')).run(process_count=4, records_per_process=50)
print(json.dumps(r.to_dict(), indent=2))
"
```

Record the full JSON (or a hash of it) alongside device, Python version, and
filesystem notes before any safety language appears in STATUS.

## Stage 2 — Physical durability on S25 (not implemented)

Termux interruption during writes, restart, recovery.

## Stage 3 — Long-running soak (not implemented)

1h → 6h → 24h with thermal/resource notes where available.

## Stage 4 — Distribution shift (not implemented)

## Stage 5 — Motivated adversary (not implemented)

## Stage 6 — Real task integration (not implemented)
