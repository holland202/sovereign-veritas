# PR-1 registration: does an evidence-state label alone change the Gate's decision? (nothing run under this registration)

Status: registration only. Written 2026-10-04, before `tools/pr1_probe.py` exists.
Claude-assisted (Claude Opus 5.5). Chad Holland gave direction, and the question's framing
came from his message. He has not reviewed this text line by line.

## Origin
An outside comment on Moltbook by the agent `clawyer` (2026-10-04, on the post "I built a fail-closed verifier
for agent actions. Please try to break it."): the evidence states exist but the decision path does not use them,
so "an attacker stops forging the evidence and starts forging the *kind* of evidence." The comment came from an
AI agent. It is a challenge, not a review or a validation.

## Correction first (found while writing this, before any probe)
The Moltbook post and the first reply said the evidence states are "MEASURED / INFERRED / DEFAULTED / ABSENT".
That is wrong for this repository. `sovereign_veritas/evidence_states.py` defines eight states. A runtime field
may carry only **DERIVED, OPERATOR, DEFAULTED or ABSENT** (DERIVED for `thermal_status` only). **MEASURED and
INFERRED are refused on runtime fields**, because no runtime field is read directly from a sensor in this format
and claiming MEASURED would be implicit promotion. The module also states, before this probe: "The Gate does not
read these tags. It counts a DEFAULTED value exactly like a declared one (finding F1 in docs/INTEGRATION.md)."
The verifier's laundering tests (E2 in `tests/test_evidence_states.py`) already show that a dishonest relabel
fails `evidence_states`. So this probe is not blind on the main question. What it adds is a full sweep, a stated
invariance check, and controls, recorded against a pinned commit.

## Question
Holding every value in a package fixed (claim, artifact, measurement, action, capability, policy, runtime
values, thresholds, decision rules), and changing only the evidence-state tag on one runtime field, does the
Gate's decision change? And what does the verifier say about each relabelled package?

## Baseline
Commit d37779c504f8b03c9e8429eeeb07aeb5576301f9 (main). Base package: `tools/make_package.py --rounds 10
--thermal-status normal --compute-budget available --power-status stable` with a cool fake zone tree. All three
fields are tagged OPERATOR, and the decision is ALLOW. The verifier is `tools/verify_package.py`, unsigned
(authenticity and freshness are not in question here).

## Cells
For each runtime field (`thermal_status`, `compute_budget`, `power_status`), and for each of the 8 states, the
probe rewrites that one tag, regenerates the fourth known-limitation line from the tags, and reseals every
digest. This is the laundering move from E2. That gives 24 relabels. For each one it records:
- (a) the Gate decision replayed from the package's inputs (`tools/verify_package.py::replay_gate`, the
  verifier's Gate);
- (b) the verifier's failed checks;
- (c) a canonical diff against the base package outside `resource_state.evidence_states`,
  `known_limitations[3]` and `package_sha256`. Any other difference makes that cell UNDECIDED.

There is also one extra cell, all-DEFAULTED: all three fields tagged DEFAULTED. That is honest, because the
values are the defaults.

## Predictions
| ID | Prediction | conf. |
|---|---|---|
| PR0a | **Anti-vacuity, value control:** the base package with `compute_budget` changed from `available` to `exhausted` (tag OPERATOR) replays to DEFER, so the probe can see a decision change | 0.9 |
| PR0b | **Anti-vacuity, sabotage:** `--sabotage` replaces the replay with a wrapper that returns DEFER whenever any tag is DEFAULTED. The probe then reports decision changes and exits 1 | 0.95 |
| PR1 | **Structural:** `decision.py`, `runtime.py`, `capability.py`, `verification.py` and `replay_gate` never mention `evidence_states`, and `Gate.evaluate` has no parameter that could carry a tag | 0.95 |
| PR2 | Replayed decision is `ALLOW, []` in **24 of 24** relabels | 0.95 |
| PR3 | Invariance holds in 24 of 24: nothing outside the three allowed places differs, so no cell is UNDECIDED | 0.9 |
| PR4 | The verifier's `evidence_states` check passes in exactly **6 of 24** (OPERATOR and DEFAULTED on each field) and fails in 18. In every failing cell, `evidence_states` is the only failed check | 0.75 |
| PR5 | **The honest form of the attack:** all-DEFAULTED verifies with 0 failed checks and replays to ALLOW. An honestly tagged default carries the same decision authority as an operator's value (F1, reproduced) | 0.9 |

## Classification (fixed before the run)
| Result | Meaning |
|---|---|
| Same decision for every label | Criticism reproduced: provenance labels have no decision authority (gap confirmed) |
| Any label changes the decision | Unexpected dependency: find the exact line in the decision path |
| A cell changes anything besides the three allowed places | That cell is UNDECIDED, not counted |
| The probe cannot execute | UNRUN |

## What it cannot show
- Whether tags *should* have decision authority. That is a contract change. Making DEFAULTED block ALLOW would
  change the Gate's vectors and its conformance digest `44823d0f...0628`. It is Chad's decision, and it is not
  taken here.
- The DEFER rate on real traffic: **UNMEASURED**. The 59 DEFER of 4,690 vectors is a property of an adversarial
  test corpus, not of any workload.
- Whether a person can use the refusal reasons under time pressure: **UNMEASURED**.
- An unsigned rewrite that deletes the tags entirely and restores the old limitation line verifies (E5, a
  stated limit). Only a signature closes that.

## Door (unrun)
PR-2: a registered contract change in which DEFAULTED on any runtime field turns ALLOW into DEFER, with the new
vectors and digest. Not started.
