# Physical durability run log

Each entry is one independent experiment. Do not pool runs into a stronger
claim without preserving individual evidence.

## Measurement baseline (frozen)

| Field | Value |
|-------|-------|
| Branch | `feature/bounded-multi-step-planner` |
| SHA (matrix start) | `d813833` / docs tip `3d834d0` |
| Suite | **110 passed** |
| Runtime dirs | ignored (`runtime-*/`) |

Do not change implementation between SIGKILL matrix runs.

---

## Run 2026-09-24 — SIGKILL #1

| Field | Value |
|-------|-------|
| Host | Samsung SM-S938U / Android 16 / Termux / CPython 3.14.6 |
| interruption_method | `sigkill` |
| session_id | `1790301674-31060` |
| manifest_status | **running** |
| recovered_ok | **true** |
| recovered_count | **2226** |
| ledger_size_bytes | 1055062 |
| ledger_sha256 | `458894656f0d897a4b5b8afcf0a06d222c3a9268e974eff6f0ee4b91d7565c48` |
| reload_error | null |

---

## Run 2026-09-24 — SIGKILL #2

| Field | Value |
|-------|-------|
| Host | Samsung SM-S938U / Android 16 / Termux / CPython 3.14.6 |
| interruption_method | `sigkill` |
| session_id | `1790302312-9761` |
| directory | `runtime-durability-physical-02` |
| manifest_status | **running** |
| recovered_ok | **true** |
| recovered_count | **2810** |
| ledger_size_bytes | 1331878 |
| ledger_sha256 | `0b364791b1eff545124a2a90f55f17373f0d77e1f3c1f60dccb8aec7dc4193f1` |
| reload_error | null |

Second `recover` on the same files matched count and SHA-256 (artifact consistency, not a second kill).

---

## Summary so far

| Run | recovered_ok | count | SHA-256 (prefix) |
|-----|--------------|-------|------------------|
| SIGKILL #1 | true | 2226 | `45889465…` |
| SIGKILL #2 | true | 2810 | `0b364791…` |
| SIGKILL #3–#5 | pending | — | — |

**Allowed:** 2/2 measured SIGKILL runs on this device/checkout recovered and verified.  
**Not claimed:** reliable survival rate, power-loss durability, concurrent writers.

---

## SIGKILL #3–#5 — pending

```bash
rm -rf ./runtime-durability-physical-0N
python tools/physical_durability.py writer \
  ./runtime-durability-physical-0N --interval-s 0.01
# other session: kill -9 <PID>
python tools/physical_durability.py recover \
  ./runtime-durability-physical-0N --interruption-method sigkill
```
