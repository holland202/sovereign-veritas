# Physical durability run log

Each entry is one independent experiment. Do not pool runs into a stronger
claim without preserving individual evidence.

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
- Device reboot or battery-pull survival
- Multi-run statistics (n=1)
- Concurrent-writer safety
- All future Termux/Android builds

Artifacts to preserve offline: `SESSION.json`, `durability_ledger.jsonl`,
`RECOVERY.json` for this session.
