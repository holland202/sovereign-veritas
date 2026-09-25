# STATUS — Verified vs. Unverified

---

## VERIFIED — automated tests

**141 passed** on `feature/bounded-multi-step-planner` @ 9308ce3 (Termux / S25, Python 3.14.6, 7.29 s).

Gate constraint (`tools/gate_constraint.py --mutants`): DIGEST identical on S25 aarch64 and container x86_64;
19/19 mutants killed. See `docs/GATE_CONSTRAINT.md`.

---

## MEASURED — Stage-1 concurrency (frozen)

Concurrent writers UNSUPPORTED (chain broken, fail closed). Single writer SUPPORTED.

---

## MEASURED — Stage-2 software durability

clean recover · torn line fail closed.

---

## MEASURED — Physical SIGKILL (n=3 valid)

| Run | recovered_ok | count | notes |
|-----|--------------|-------|-------|
| #1 | true | 2226 | manifest running |
| #2 | true | 2810 | manifest running |
| #3 | true | 1127 | manifest running; dir `03b` |
| #4–#5 | pending | — | — |

Ctrl+C attempt discarded (`clean_stop`).  
**claim:** 3/3 valid measured SIGKILL recoveries verified. Not a reliability rate; not power-loss.

See `docs/PHYSICAL_DURABILITY_RUNS.md`.

---

## Version

`__version__ = "0.1.1"`
