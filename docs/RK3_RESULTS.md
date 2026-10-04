# RK-3 results: the lost COMPLETED is closed (0 of 300, against 123 of 300 before); a late holder still doubles, now visibly (all six registered predictions held: 5 of 5 in the run, Q5 under sabotage)

Registration: [`RK3_PREREG.md`](RK3_PREREG.md), committed alone at `d688b2b` before any change. Fix, tests and
probe at `40fe508`. Baseline `main` `1307da7`. Linux x86_64 container, 2 CPUs, Python 3.13.16. **NOT VALIDATED on
the S25.**

Drafted by Claude (Opus 5.5), which also wrote the fix and the probe and judged the results, at Chad Holland's
direction. Chad has not reviewed it line by line. The findings it fixes came from a separate Claude session asked to
read the repository as a hostile reader (`results/rk3/independent_review/`). That is an independent read, but not an
independent person.

## What still fails, first

- **E1 is not fixed, by design: one key can still produce two effects.** If a holder outlives its lease and a
  person releases the key after truthfully seeing no effect yet, the retry runs and then the late holder's action
  lands (Q2: `effects: 2`). Checking that no effect has happened does not show that the earlier attempt can no
  longer produce one. Only a fence checked by the action's target can stop that, and that is what the OBS-1
  interface (frozen at `04bca2d`) tests. What RK-3 changes is that the double is now **on the record**: the late
  holder's completion goes to an append-only late-event log with both tokens, instead of overwriting the new
  holder's entry.
- **E3 is not fixed.** An empty reservation file (a crash between the exclusive create and the write) still reads
  IN_FLIGHT for ever and cannot be released. It blocks the key and causes no double.
- **The race rate is not a field rate.** Q1 hammers the window deliberately: 3 processes reserve continuously, and
  `complete()` lands within ±0.5 ms of expiry. 123 of 300 shows the race exists, not how often it happens in use.

## Outcome

| ID | Prediction | Result |
|---|---|---|
| Q1 | changed store: 0 of 300 trials lose COMPLETED | **HELD**: 0 of 300 |
| Q1c | anti-vacuity: `1307da7`'s store, same harness, same run: at least 1 of 300 | **HELD**: 123 of 300 |
| Q2 | E1 with `lease_s=1`: 2 effects; C's history exactly `IN_FLIGHT, COMPLETED`; one `late_complete` with A's token | **HELD** |
| Q3 | `lease_s=5`: IN_FLIGHT at 1 s, release refused, 1 effect, COMPLETED | **HELD** |
| Q4 | RK-2 10 of 10, its `--sabotage` exits 1; MP-1 5 of 5; full suite passes | **HELD**: 481 passed |
| Q5 | `--sabotage` (token ignored, today's behaviour): Q2 fails, exit 1 | **HELD**: C's history gains a second COMPLETED |

## What changed

1. `reserve()` never writes to an existing key. Expiry is computed when the entry is read, not stored, so nothing
   competes with a late `complete()`. `release()` writes the derived expiry into the history it keeps, so a
   released history still reads `IN_FLIGHT, UNKNOWN (lease_expired), RELEASED`.
2. `reserve()` returns a holder token, stored in the entry. The workflow passes it to `complete()` and `unknown()`.
   A call whose token no longer matches (the key was released, and maybe reserved again) does not touch the entry.
   It appends a `late_complete` or `late_unknown` line with both tokens to `<key hash>.late.jsonl`, read with
   `late_events(key)`. Calls without a token behave as before.
3. `EvidenceWorkflow.run(lease_s=...)`. Default 30 s, as before.

No locks: the test matrix includes Windows. Four unit tests were added in `tests/test_idempotency.py`.

## Output, registered run (verbatim, `results/rk3/run_registered.txt`)

```
Q1   changed store   trials=300 hammers=3 COMPLETED lost=0
Q1c  1307da7 store  trials=300 hammers=3 COMPLETED lost=123
Q2   lease 1 s, holder 2 s, release at 1.2 s: {"a_token": "0e809fe54ca6f5b0", "effects": 2, "effects_at_check": 0, "errors": {}, "final_state": "COMPLETED", "history": ["IN_FLIGHT", "COMPLETED"], "late": [{"at": 1791152936.1828172, "current_token": "89932931a0d3b026", "event": "late_complete", "late_token": "0e809fe54ca6f5b0"}], "release": "accepted", "seconds": 2.0, "state_at_check": "UNKNOWN"}
Q3   lease 5 s, holder 2 s, release at 1.0 s: {"a_token": null, "effects": 1, "effects_at_check": 0, "errors": {}, "final_state": "COMPLETED", "history": ["IN_FLIGHT", "COMPLETED"], "late": [], "release": "refused: release is allowed only from UNKNOWN: 'K-rk3'", "seconds": 2.0, "state_at_check": "IN_FLIGHT"}
Q4   rk2             exit 0 | VERDICT  10 of 10 as registered (R11: run --sabotage, expect exit 1; R12: regression, run separately)
Q4   rk2 --sabotage  exit 1 | VERDICT  9 of 10 as registered (R11: run --sabotage, expect exit 1; R12: regression, run separately)
Q4   mp1             exit 0 | VERDICT  5 of 5 as registered
Q4   pytest          exit 0 | 481 passed in 40.31s

  Q1   HELD
  Q1c  HELD
  Q2   HELD
  Q3   HELD
  Q4   HELD
  Q5   run --sabotage, expect Q2 REFUTED and exit 1
VERDICT  5 of 5 as registered
exit 0
```

## Output, `--sabotage` (verbatim, `results/rk3/run_sabotage.txt`)

```
Q2   lease 1 s, holder 2 s, release at 1.2 s: {"a_token": "4da494fcaad34ada", "effects": 2, "effects_at_check": 0, "errors": {}, "final_state": "COMPLETED", "history": ["IN_FLIGHT", "COMPLETED", "COMPLETED"], "late": [], "release": "accepted", "seconds": 2.0, "state_at_check": "UNKNOWN"}

  Q2   REFUTED
mode: SABOTAGE (complete() ignores the holder token); Q5 holds if Q2 is REFUTED and the exit is 1
VERDICT  0 of 1 under sabotage
exit 1
```

## Not tested

- Two `release()` calls racing each other, or a `release()` racing a late `complete()` with no token. Read from
  the code: both are read-check-write sequences without a lock.
- Android storage, network filesystems, separate machines.

## Next unrun test

E1 against a fenced target: the OBS-1 round-one cases, once Amos Tipton's cases are committed unedited.
