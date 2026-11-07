# EO-2 — Can an independent observer close the EO-1 gap, and where does it stop? Registration

**Status:** REGISTRATION. Nothing for EO-2 is built or run at the commit that adds this file, except the
feasibility count below.
**Date:** 2026-11-07. **Base:** `main` at `47df775`.
**Go-ahead:** Chad Holland, 2026-11-07 (choice of EO-2 over the alternatives offered).

## Where the question came from

EO-1 ([docs/EO1_RESULTS.md](EO1_RESULTS.md)) confirmed that SV's record, `WorkflowResult.executed`, the
evidence package and `verify_package.py` report the workflow's account of calling the executor, not an effect.
Its door, E7, named three candidates: a fifth limitation, a renamed check, and an executor-issued effect receipt
that the verifier checks. EO-2 runs that door. It also tests a fourth candidate the EO-1 results did not name: an
**observer that does not go through the executor** reads the target's state before and after the run, and a
checker compares that with the decision. The predictions say which attacks each candidate catches, and where
each one stops.

This is not a new idea. Reading state back after a write instead of trusting the writer's report is ordinary
practice (read-after-write verification, closed-loop control, the defect EO-1 found in the Elyria harness). The
question is narrower: what it catches **in SV**, against EO-1's attacks plus three new ones, and what it rests on.

## Question

For each checker below, which of seven attacks does it detect, without false alarms on honest runs?

## Design

**Stand-in target.** The target is a file-backed valve (`V1`, `closed` or `open`), owned by a `Target` object.
The real state is changed only by `Target.apply`. A test executor calls it, and so does the M1 mutant through the
executor. The **observer** reads the state through `Target.read`; it never calls the executor and never sees its
return value. The effect spec maps `open_valve` to `V1 = open` and `close_valve` to `V1 = closed`.

Every run uses the real `EvidenceWorkflow`, `Gate` and `LedgerSink`. M1, as in EO-1, is the inserted block that
calls the executor on REFUSE/DEFER and discards the result. It runs on a temporary copy of the repository; the
checkout is never edited.

**Checkers** (all read the ledger record; none changes it):
- **R0, the record** (the simplest rival: "the record is enough"). The rule at `tools/verify_package.py`
  `execution_only_if_allowed`, applied to the record: OK when there is no `execution_status`, or when it is
  SUCCEEDED/FAILED under ALLOW. A fifth limitation or a renamed check would change words, not this rule, so its
  detection equals R0's. It is not run as a separate arm.
- **R1, executor receipt** (EO-1 E7 candidate 3). The executor returns `{"receipt": {"requested", "target",
  "state"}}`. OK when ALLOW + SUCCEEDED has a receipt whose `requested` equals the record's and whose `state` is
  the spec's, and when REFUSE/DEFER has none.
