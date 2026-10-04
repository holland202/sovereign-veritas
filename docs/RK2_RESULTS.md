# RK-2 results: a reserved idempotency key closes RK-1's fresh-id retry, X4 and X5, if callers fix the key at intent (12 of 12 as registered)

Registration: `docs/RK2_PREREG.md`, commit 262c23a (pushed 2026-10-04 05:49 -0500), before
`sovereign_veritas/idempotency.py`, the workflow change and `tools/rk2_probe.py` existed. Baseline main 2c825b8.
Each mode was run once, in a Linux container. **NOT VALIDATED on the S25**: the file store on Android storage is
untested. Claude-assisted (Claude Opus 5.5). Chad Holland directed it. He has not reviewed this text or the code
line by line. The merge is his decision.

## What it does not fix, and what to watch (first)
1. **A fresh key per attempt still runs twice (A3: 2 effects).** The protection exists only if the caller fixes
   the key when the intent is created. That is a requirement on callers, not something this code can enforce.
2. **In A1 the retry was refused by PR #8's record_id check, not by the key**, because A1 reuses the record_id.
   A2 (fresh record_id, same key) is the case that shows the key itself holding.
3. **Fail closed costs liveness.** An expired lease is never taken over (A7). Keys in UNKNOWN wait for a person
   to `release` them. How often that would happen is unmeasured.
4. **A6 holds the effect at 1, but the ledger has 0 records.** The reservation is then the only trace that the
   effect happened. Reservation and record are two writes, not one transaction.
5. **Packages and the verifier don't carry reservations.** `execution_status: UNKNOWN` appears only on the new
   keyed path. The verifier has not been taught it (RK-3, unrun).
6. The design came from two Moltbook comments by AI agents (`maies`, `heejin`). The fail-closed lease policy is
   ours and differs from theirs.

