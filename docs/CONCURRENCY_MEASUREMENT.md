# Concurrency measurement log

## 2026-09-24 — Termux / Galaxy S25

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

### Result (summary)

```
claim_level: concurrency_characterization
process_count: 4
records_per_process: 50
expected_unique_ids: 200
total_succeeded: 100
total_errors: 4
reload_ok: false
reload_error: ValueError: ledger chain broken at index 2
unique_ids_on_disk: 100
file_size_bytes: 44298
```

Workers 2 and 3: 50/50 success.  
Workers 0 and 1: 0 success — `FileLedger` init raised chain-broken after concurrent writes.

### Bounded conclusions

- Current `FileLedger` has **no multi-process writer serialization**.
- Concurrent appends can interleave JSONL lines and/or race `previous_digest`.
- Fail-closed reload works: broken chain is **not** accepted as valid.
- Single-process use remains the supported mode until a locking design is
  implemented and **re-measured** under the same probe.

### Next engineering options (not yet chosen)

1. Document single-writer invariant only (policy).
2. Advisory `flock` around append + load (measure again).
3. Per-process ledgers + merge/verify tool (measure again).

None of these are done until code + probe re-run support the claim.