- **R2, independent observer, bound.** New, opt-in, in `sovereign_veritas/effect_observation.py`. The
  observation is `{record_id, action_digest, before, after}`. Verdicts, in order:
  - `NO_OBSERVATION`;
  - `BINDING_MISMATCH` (`record_id` or the sha256 of the record's canonical action differs);
  - under REFUSE/DEFER: `OK` if nothing changed, else `UNAUTHORIZED_EFFECT`;
  - under ALLOW + SUCCEEDED: `UNOBSERVABLE` if `before` already equals the expected state; `OK` if the expected
    keys reached the expected values and nothing else changed; `NO_EFFECT` if nothing changed; else
    `WRONG_EFFECT`;
  - under ALLOW + FAILED/UNKNOWN: `OK` if nothing changed, else `EFFECT_DESPITE_FAILURE`.

  `UNOBSERVABLE` is neither OK nor a detection.
- **R2u, observer without binding.** R2 with the binding step removed (ablation).

**Cases.**

| ID | Run | Executor |
|---|---|---|
| C1 | ALLOW, V1 closed → open | honest, with receipt |
| C2 | REFUSE (capability not authorized) | honest |
| C3 | DEFER (`thermal_status="hot"`) | honest |
| C4 | ALLOW `open_valve` with V1 already open | honest |
| A1 | M1, REFUSE | honest |
| A2 | M1, DEFER | honest |
| A3 | ALLOW | no-op, returns no receipt |
| A4 | ALLOW | wrong action (applies `close_valve` to an open valve), honest receipt saying so |
| A5 | ALLOW | no-op that forges a receipt claiming `V1 = open` |
| A6 | the A5 run, with C1's observation attached (replay) | |
| A7 | the A5 run, with the observer wired to a view the executor controls (compromised observer; the executor writes `open` there) | |

For A4 the valve starts `open`, so the wrong action makes a change and the case is not `UNOBSERVABLE`.

## Feasibility (unmutated code, before registering)

`python -m pytest -q`: `513 passed, 49 skipped` (container, Python 3.13.18).

## Predictions

Detected = the checker returns anything other than OK (for C4, anything other than OK or UNOBSERVABLE).

| | C1–C3 false alarms | C4 | A1 | A2 | A3 | A4 | A5 | A6 | A7 |
|---|---|---|---|---|---|---|---|---|---|
| R0 | 0 | OK | miss | miss | miss | miss | miss | miss | miss |
| R1 | 0 | OK | miss | miss | **detect** | **detect** | miss | miss | miss |
| R2 | 0 | UNOBSERVABLE | **detect** | **detect** | **detect** | **detect** | **detect** | **detect** | miss |
| R2u | 0 | UNOBSERVABLE | **detect** | **detect** | **detect** | **detect** | **detect** | miss | miss |

- **P1 (the gap is still there).** R0 detects 0 of 7.
- **P2 (executor receipts don't close it).** R1 detects exactly A3 and A4. It misses M1 (A1, A2), because the
  workflow discards the receipt, and it misses the forged receipt (A5).
- **P3 (the observer does).** R2 detects A1–A6 with 0 false alarms on C1–C3, giving these verdicts: A1 and A2
  `UNAUTHORIZED_EFFECT`, A3 `NO_EFFECT`, A4 `WRONG_EFFECT`, A5 `NO_EFFECT`, A6 `BINDING_MISMATCH`.
- **P4 (binding earns its place).** R2u misses A6 and otherwise matches R2.
- **P5 (where it stops).** R2 misses A7. An observer the executor can write to is not independent, and this
  checker cannot tell.
- **P6 (an honest edge).** C4 is `UNOBSERVABLE` under R2 and R2u: an action that leaves the state where it was
  cannot be told apart from no action.
- **P7 (the controls can fail a checker).** A paranoid checker that flags everything raises 3 of 3 false alarms
  on C1–C3.
- **P8 (anti-vacuity, `--sabotage`).** The observer is replaced by a blind one that reports `after = before`.
  Then R2 misses A1, A2 and A4 and false-alarms on C1 (`NO_EFFECT`): P3 is REFUTED and the harness exits 1.
- **P9 (tests of the new module).** Property tests on seeded random states, actions and decisions, written from
  the verdict rules above, pass. Each of at least five hand-made mutants of `effect_observation.py` makes at
  least one test fail. SV's existing suite still passes, and no file it covers is changed.
- **P10 (door, unrun).** Whether and how observations enter the evidence package and `verify_package.py`. That is
  a format change and Chad's decision. Also unrun: an observer on real hardware, and observations taken while
  other writers are active.

## What the predictions mean if they hold

P1 and P2 holding means labels and executor receipts leave the EO-1 gap open where it matters (a broken guard, a
lying executor). P3 and P4 holding means a bound, independent read-back closes it **for these attacks, on this
stand-in**. P5 states the cost: the guarantee moves from "trust the executor" to "trust the observer's wiring".
That moves trust; it does not remove it.

## Pre-mortem: how this could mislead

- The observer and the executor are in one process and touch one file system. Their "independence" is a code
  boundary, not a physical one. A7 is there to show what is lost when the boundary fails; this experiment does
  not test a real one.
- A single valve with two states makes `UNOBSERVABLE` common. Real targets can have richer state.
- R1's receipt format is mine. A better-designed receipt (for example, signed by the device) is not R1.
- I wrote the checker, the attacks and the predictions, so a result that fits them is a self-test, not
  validation.

## Limits

- Self-tested: Claude (Opus 5.5, Anthropic) writes the registration, module, harness and tests.
- Container only. NOT VALIDATED on the S25.
- The effect is a file-backed stand-in. No real actuator.
- Additive and opt-in. No change to `workflow.py`, the record, the package format, `V0_LIMITATIONS` or
  `verify_package.py`.

## Provenance

Follows EO-1 (question prompted by Terry Snyder's Elyria harness; that credits a question, not an endorsement
either way). Registration by Claude (Opus 5.5, Anthropic); direction by Chad Holland, no line review before
this commit.
