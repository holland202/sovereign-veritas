# STATUS — Verified vs. Unverified

Only claims supported by recorded runs appear below.

---

## VERIFIED — automated tests (Termux / S25)

| Field | Value |
|-------|-------|
| Branch | `feature/bounded-multi-step-planner` |
| SHA | `d813833b5e09b859b9a8940a783b78a3c36d08e0` |
| Result | **110 passed** |
| Host | Galaxy S25 / Termux |
| Working tree | clean |

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

## MEASURED — Physical interruption

| Run | Method | recovered_ok | count | notes |
|-----|--------|--------------|-------|-------|
| SIGKILL #1 | sigkill | true | 2226 | SM-S938U; manifest running |
| SIGKILL #2–#5 | — | pending | — | same SHA; new dirs |

See `docs/PHYSICAL_DURABILITY_RUNS.md`.

**claim:** per-run only. Not power-loss; not reliability statistics until n grows.

---

## NOT YET MEASURED

- Full SIGKILL matrix (5)
- termux-force-stop / device-reboot / genuine power-loss
- Long-running soak
- Multi-writer B/C
- Distribution shift, motivated adversary, real-task E2E

---

## Version

`__version__ = "0.1.1"`
