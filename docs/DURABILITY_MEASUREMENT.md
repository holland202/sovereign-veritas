# Durability measurement

## Contract

```
Single-writer continuous append
        ↓
interrupt proxy (clean | torn last line | operator physical interrupt)
        ↓
FileLedger reload
        ↓
valid chain  OR  FAIL CLOSED
```

**claim_level:** `durability_characterization`

Software proxies are **not** physical power-cycle evidence.

---

## Module

`sovereign_veritas.durability.DurabilityProbe`

| Mode | Intent |
|------|--------|
| `clean` | Stop between complete records; expect full recovery |
| `torn_last_line` | After N complete records, write partial JSON; expect fail closed |

---

## Measured — 2026-09-24 Termux / Galaxy S25

Branch tip: `e1da8fd` · Suite: **110 passed**

### Clean

```
mode: clean
target_records: 100
records_written_before_stop: 100
reload_ok: true
recovered_count: 100
file_size_bytes: 43918
```

### Torn final line

```
mode: torn_last_line
target_records: 50
records_written_before_stop: 50
reload_ok: false
reload_error: ValueError:invalid JSON at ledger index 50
notes: appended_partial_json_line_without_newline_close
file_size_bytes: 21949
```

---

## Physical interruption protocol (open)

Use a **disposable** test ledger only (`./runtime-durability-physical/`), never production evidence.

1. Start a long single-writer append loop in Termux.
2. Interrupt (force-stop app / kill -9 / controlled power event if you accept risk).
3. New process: `FileLedger(path)` — record `reload_ok`, error, recovered count, file size.
4. Record: device model, Termux/Android version, Python version, filesystem path, interruption method, wall-clock time, full JSON.
5. Append that record here. Do **not** upgrade claim level without it.

## Relationship to Stage 1

Concurrency remains option A. Durability runs are **single-writer only**.
