# EO-1 — Does SV's record report the effect, or the workflow's account of it? Results

**Status:** Draft, self-tested. **5 of 5 as registered, and these were predictions of a gap**: the gap is
confirmed, nothing "passed". E6 (sabotage) exits 1. E7 is the open door.
**Registration:** `docs/EO1_PREREG.md` (`53468ff`). **Harness and raw output:** `25c73b4`, re-run after deviation 4.
**Digest:** `26dd247f1359b68985094821fc85d7a3c4b1fd8237212aec0e9984ff5cdc5d94` (first pinned as `bdb2ec94…`, see deviation 4). Container only, **NOT VALIDATED on the S25**.

## What could have gone wrong, first

- **Self-tested.** Claude (Opus 5.5, Anthropic) wrote the registration, the mutant, the rival executors and the
  harness. It is not independent validation.
- **Deviations, after the first run and before pinning:**
  1. The first run's E3 ran `tests/test_workflow.py` only, not "the suite" as registered. Changed to the
     whole suite. On `test_workflow.py` alone it was `10 failed, 12 passed`.
  2. The pytest summary included its timing, so the digest changed run to run. Timing was removed from the
     summary.
  3. Failed-test ids with spaces in them were cut at the first space. Parsing was fixed.
  4. **Found by CI, after the first pin.** The CI runner reported `35 failed, 443 passed, 3 skipped` against the
     container's `35 failed, 444 passed, 2 skipped`, with the same 35 failures. The pass/skip counts depend on
     the machine, so the pinned digest (`bdb2ec94…`) could not reproduce. Only the failed set now enters the
     digest, and it is re-pinned as `26dd247f…`. The registered E3 criterion is unchanged.
  None of these changed a verdict. Every run printed `VERDICT 5 of 5 as registered`.
- **Sabotage refutes more than registered.** E6 named E2, E4 and E5. It also refutes E1, because the ALLOW
  effect stops being counted too. E3 still holds under sabotage because it does not use the counter
  (`VERDICT 1 of 5`, exit 1).
- **The stand-ins.** The effect is a marker-file line. M1 is one mutant. The two skipped tests in the mutant
  run are skipped because the repository copy has no `.git` (`not a git checkout`). They are not caused by M1.

## Raw output (`results/eo1/run.txt`; the E3 line is long and shown in full in the file)

```
EO-1 | registered run | python 3.13.16 | linux
  E2: {"DEFER": {"action_requested": "open_valve", "decision": "DEFER", "effect_requested": ["open_valve"], "effects": 1, "executed": false, "execution_status": null}, "REFUSE": {"action_requested": "open_valve", "decision": "REFUSE", "effect_requested": ["open_valve"], "effects": 1, "executed": false, "execution_status": null}}
  E4: {"decision": "DEFER", "effects": 1, "execution_check": "PASS  execution_only_if_allowed          no execution recorded", "verdict": "VERDICT  CONSISTENT  freshness=NOT_PROVEN  authenticity=NOT_PROVEN", "verify_exit": 0}
  E5: {"noop": {"action_requested": "open_valve", "decision": "ALLOW", "effect_requested": [], "effects": 0, "executed": true, "execution_status": "SUCCEEDED"}, "wrong_action": {"action_requested": "open_valve", "decision": "ALLOW", "effect_requested": ["close_valve"], "effects": 1, "executed": true, "execution_status": "SUCCEEDED"}}

  E1  HELD
  E2  HELD
  E3  HELD
  E4  HELD
  E5  HELD
VERDICT 5 of 5 as registered (E6 is --sabotage; E7 is the door)
DIGEST 26dd247f1359b68985094821fc85d7a3c4b1fd8237212aec0e9984ff5cdc5d94
```

E3 summary (from `results/eo1/results.json`): `35 failed, 444 passed, 2 skipped`, including both registered
tests. Sabotage (`results/eo1/sabotage.txt`): `VERDICT 1 of 5 as registered`, `exit 1`.

## Predictions

| | prediction | result |
|---|---|---|
| E1 | control: ALLOW 1 effect + SUCCEEDED; REFUSE/DEFER 0 effects, no status | HELD |
| E2 | M1: 1 effect on REFUSE and on DEFER; record and `WorkflowResult.executed` unchanged | HELD: the gap |
| E3 | M1 under SV's own suite: fails, including the two named tests | HELD: 35 failed |
| E4 | M1 DEFER package: `verify_package.py` exit 0, CONSISTENT, `no execution recorded`; 1 effect counted | HELD: the gap |
| E5 | no-op executor recorded SUCCEEDED; wrong-action effect recorded as the proposed action, SUCCEEDED | HELD: the gap |
| E6 | `--sabotage` refutes E2, E4, E5, exits 1 | HELD (also refutes E1, see above) |
| E7 | door: fifth limitation or an executor-issued effect receipt | not run |

## What this shows and does not show

- **Implementation fact.** SV's evidence record, `WorkflowResult.executed`, the evidence package and
  `verify_package.py` report the workflow's account of calling the executor. None of them observes an effect.
  `SUCCEEDED` means "the executor returned without raising". It does not mean "the proposed action happened".
  That is the defect found in Terry Snyder's Elyria harness, **in kind**.
- **Where SV differs from that harness.** SV's own test suite watches the executor directly and catches a guard
  mutation: 35 tests fail (10 in `test_workflow.py`), including all three tests whose names say the executor is
  never reached (`test_refused_capability_never_executes`, `test_failed_verification_never_executes`,
  `test_gate_refuse_or_defer_never_reaches_executor`). Elyria's pytest suite
  also caught its mutant. Its one-command proof did not. SV's equivalent of that proof command is the
  package-plus-verifier path, and it does not catch it (E4).
- **This is not a bug in the guard.** In the unmutated code, no effect happened outside ALLOW (E1).
- **The overclaim risk is in a name.** The check is called `execution_only_if_allowed`. What it checks is
  "the record shows execution only if allowed", and its detail line says so (`no execution recorded`).
  None of the four declared v0 limitations says what `execution_status` is evidence of.
- **Not shown.** Anything on the S25. Any real effect. Whether other guard mutants are caught.

## Candidate fixes (proposals; format changes are Chad's decision)

1. **A fifth v0 limitation** (smallest change): "execution: `execution_status` is the workflow's account of the
   executor call; no effect is observed". This changes the exact-match `V0_LIMITATIONS` and every package.
2. **Rename or re-detail the check**, for example `execution_recorded_only_if_allowed`. The renamed check
   would show up in recorded outputs that other experiments pin.
3. **An executor-issued effect receipt** that `verify_package.py` checks against the proposed action. Only this
   one closes the gap rather than labelling it, and it is a format change plus a trust question (who signs
   the receipt).

## Open

- E7 itself: which of the three, if any.
- Whether the same test applies to `tools/vehicle_action.py`, `model_action.py` and `companion_action.py`. They
  carry their own executors and records. 16 of the 35 failures under M1 were in those suites (vehicle 11, model 4, companion 1), so they observe
  something. What they observe was not checked.

## Credit and provenance

Question prompted by Terry Snyder's Elyria harness and his invitation to break it. That credits a question,
not an endorsement either way. AI participation: Claude (Opus 5.5, Anthropic) wrote the registration, harness
and this file. Human validation: Chad Holland directed the work; no line review yet. Chad is
responsible for the final artifact.
