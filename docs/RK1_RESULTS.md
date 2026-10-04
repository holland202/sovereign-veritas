# RK-1 results: a fresh record_id on retry repeats the effect, and the ledger says the first attempt FAILED (7 of 7 as registered)

Registration: `docs/RK1_PREREG.md`, commit 10aa66d (pushed 2026-10-04 05:42 -0500), before `tools/rk1_probe.py`
existed. Baseline main 2c825b8. Each mode was run once, in a Linux container. **NOT VALIDATED on the S25.**
Claude-assisted (Claude Opus 5.5). Chad Holland directed it. He has not reviewed this text line by line.

## What failed (first)
1. **The outside claim is confirmed.** After a timeout that lost the response but not the effect, a retry with
   a **fresh** record_id ran the action again: **2 external effects, 2 records, no refusal** (K2). It is the same
   through a sink rebuilt from disk, as a new process would build it (K3). PR #8's repeat check keys on record_id
   alone, and the caller chooses the id, so a new id is never a repeat.
2. **The ledger tells a false story about the world.** In K2 it says the first attempt `FAILED` and the second
   `SUCCEEDED`. The world received two effects. Even in K1 (same id, retry correctly refused) the only record says
   `FAILED` while the effect happened. After a lost response the honest status is UNKNOWN. The workflow writes
   FAILED for any exception from the executor.
3. **Not blind.** Reading `workflow.py` before the run predicted both, and the registration says so. The probe
   pins the behaviour against a commit and adds controls. It does not add surprise.

## Outcome
| ID | Prediction | Result |
|---|---|---|
| RK0 | one ordinary run: 1 effect, 1 record | HELD |
| RK1 | same id on retry: 1 effect, retry refused before execution | HELD |
| RK2 | that record says FAILED although the effect happened | HELD |
| RK3 | **fresh id on retry: 2 effects, 2 records, no refusal** | HELD |
| RK4 | the same through a sink rebuilt from disk | HELD |
| RK5 | positive control (content-keyed test double): 1 effect, retry refused | HELD |
| RK6 | `--sabotage` (K2 against the test double) breaks RK3, exit 1 | HELD: 5 of 6, exit 1 |

## What it means, and what it does not
- PR #8 stops a caller who repeats the *same* id. It does not stop a caller, or an agent's "helpful recovery",
  that picks a new id for the same action after a timeout. That is the common retry pattern.
- The content-keyed test double is not a fix. Refusing every repeat of an identical action would also block
  legitimate repeats. The registered next step is an idempotency key chosen by the caller and **reserved
  before execution** (written ahead), judged against K1 to K3 and the open X4 and X5.
- The FAILED-versus-UNKNOWN mislabel can be fixed on its own, but a fix changes records that are already
  published, so it is a format decision. Not taken. Chad's decision.
- A counting executor stands in for a real API. Whether a given API applies the effect before timing out is
  not measured.

## Credit
The lead came from the Moltbook agent `hermesagentj`'s comment ("A fresh key on retry is the laundering
vector"), found by the read-only scout. That was an AI agent's claim. This probe tested it against this
repository; it does not validate anything else that agent said.

## Door (unrun)
RK-2: a reserved idempotency key (written ahead of `execute`), registered against K1 to K3, X4 and X5.

## Output, normal run (verbatim)
```
K0: effects=1 records=1 retry_raised=None record_statuses=['SUCCEEDED']
K1: effects=1 records=1 retry_raised='ValueError: duplicate record_id refused before execution: k1' record_statuses=['FAILED'] first_raised='TimeoutError: response lost after the effect was applied'
K2: effects=2 records=2 retry_raised=None record_statuses=['FAILED', 'SUCCEEDED'] first_raised='TimeoutError: response lost after the effect was applied'
K3: effects=2 records=2 retry_raised=None record_statuses=['FAILED', 'SUCCEEDED'] first_raised='TimeoutError: response lost after the effect was applied'
K4: effects=1 records=1 retry_raised='ValueError: duplicate record_id refused before execution: k4-retry' record_statuses=['FAILED'] first_raised='TimeoutError: response lost after the effect was applied'

mode: normal
  RK0  HELD
  RK1  HELD
  RK2  HELD
  RK3  HELD
  RK4  HELD
  RK5  HELD
VERDICT  6 of 6 as registered (RK6: run --sabotage, expect exit 1)
exit 0
```

## Output, `--sabotage` (verbatim)
```
K0: effects=1 records=1 retry_raised=None record_statuses=['SUCCEEDED']
K1: effects=1 records=1 retry_raised='ValueError: duplicate record_id refused before execution: k1' record_statuses=['FAILED'] first_raised='TimeoutError: response lost after the effect was applied'
K2: effects=1 records=1 retry_raised='ValueError: duplicate record_id refused before execution: k2-retry' record_statuses=['FAILED'] first_raised='TimeoutError: response lost after the effect was applied'
K3: effects=2 records=2 retry_raised=None record_statuses=['FAILED', 'SUCCEEDED'] first_raised='TimeoutError: response lost after the effect was applied'
K4: effects=1 records=1 retry_raised='ValueError: duplicate record_id refused before execution: k4-retry' record_statuses=['FAILED'] first_raised='TimeoutError: response lost after the effect was applied'

mode: SABOTAGE (K2 uses the content-keyed test double)
  RK0  HELD
  RK1  HELD
  RK2  HELD
  RK3  NOT HELD
  RK4  HELD
  RK5  HELD
VERDICT  5 of 6 as registered (RK6: run --sabotage, expect exit 1)
exit 1
```
