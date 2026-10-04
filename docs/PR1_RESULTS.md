# PR-1 results: an evidence-state label alone never changed the Gate's decision (7 of 7 as registered)

Registration: `docs/PR1_PREREG.md`, commit 8d16f45 (pushed 2026-10-04 05:24 -0500), before `tools/pr1_probe.py`
existed. The probe was run once in normal mode and once with `--sabotage`, on commit 8d16f45, which is d37779c plus
the registration. Linux container, Python 3. **NOT VALIDATED on the S25.**
Claude-assisted (Claude Opus 5.5). Chad Holland directed it. He has not reviewed this text line by line.

## What failed or was wrong (first)
1. **Our public description was wrong.** The Moltbook post and the first reply to `clawyer` said the evidence
   states are "MEASURED / INFERRED / DEFAULTED / ABSENT". Runtime fields carry DERIVED, OPERATOR, DEFAULTED or
   ABSENT. MEASURED and INFERRED are *refused*, and the verifier fails them (table below). A correction is owed
   publicly.
2. **The criticism is confirmed.** No label changes a decision. In particular an honest DEFAULTED tag on all three
   runtime fields still gets ALLOW and verifies with zero failed checks. The tags record where a value came from;
   they carry no decision authority. This is finding F1 in `docs/INTEGRATION.md`, reproduced on purpose.
3. **The probe is not blind**, as the registration said: the module's own docstring states that the Gate does not
   read the tags. The probe adds a full sweep, an invariance check and two controls. It does not add surprise.
4. **PR1 is a weak check.** It is a text search for "evidence_state" in four files plus `replay_gate`, and a scan
   of `Gate.evaluate`'s parameter names. It would miss an indirect dependency. PR2, the behaviour, is the real
   evidence.

## Outcome
| ID | Prediction | Result |
|---|---|---|
| PR0a | value control (compute_budget exhausted) changes the decision | HELD: DEFER, `runtime_not_healthy` |
| PR0b | `--sabotage` (DEFER on any DEFAULTED tag) is detected, exit 1 | HELD: 4 of 6, exit 1 (PR2 and PR5 broke as they should) |
| PR1 | decision code never mentions evidence states; no tag parameter | HELD (weak check, see above) |
| PR2 | replay unchanged in 24 of 24 relabels | HELD: 24 of 24 `ALLOW []` |
| PR3 | no cell changes anything else | HELD: 0 UNDECIDED |
| PR4 | `evidence_states` passes 6 of 24, the 18 failures fail on it alone | HELD: 6 of 24, 18 of 18 |
| PR5 | all-DEFAULTED verifies clean and ALLOWs | HELD: ALLOW, no failed checks |

Classification (fixed before the run): **same decision for every label, so the criticism is reproduced and the gap
confirmed.**

## What it means, and what it does not
- A *dishonest* relabel (MEASURED, INFERRED, DERIVED without a measurement, ABSENT on a usable value, the
  unwired states) is caught, by the **verifier**, not the Gate: the package fails `evidence_states`. A consumer
  that requires CONSISTENT rejects it. That only works if the consumer runs the verifier.
- An *honest* DEFAULTED is not caught, because nothing is wrong with it. The Gate counts a default exactly like a
  value someone supplied. That is the "forge the kind of evidence" gap in its real form: an attacker doesn't
  need to forge anything if the system already treats "nobody said" as "healthy".
- Whether DEFAULTED *should* block ALLOW is a contract change (new vectors, new digest). Not taken. Chad's decision.
- Still **UNMEASURED**: the DEFER rate on real traffic, and whether a person can use the refusal reasons under time
  pressure.

## Door (unrun)
PR-2: a registered contract change in which DEFAULTED on any runtime field turns ALLOW into DEFER, with new vectors
and a new conformance digest.

