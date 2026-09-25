# Physical durability run log

Each entry is one independent experiment. Do not pool runs into a stronger
claim without preserving individual evidence.

## Measurement baseline

Branch `feature/bounded-multi-step-planner` · suite **110 passed** · `runtime-*/` ignored.

**Valid SIGKILL row requires `manifest_status: "running"`.**  
`clean_stop` (Ctrl+C / SIGTERM) is **not** SIGKILL evidence.

---

## SIGKILL #1

| Field | Value |
|-------|-------|
| session_id | `1790301674-31060` |
| manifest_status | running |
| recovered_ok | true |
| recovered_count | 2226 |
| ledger_size_bytes | 1055062 |
| ledger_sha256 | `458894656f0d897a4b5b8afcf0a06d222c3a9268e974eff6f0ee4b91d7565c48` |

## SIGKILL #2

| Field | Value |
|-------|-------|
| session_id | `1790302312-9761` |
| directory | `runtime-durability-physical-02` |
| manifest_status | running |
| recovered_ok | true |
| recovered_count | 2810 |
| ledger_size_bytes | 1331878 |
| ledger_sha256 | `0b364791b1eff545124a2a90f55f17373f0d77e1f3c1f60dccb8aec7dc4193f1` |

## SIGKILL #3

| Field | Value |
|-------|-------|
| session_id | `1790302801-14545` |
| directory | `runtime-durability-physical-03b` |
| pid | 14545 |
| manifest_status | **running** |
| recovered_ok | **true** |
| recovered_count | **1127** |
| ledger_size_bytes | 534136 |
| ledger_sha256 | `a79f5ed6043aa91718aab6cf4433246e2da0794f4221a3fd0a93075afd87a169` |
| reload_error | null |

Host for all: SM-S938U / Android 16 / Termux / CPython 3.14.6.

---

## Discarded (not SIGKILL)

| Attempt | Why discarded |
|---------|----------------|
| physical-03 Ctrl+C | `manifest_status: clean_stop`, 1073 records |

---

## Summary

| Run | valid SIGKILL | recovered_ok | count |
|-----|---------------|--------------|-------|
| #1 | yes | true | 2226 |
| #2 | yes | true | 2810 |
| #3 | yes | true | 1127 |
| #4–#5 | pending | — | — |

**Allowed:** 3/3 valid SIGKILL runs recovered and verified on this device/checkout.  
**Not claimed:** statistical reliability, power-loss, concurrent writers.
