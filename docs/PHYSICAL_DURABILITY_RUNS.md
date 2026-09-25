# Physical durability run log

Each entry is one independent experiment. Do not pool runs into a stronger
claim without preserving individual evidence.

## Measurement baseline (frozen)

| Field | Value |
|-------|-------|
| Branch | `feature/bounded-multi-step-planner` |
| SHA | `d813833b5e09b859b9a8940a783b78a3c36d08e0` |
| Suite | **110 passed** |
| Working tree | clean |
| Runtime dirs | ignored (`runtime-*/`) |

Do not change implementation between SIGKILL matrix runs.

---

## Run 2026-09-24 — SIGKILL #1

| Field | Value |
|-------|-------|
| Host | Samsung SM-S938U (Galaxy S25 Ultra) |
| Android | 16 / SDK 36 |
| Python | 3.14.6 CPython aarch64 (Termux) |
| interruption_method | `sigkill` |
| session_id | `1790301674-31060` |
| manifest_status | **running** (clean-stop handler did not run) |
| recovered_ok | **true** |
| recovered_count | **2226** |
| ledger_size_bytes | 1055062 |
| ledger_sha256 | `458894656f0d897a4b5b8afcf0a06d222c3a9268e974eff6f0ee4b91d7565c48` |
| reload_error | null |

### Allowed claim

Under this single SIGKILL interruption, on this device/path/checkout, the
persisted ledger reloaded and its complete hash chain verified (2226 records).

### Not claimed

- General power-loss durability
- Multi-run statistics (n=1 so far)
- Concurrent-writer safety

Artifacts (offline only): `SESSION.json`, `durability_ledger.jsonl`, `RECOVERY.json`.

---

## SIGKILL #2–#5 — pending

Protocol (same checkout, new directory each time):

```bash
rm -rf ./runtime-durability-physical-0N
python tools/physical_durability.py writer \
  ./runtime-durability-physical-0N --interval-s 0.01
# note PID; from another session: kill -9 <PID>
python tools/physical_durability.py recover \
  ./runtime-durability-physical-0N --interruption-method sigkill
```

Append each recovery JSON summary here after the run. Do not edit prior entries.
