# EP-1 registration: do the states the Gate collapses need different dispositions? (nothing run)

Status: registration only. Written 2026-10-03 before `tools/ep1_probe.py` exists. Claude-assisted (Claude Opus 5.5);
Chad gave direction only. Three narrow questions as ChatGPT proposed (EP-1A/B/C), each with a negative control.
Builds on EP-0 (PR #29). Nothing in SV is changed.

**Exploration disclosed (C-EXPLORE):** read `evidence_states.py`, `runtime.py`, `Gate.evaluate`. EP-0 already ran.

## What is empirical and what is by construction
- **Empirical (real Gate):** the (decision, reason) the Gate returns for each condition (F1, F2).
- **By construction:** whether a distinction *matters* depends on a declared world model (below). F3-F7 follow from
  that model plus F1. They make the consequence explicit and checkable; they do not discover it.

## Conditions
Evidence path (`required_evidence=("sensor",)`, verifier PASS): **M** missing (no key), **I** `"INACCESSIBLE"`,
**U** `"UNSEARCHED"`, **O** `"OUT_OF_SCOPE"`; **S** verifier `INSUFFICIENT_EVIDENCE` with `sensor: True` (control).
Runtime path: **RM** `thermal_status=None` (missing runtime value); **RD** default runtime (DEFAULTED).

## Declared world model (assumption)
- I: transient; one retry makes the sensor readable (`True`).
- U: one *search* makes it available; a plain retry does not search.
- M, O: no retry or search makes evidence available.
- S: transient like I.

## Caller policies (only the Gate's output is visible to the caller)
- **P_gen:** one policy per (decision, reason): on DEFER, retry up to R times. Never searches (no output says "search").
- **P_dist:** knows the condition: I and S retry; U searches once then retries; M and O stop.
Budget R = 3; negative control N1 uses R = 0.

## Predictions
| ID | Prediction |
|---|---|
| F1 | M, I, U, O give one identical (DEFER, missing_required_evidence:sensor). |
| F2 | RM gives REFUSE (runtime_state_unavailable) while M gives DEFER: a missing *runtime* value and a missing *evidence* item get different dispositions. RD gives ALLOW. |
| F3 (EP-1A inaccessible) | P_gen and P_dist both reach ALLOW after 1 retry: **no different disposition required.** |
| F4 (EP-1B unsearched) | P_gen ends not-ALLOW after 3 wasted retries; P_dist reaches ALLOW: **the distinction changes the outcome.** |
| F5 (EP-1C out of scope) | both end not-ALLOW; P_gen spends 3 retries, P_dist 0: **cost changes, outcome does not.** M behaves the same as O. |
| F6 (negative control N1, R = 0) | every condition has identical outcome and cost under both policies. |
| F7 (negative control N2) | I and S: same outcome and cost under both policies (two different reasons that legitimately share DEFER-and-retry). |

## Sabotage (M3)
`--sabotage` gives P_gen the condition labels (it becomes P_dist); F4 and F5 must fail and the script must exit 1.

## What it cannot show
Whether the world model is right for any real sensor or search. F3-F7 are only as good as it.

## Door (M15)
If F4 holds, the smallest change that would matter is a distinct DEFER reason for "not searched" (a caller can act on
it). That is a gate-contract change (CONTRACT.md, vectors, Go port) and is not registered here.
