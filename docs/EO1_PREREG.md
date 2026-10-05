# EO-1 — Does SV's record report the effect, or the workflow's account of it? Registration

**Status:** REGISTRATION. Nothing built or run at the commit that adds this file, except the feasibility
counts below.
**Date:** 2026-10-05. **Base:** `main` at `27ce753`.
**Go-ahead:** Chad Holland, 2026-10-05 06:13 CDT ("Run the test").

## Where the question came from

The same day, Claude (for Chad) challenged a third-party proof harness:
`Kamanaka5502/elyria-pre-effect-enforcement-harness` at `bf3cf0c`, sent by Terry Snyder with an invitation
to break it. Its one-command proof built the receipt's after-state from what the effect function **returned**,
not from storage. A mutant that wrote protected state on REFUSE still printed PASS, while the repository's
own pytest suite (which reads storage) caught it. EO-1 asks whether Sovereign Veritas has the same defect in
kind. Terry Snyder is credited for the harness and the invitation that led to the question. That implies no
endorsement of this work by him, and none of his by this work.

## Question

When `EvidenceWorkflow.run()` records a decision, does anything in SV observe whether an external effect
happened, or do the record, `WorkflowResult.executed`, the evidence package and `tools/verify_package.py`
report only the workflow's own account of calling the executor?

## What the code can express (read before registering)

- `workflow.py`: `executor.execute(action)` is called only under ALLOW. `execution_status` is `SUCCEEDED`
  when it returns, `FAILED`/`UNKNOWN` when it raises. `WorkflowResult.executed` is
  `execution_result is not None`, i.e. derived from the workflow's own return value.
- `tests/test_workflow.py` observes the executor directly (`executor.calls == []`) in its never-executes
  tests. `tests/test_thermal_policy.py` T2 reads only the record's `execution_status`.
- `tools/make_package.py` runs the real workflow with `NoSideEffect`, whose `execute` returns a dict and
  does nothing. `tools/verify_package.py`'s `execution_only_if_allowed` reads the record's
  `execution_status` and prints `no execution recorded` when it is absent.
- The four v0 limitation statements cover freshness, authenticity, verifier identity and resource state.
  None states what `execution_status` is evidence of.

## Design

The external effect is counted **outside SV**, by the harness, as lines appended to a marker file by a
counting executor. Every arm uses the real `EvidenceWorkflow`, `Gate`, `LedgerSink` and, for packages, the
real `make_package.py` and `verify_package.py` as subprocesses. Mutated code runs on a temporary copy of the
repository. The checkout is never edited.

- **Mutant M1** (one inserted block, in `workflow.py` immediately before `if decision.decision == "ALLOW":`):
  ```python
          if decision.decision != "ALLOW" and action is not None:
              self.executor.execute(action)  # EO-1 MUTANT
  ```
  The effect happens, and the result is discarded, so nothing in the workflow's account changes.
- **Cases at workflow level:** ALLOW (authorized capability, PASS verifier, normal runtime); REFUSE
  (capability not authorized); DEFER (runtime `thermal_status="hot"`). Counting executor.
- **Package arm:** `make_package.py --rounds 10 --thermal-status hot` (a DEFER package) with
  `NoSideEffect` replaced, in-process, by the counting executor; then `verify_package.py` on the package.
- **Rival executors** (unmutated workflow, ALLOW): a no-op that returns normally and records no effect; and a
  wrong-action executor that writes the effect `requested="close_valve"` for a proposal `requested="open_valve"`.
- **Simplest rival:** "the record is enough". Arms M1 and the rival executors test it directly.

## Feasibility (run before registering, unmutated code)

```
481 passed in 45.64s
decision DEFER ['runtime_not_healthy']
PASS  execution_only_if_allowed          no execution recorded
VERDICT  CONSISTENT  freshness=NOT_PROVEN  authenticity=NOT_PROVEN
verify exit 0
```

## Predictions

- **E1 (control, unmutated).** ALLOW: 1 effect, record `ALLOW` / `SUCCEEDED`, `executed` true. REFUSE and
  DEFER: 0 effects, record decision as named, no `execution_status`, `executed` false.
- **E2 (M1, workflow level).** REFUSE and DEFER: 1 effect each, while the record still says the decision
  with no `execution_status`, and `WorkflowResult.executed` is false. The record and the result do not see
  the effect.
- **E3 (M1 under SV's own suite).** The suite fails. At least the two tests that assert
  `executor.calls == []` for REFUSE (`test_refused_capability_never_executes`,
  `test_failed_verification_never_executes`) fail. The exact count is recorded.
- **E4 (M1, package path).** The DEFER package is produced, `verify_package.py` exits 0 with
  `VERDICT  CONSISTENT` and `PASS  execution_only_if_allowed          no execution recorded`, and the harness
  counts 1 effect.
- **E5 (rival executors, unmutated).** No-op: 0 effects, record `SUCCEEDED`. Wrong action: 1 effect whose
  requested value is `close_valve`, while the record's `action.requested` is `open_valve` and
  `execution_status` is `SUCCEEDED`.
- **E6 (anti-vacuity, `--sabotage`).** The effect counter is replaced by one that always reads 0. E2, E4 and
  E5 must then be REFUTED and the harness exit 1. This shows the harness can tell effect from no effect.
- **E7 (door, unrun).** Candidate remedies, both format changes and so Chad's decision: (a) a fifth v0
  limitation stating that `execution_status` is the workflow's account of the executor call, not an observed
  effect; (b) an executor-issued effect receipt that `verify_package.py` checks against the proposed action.

## What the predictions mean if they hold

E2 and E4 holding means SV's record and package verifier have Terry's harness defect **in kind**: they report
what the workflow did, not what happened. E3 holding means SV's unit tests, unlike that harness's one-command
proof, would catch a guard mutation. E5 holding means `SUCCEEDED` is the executor's say-so. All of these are
predictions of a gap, so "n of n as registered" is a confirmed gap, not a pass.

## Limits

- Self-tested: Claude (Opus 5.5, Anthropic) writes the registration, mutant and harness.
- Container only. NOT VALIDATED on the S25.
- The effect is a marker-file line, a stand-in for an external effect.
- M1 is one mutant. It tests whether the record can see a guard failure, not every way a guard can fail.

## Provenance

Question prompted by Terry Snyder's harness and invitation (above). Registration by Claude (Opus 5.5,
Anthropic); direction by Chad Holland, no line review before this commit.
