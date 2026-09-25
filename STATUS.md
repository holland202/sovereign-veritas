# STATUS — Verified vs. Unverified

Only claims supported by recorded runs appear below.

---

## VERIFIED — automated tests (Termux / S25)

| Field | Value |
|-------|-------|
| Branch | `feature/bounded-multi-step-planner` |
| Result | **110 passed** (Termux; tip at durability harness era) |
| Host | Galaxy S25 / Termux |

---

## MEASURED — Stage-1 concurrency (frozen)

4 × 50 → 100/200 unique IDs, `reload_ok=false`, chain broken at index 2.  
**Single writer SUPPORTED; concurrent writers UNSUPPORTED.** Option A in force.

---

## MEASURED — Stage-2 software durability

| Mode | Result |
|------|--------|
| clean 100 | reload_ok true, recovered 100 |
| torn_last_line 50 | reload_ok false, invalid JSON at index 50 |

---

## MEASURED — Physical interruption (n=1)

| Field | Value |
|-------|-------|
| Method | **sigkill** |
| Device | SM-S938U / Android 16 |
| manifest_status | running |
| recovered_ok | **true** |
| recovered_count | **2226** |
| ledger_sha256 | `458894656f0d897a4b5b8afcf0a06d222c3a9268e974eff6f0ee4b91d7565c48` |

See `docs/PHYSICAL_DURABILITY_RUNS.md`.  
**claim:** this SIGKILL class, this run only. Not power-loss; not n≥1.

---

## NOT YET MEASURED

- Repeated SIGKILL matrix (suggested 5)
- termux-force-stop / device-reboot / genuine power-loss
- Long-running soak
- Multi-writer B/C
- Distribution shift, motivated adversary, real-task E2E

---

## Version

`__version__ = "0.1.1"`