## Output, normal run (verbatim)
```
base tags {'compute_budget': 'OPERATOR', 'power_status': 'OPERATOR', 'thermal_status': 'OPERATOR'} | replay ('ALLOW', []) | recorded ALLOW | failed checks []
PR0a value control: compute_budget exhausted -> ('DEFER', ['runtime_not_healthy'])
PR1 files mentioning evidence states: none | Gate.evaluate params: ['self', 'evidence', 'capability', 'runtime', 'policy', 'registry']

field            state        replay              invariant  failed checks
thermal_status   MEASURED     ALLOW  []           True       ['evidence_states']
thermal_status   OPERATOR     ALLOW  []           True       []
thermal_status   DERIVED      ALLOW  []           True       ['evidence_states']
thermal_status   INFERRED     ALLOW  []           True       ['evidence_states']
thermal_status   ABSENT       ALLOW  []           True       ['evidence_states']
thermal_status   DEFAULTED    ALLOW  []           True       []
thermal_status   NEVER_WIRED  ALLOW  []           True       ['evidence_states']
thermal_status   UNVERIFIED   ALLOW  []           True       ['evidence_states']
compute_budget   MEASURED     ALLOW  []           True       ['evidence_states']
compute_budget   OPERATOR     ALLOW  []           True       []
compute_budget   DERIVED      ALLOW  []           True       ['evidence_states']
compute_budget   INFERRED     ALLOW  []           True       ['evidence_states']
compute_budget   ABSENT       ALLOW  []           True       ['evidence_states']
compute_budget   DEFAULTED    ALLOW  []           True       []
compute_budget   NEVER_WIRED  ALLOW  []           True       ['evidence_states']
compute_budget   UNVERIFIED   ALLOW  []           True       ['evidence_states']
power_status     MEASURED     ALLOW  []           True       ['evidence_states']
power_status     OPERATOR     ALLOW  []           True       []
power_status     DERIVED      ALLOW  []           True       ['evidence_states']
power_status     INFERRED     ALLOW  []           True       ['evidence_states']
power_status     ABSENT       ALLOW  []           True       ['evidence_states']
power_status     DEFAULTED    ALLOW  []           True       []
power_status     NEVER_WIRED  ALLOW  []           True       ['evidence_states']
power_status     UNVERIFIED   ALLOW  []           True       ['evidence_states']

replay unchanged 24 of 24 | UNDECIDED 0 | evidence_states pass 6 of 24 | failing on evidence_states alone 18 of 18
PR5 all-DEFAULTED: replay ('ALLOW', []) | failed checks none

mode: normal
  PR0a  HELD
  PR1   HELD
  PR2   HELD
  PR3   HELD
  PR4   HELD
  PR5   HELD
VERDICT  6 of 6 as registered (PR0b: run --sabotage, expect exit 1)
exit 0
```

## Output, `--sabotage` (verbatim)
```
base tags {'compute_budget': 'OPERATOR', 'power_status': 'OPERATOR', 'thermal_status': 'OPERATOR'} | replay ('ALLOW', []) | recorded ALLOW | failed checks []
PR0a value control: compute_budget exhausted -> ('DEFER', ['runtime_not_healthy'])
PR1 files mentioning evidence states: none | Gate.evaluate params: ['self', 'evidence', 'capability', 'runtime', 'policy', 'registry']

field            state        replay              invariant  failed checks
thermal_status   MEASURED     ALLOW  []           True       ['evidence_states']
thermal_status   OPERATOR     ALLOW  []           True       []
thermal_status   DERIVED      ALLOW  []           True       ['evidence_states']
thermal_status   INFERRED     ALLOW  []           True       ['evidence_states']
thermal_status   ABSENT       ALLOW  []           True       ['evidence_states']
thermal_status   DEFAULTED    DEFER  ['sabotage:defaulted_tag'] True       []
thermal_status   NEVER_WIRED  ALLOW  []           True       ['evidence_states']
thermal_status   UNVERIFIED   ALLOW  []           True       ['evidence_states']
compute_budget   MEASURED     ALLOW  []           True       ['evidence_states']
compute_budget   OPERATOR     ALLOW  []           True       []
compute_budget   DERIVED      ALLOW  []           True       ['evidence_states']
compute_budget   INFERRED     ALLOW  []           True       ['evidence_states']
compute_budget   ABSENT       ALLOW  []           True       ['evidence_states']
compute_budget   DEFAULTED    DEFER  ['sabotage:defaulted_tag'] True       []
compute_budget   NEVER_WIRED  ALLOW  []           True       ['evidence_states']
compute_budget   UNVERIFIED   ALLOW  []           True       ['evidence_states']
power_status     MEASURED     ALLOW  []           True       ['evidence_states']
power_status     OPERATOR     ALLOW  []           True       []
power_status     DERIVED      ALLOW  []           True       ['evidence_states']
power_status     INFERRED     ALLOW  []           True       ['evidence_states']
power_status     ABSENT       ALLOW  []           True       ['evidence_states']
power_status     DEFAULTED    DEFER  ['sabotage:defaulted_tag'] True       []
power_status     NEVER_WIRED  ALLOW  []           True       ['evidence_states']
power_status     UNVERIFIED   ALLOW  []           True       ['evidence_states']

replay unchanged 21 of 24 | UNDECIDED 0 | evidence_states pass 6 of 24 | failing on evidence_states alone 18 of 18
PR5 all-DEFAULTED: replay ('DEFER', ['sabotage:defaulted_tag']) | failed checks none

mode: SABOTAGE
  PR0a  HELD
  PR1   HELD
  PR2   NOT HELD
  PR3   HELD
  PR4   HELD
  PR5   NOT HELD
VERDICT  4 of 6 as registered (PR0b: run --sabotage, expect exit 1)
exit 1
```
