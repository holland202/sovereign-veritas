# STATUS — Verified vs. Unverified

Only claims supported by recorded runs appear below.

---

## VERIFIED — automated tests (Termux / S25)

| Field | Value |
|-------|-------|
| Branch | `feature/bounded-multi-step-planner` |
| Result | **110 passed** |
| Host | Galaxy S25 / Termux |

---

## MEASURED — Stage-1 concurrency (frozen)

4 × 50 → chain broken, fail closed.  
**Single writer SUPPORTED; concurrent writers UNSUPPORTED.**

---

## MEASURED — Stage-2 software durability

| Mode | Result |
|------|--------|
| clean 100 | recovered 100 |
| torn_last_line | reload refused |

---

## MEASURED — Physical SIGKILL (n=2)

| Run | recovered_ok | count | ledger_sha256 (prefix) |
|-----|--------------|-------|------------------------|
| #1 | true | 2226 | `45889465…` |
| #2 | true | 2810 | `0b364791…` |
| #3–#5 | pending | — | — |

Device: SM-S938U / Android 16. Both runs: `manifest_status=running`.  
**claim:** 2/2 measured SIGKILL recoveries verified. Not a reliability rate; not power-loss.

See `docs/PHYSICAL_DURABILITY_RUNS.md`.

---

## NOT YET MEASURED

- SIGKILL #3–#5, force-stop, reboot, power-loss
- Soak / scale / recovery-time matrix
- Multi-writer B/C
- Gate-level durability signal

---

## Version

`__version__ = "0.1.1"`
