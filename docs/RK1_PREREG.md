# RK-1 registration: a retry with a fresh record_id after a timeout (nothing run under this registration)

Status: registration only. Written 2026-10-04, before `tools/rk1_probe.py` exists.
Claude-assisted (Claude Opus 5.5). Chad Holland gave direction. He has not reviewed this text line by line.

## Origin
A Moltbook comment by the agent `hermesagentj` (on the post "A gate that re-arms on retry was never a gate"),
found by the read-only scout on 2026-10-04: "the idempotency key chosen before the side-effect is what makes the
retry *recovery* rather than a *new write*. A fresh key on retry is the laundering vector." It came from an AI
agent, so it is a lead, not evidence. A second comment, by `matritsaopenclaw` ("A timeout is not a no"), says
an abandoned key moves the ambiguity from the timeout into the store. That relates to the registered gap X5.

## What the code does (read, not run)
`sovereign_veritas/workflow.py::run` refuses a `record_id` the sink already holds, before anything runs (PR #8,
which covers sequential repeats only). When the executor raises, the workflow records the evidence with
`execution_status: FAILED` and re-raises. The repeat check keys on `record_id` alone, and the caller chooses
that id.

## Cases
The executor counts external effects, as in XB-1. The "timeout" executor applies its effect, then raises
`TimeoutError`, so the effect happened but the response was lost. All runs are ALLOW decisions with the same
action and the same `input_digest`.
| case | what |
|---|---|
| K0 | one ordinary run (counting control) |
| K1 | timeout-after-effect, then a retry with the **same** record_id |
| K2 | timeout-after-effect, then a retry with a **fresh** record_id |
| K3 | K2 with a file ledger, the retry made through a sink rebuilt from disk (a new process) |
| K4 | **positive control:** K2 against a test-double sink that also refuses any record with the same `input_digest` and action. This is not a proposed fix. It only shows the probe can see a defence work |

## Predictions (effects, records, refusals)
| ID | Prediction | conf. |
|---|---|---|
| RK0 | K0: 1 effect, 1 record, nothing raised | 0.95 |
| RK1 | K1: 1 effect, 1 record. The retry is refused as a duplicate before execution | 0.9 |
| RK2 | K1's record says `execution_status: FAILED`, although the effect happened: the record is wrong about the world (it should say UNKNOWN) | 0.85 |
| RK3 | **The claim:** K2 gives 2 effects, 2 records, and no refusal. A fresh id launders the retry | 0.9 |
| RK4 | K3 gives the same as K2 | 0.85 |
| RK5 | K4 gives 1 effect. The retry is refused, so the probe can report a defence working | 0.85 |
| RK6 | **Anti-vacuity:** `--sabotage` runs K2 against the K4 sink. RK3 then fails, and the probe exits 1 | 0.9 |

## What it cannot show
- Whether a real external system applies the effect before timing out. This is a counting executor.
- Whether content-keyed refusal is the right fix. It would also block a legitimate repeat of an identical
  action, which is a cost. No fix is made here.
- The concurrency gap (X4) is not retested.
- Container only. NOT VALIDATED on the S25.

## Door (unrun)
RK-2: register a fix in which the caller supplies an idempotency key that is reserved (written ahead) before
`execute`, and judge it against K1 to K3 plus X4 and X5.
