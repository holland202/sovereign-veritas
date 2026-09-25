# STATUS — Verified vs. Unverified

Only claims supported by recorded runs appear below.

---

## VERIFIED — automated tests (Termux / S25)

| Field | Value |
|-------|-------|
| Branch | `feature/bounded-multi-step-planner` |
| Tip at measurement | `e1da8fd` |
| Command | `pytest -q` |
| Result | **110 passed in 0.67s** |
| Host | Galaxy S25 / Termux |

---

## MEASURED — Stage-1 concurrency (frozen)

| Metric | Baseline + control |
|--------|--------------------|
| Workload | 4 processes × 50 records |
| Expected unique IDs | 200 |
| Succeeded / on disk | 100 / 100 |
| reload_ok | **false** |
| Error | chain broken at index 2 |
| file_size_bytes | 44298 |

**Contract:** single-writer SUPPORTED; concurrent writers UNSUPPORTED; corruption → FAIL CLOSED.  
Option A in force. B/C require re-measure against this baseline.

---

## MEASURED — Stage-2 software durability (Termux / S25)

### Clean restart

| Field | Value |
|-------|-------|
| mode | `clean` |
| target_records | 100 |
| written | 100 |
| reload_ok | **true** |
| recovered_count | **100** |
| file_size_bytes | 43918 |

Allowed claim: under the clean single-writer restart model, 100 records were persisted and fully recovered.

### Torn final line

| Field | Value |
|-------|-------|
| mode | `torn_last_line` |
| written (complete) | 50 |
| reload_ok | **false** |
| reload_error | `ValueError: invalid JSON at ledger index 50` |
| notes | partial JSON line appended deliberately |

Allowed claim: incomplete trailing JSON is detected; reload refused (fail closed).

**claim_level:** `durability_characterization` only.  
**Not measured:** physical power loss, battery pull, sudden device shutdown, FS journal under power loss.

---

## NOT YET MEASURED

- Physical S25 interruption / power-loss durability
- Long-running soak (1h / 6h / 24h)
- Multi-writer designs B (flock) / C (per-process + merge)
- Distribution shift, motivated adversary, real-task end-to-end

---

## Version

`__version__ = "0.1.1"`
