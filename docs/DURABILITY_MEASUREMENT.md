# Durability measurement

## Contract

```
Single-writer continuous append
        ↓
interrupt proxy (clean stop | torn last line | operator SIGKILL)
        ↓
FileLedger reload
        ↓
valid chain  OR  FAIL CLOSED
```

**claim_level:** `durability_characterization`

This is **not** a physical power-cycle or dirty-block-device claim until an
operator runs a real interruption on the S25 and records device/FS/Python.

## Module

`sovereign_veritas.durability.DurabilityProbe`

### Modes

| Mode | Meaning |
|------|---------|
| `clean` | Stop between complete records; reload should recover exact count |
| `torn_last_line` | After N complete records, write a partial JSON line; reload must fail closed |

### Example

```bash
python -c "
from pathlib import Path
from sovereign_veritas.durability import DurabilityProbe
import json

p = DurabilityProbe(Path('./runtime-durability-test'))
print(json.dumps(p.run(target_records=100, mode='clean').to_dict(), indent=2))
print(json.dumps(p.run(target_records=50, mode='torn_last_line').to_dict(), indent=2))
"
```

### Manual physical experiment (operator)

1. Start a long clean run in one Termux session.
2. Force-stop the process mid-write (or power-interrupt if you accept the risk).
3. Restart Python, `FileLedger(path)`, record `reload_ok` / error / count.
4. Append the JSON + device notes to this file. Do not upgrade claim level
   without that record.

## Relationship to Stage 1

Concurrency remains **option A** (single-writer). Durability experiments assume
one writer. Do not mix concurrent writers into durability runs.