7. **Keys are compared byte for byte (found 2026-10-04, after the registered run).** The file store names each
   reservation file by `sha256` of the key, and the memory store uses the key as a dictionary key, so "café" in
   NFC and in NFD are two keys. A caller that re-normalizes its key between attempts can run the action twice.
   Pinned by a test, not fixed. This new hash also refuted JG-2's P1 in CI at this branch's head `2b7f8a2`; see
   [JG-2 Amendment 1](JG2_PREREG.md#amendment-1-2026-10-04-after-a-failure-the-text-above-is-unchanged).

## Outcome
| ID | Case | Result |
|---|---|---|
| R1 | timeout, retry same key and same record_id | HELD: 1 effect, refused, record `UNKNOWN`, key UNKNOWN |
| R2 | timeout, retry **fresh record_id, same key** (RK-1's attack) | HELD: **1 effect** (RK-1: 2) |
| R3 | fresh record_id **and fresh key** | HELD: 2 effects (stated limit) |
| R4 | R2 across processes (file store and file ledger rebuilt from disk) | HELD: 1 effect |
| R5 | race, same key, 50 trials (X4 had 2 effects) | HELD: 0 of 50 doubled (memory), 0 of 50 (two file-store objects) |
| R6 | effect, then record write fails, then retry (X5) | HELD: 1 effect, retry refused (key COMPLETED), 0 records |
| R7 | lease expired (crashed holder) | HELD: 0 effects, refused, UNKNOWN |
| R8 | lease live | HELD: 0 effects, refused, IN_FLIGHT |
| R9 | release by an operator, then run | HELD: 2 effects in total, history IN_FLIGHT → UNKNOWN → RELEASED |
| R10 | key with no store | HELD: 0 effects, refused before execution |
| R11 | `--sabotage`: a non-atomic store is caught | HELD: 50 of 50 races doubled, exit 1 |
| R12 | regression | HELD: see below |

## R12 regression (verbatim)
pytest (457 existing tests, plus 14 new in `tests/test_idempotency.py`):
```
.....................s.................................................. [ 91%]
........................................                                 [100%]
471 passed, 1 skipped in 58.49s
```
XB-1 `--expect-fix` (no-key path):
```
VERDICT  8 of 8 as registered
```
RK-1 probe (from PR #37) run against this branch. The no-key path is unchanged, so K2 still gives 2 effects:
```
K2: effects=2 records=2 retry_raised=None record_statuses=['FAILED', 'SUCCEEDED'] first_raised='TimeoutError: response lost after the effect was applied'
VERDICT  6 of 6 as registered (RK6: run --sabotage, expect exit 1)
```
Contract digest (Gate untouched):
```
conformance digest 44823d0ff707213ae8bc310ed8b21e135f8e742fd8834e8f9474743d3a250628  (expected 44823d0ff707213ae8bc310ed8b21e135f8e742fd8834e8f9474743d3a250628)
VERDICT  CONFORMS
conformance digest 44823d0ff707213ae8bc310ed8b21e135f8e742fd8834e8f9474743d3a250628  (expected 44823d0ff707213ae8bc310ed8b21e135f8e742fd8834e8f9474743d3a250628)
VERDICT  CONFORMS
```

## Output, normal run (verbatim)
```
A1 effects=1 records=1 retry='ValueError: duplicate record_id refused before execution: a1' statuses=['UNKNOWN'] key_state='UNKNOWN' first='TimeoutError: response lost after the effect was applied'
A2 effects=1 records=1 retry="ReservationRefused: idempotency key 'K-a2' is UNKNOWN: refused before execution"
A3 effects=2 records=2 retry=None
A4 effects=1 retry="ReservationRefused: idempotency key 'K-a4' is UNKNOWN: refused before execution" key_state='UNKNOWN'
A5 doubled_trials_memory='0 of 50' doubled_trials_file='0 of 50' memory_store='MemoryReservations'
A6 effects=1 records=0 first='OSError: simulated write failure (disk full)' retry="ReservationRefused: idempotency key 'K-a6' is COMPLETED: refused before execution" key_state='COMPLETED'
A7 effects=0 retry="ReservationRefused: idempotency key 'K-a7' is UNKNOWN: refused before execution" key_state='UNKNOWN'
A8 effects=0 retry="ReservationRefused: idempotency key 'K-a8' is IN_FLIGHT: refused before execution" key_state='IN_FLIGHT'
A9 effects=2 retry=None released_history=['IN_FLIGHT', 'UNKNOWN', 'RELEASED']
A10 effects=0 error='ValueError: idempotency_key given but no reservation store: refused before execution'

mode: normal
  R1   HELD
  R2   HELD
  R3   HELD
  R4   HELD
  R5   HELD
  R6   HELD
  R7   HELD
  R8   HELD
  R9   HELD
  R10  HELD
VERDICT  10 of 10 as registered (R11: run --sabotage, expect exit 1; R12: regression, run separately)
exit 0
```

## Output, `--sabotage` (verbatim)
```
A1 effects=1 records=1 retry='ValueError: duplicate record_id refused before execution: a1' statuses=['UNKNOWN'] key_state='UNKNOWN' first='TimeoutError: response lost after the effect was applied'
A2 effects=1 records=1 retry="ReservationRefused: idempotency key 'K-a2' is UNKNOWN: refused before execution"
A3 effects=2 records=2 retry=None
A4 effects=1 retry="ReservationRefused: idempotency key 'K-a4' is UNKNOWN: refused before execution" key_state='UNKNOWN'
A5 doubled_trials_memory='50 of 50' doubled_trials_file='0 of 50' memory_store='NON-ATOMIC (sabotage)'
A6 effects=1 records=0 first='OSError: simulated write failure (disk full)' retry="ReservationRefused: idempotency key 'K-a6' is COMPLETED: refused before execution" key_state='COMPLETED'
A7 effects=0 retry="ReservationRefused: idempotency key 'K-a7' is UNKNOWN: refused before execution" key_state='UNKNOWN'
A8 effects=0 retry="ReservationRefused: idempotency key 'K-a8' is IN_FLIGHT: refused before execution" key_state='IN_FLIGHT'
A9 effects=2 retry=None released_history=['IN_FLIGHT', 'UNKNOWN', 'RELEASED']
A10 effects=0 error='ValueError: idempotency_key given but no reservation store: refused before execution'

mode: SABOTAGE (non-atomic memory store in A5)
  R1   HELD
  R2   HELD
  R3   HELD
  R4   HELD
  R5   NOT HELD
  R6   HELD
  R7   HELD
  R8   HELD
  R9   HELD
  R10  HELD
VERDICT  9 of 10 as registered (R11: run --sabotage, expect exit 1; R12: regression, run separately)
exit 1
```

## Door (unrun)
RK-3: carry the reservation history in `sv.package`, and have the verifier check that an ALLOW with an effect has
exactly one COMPLETED reservation for its key.
