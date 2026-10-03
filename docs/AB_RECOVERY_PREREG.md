# Amos Tipton's A/B Recovery Challenge: registration

Status: **Registered** (2026-10-02), before any code for it was written. The harness
(`tools/ab_recovery_challenge.py`) is built after this file is committed. Results go in
`docs/AB_RECOVERY_RESULTS.md`; this file is not edited after the run.

## Provenance

The challenge was proposed by **Amos Tipton** in a public LinkedIn discussion of the V14 challenge
track on 2026-10-02. He had not inspected this repository and offered it as a test question, not a
finding. His contribution is the question; it is not an endorsement of anything below.

- **His concern:** a recovery action can inherit the same compromised dependency it is supposed to help
  contain.
- **His distinction:** evidence sufficient to invalidate an earlier approval may not be sufficient to
  authorize a particular recovery action.
- **His scenario:** source A becomes untrustworthy while source B is unavailable, or stale. Test those as
  separate conditions. Report what is permitted, what is refused, the evidence behind each, and the
  limitations.

Chad Holland formalised the test matrix. Claude (Opus 5.5) mapped it onto this repository, wrote this
registration and the harness, and ran it.

## Baseline before anything is built

- Commit: `facadc2` (main).
- `python -m pytest -q`: 434 passed, 11 skipped.
- `python tools/corridor_challenge.py`: `VERDICT 8 of 8 as registered`.

No implementation file is modified by this experiment. If a defect is found, it is reported here
first, and any fix comes later on its own branch, with pre-fix and post-fix runs.

## Where the question lands in this repository

The only code path in which two evidence sources about the same quantity meet is
`tools/vehicle_action.py`. That path is a flight-command permission layer for a MAVLink autopilot. It
was tested in SITL and through `FakeVehicle` stand-ins, never on a vehicle.

- **A** is the autopilot's GNSS position (`lat_e7`, `lon_e7` in the snapshot).
- **B** is the independent position (`xpos_lat_e7`, `xpos_lon_e7`, plus a free-text `xpos_source`).
- **Recovery actions** are `rtl`, `land`, and, as an equivalent path, a `goto` to the fence centre.
- **The prior approval** is an earlier `goto` that the Gate allowed.

The harness drives the real `vehicle_check` and the real Gate, through `EvidenceWorkflow`, with the same
wiring as `vehicle_action.py`'s `main()`. The executor is a stand-in that records commands. Nothing
flies. One control proves the wiring matches `main()` (C0 below).

## What the code can express, read before writing anything

These statements come from reading `CONTRACT.md`, `tools/vehicle_action.py` and `sovereign_veritas/`. The
run tests them.

- **R1. B is a veto, never a support.** `vehicle_check` uses B only to fail a request when A and B
  disagree by more than `max_nav_disagreement_m`. No rule lets B authorise anything A cannot. So
  "can fresh B support recovery?" has the answer *no, by construction*: B can only take permission
  away.
- **R2. The cross-check is opt-in per request.** The limit `max_nav_disagreement_m` is a field of the
  request, set by the requester (`--max-disagreement`). Without it, B is never read.
- **R3. There is no freshness for B.** The snapshot carries no timestamp, age or sequence number for B.
  `xpos_source` is a label that nothing reads.
- **R4. There is no independence for B.** Nothing records or checks what B depends on (V14g already
  showed this in the model).
- **R5. There is no approval state.** The Gate is stateless and decides each request alone. Nothing
  stores an approval, so nothing can invalidate one. "Prior approval valid" versus "invalidated" is not
  an input the code has. Proposition A ("is the previous approval still valid?") can be asked only as
  "would the same request be allowed now?"
- **R6. `land` is exempt by design.** `vehicle_check` applies no vehicle-state rule to `land` ("land must
  never be refused for lost navigation"). It is allowed without any evidence about position. Whether
  the landing itself navigates by A is outside the code (V14f: ArduCopter's LAND holds position on GNSS
  while it has a lock).
- **R7. "Untrustworthy" has three detectable forms and one undetectable one.** The code can see:
  - disagreement with B over the limit;
  - an EKF GPS-glitch flag;
  - a lost fix.

  All three produce the same verdict, FAIL, with different text. A spoof that raises no flag and has no
  B to disagree with is invisible to it.

## Matrix

L = 25 m. The fence is the V1–V13 fence: centre 35.3632, −96.9270, radius 300 m, ceiling 120 m. The
believed position A is the fence centre in every case. Every case is run with the cross-check on (L
set) and off (no limit). Each case is run for three actions:
- `goto` 100 m north: is the prior approval still good?
- `rtl`
- `land`

| Case | A | B | Prior approval | How it is built |
|---|---|---|---|---|
| 1 | trusted | fresh, agrees | valid | B = A + 3 m |
| 2 | untrustworthy: spoofed, vehicle really 111 m north | fresh | valid | B = true position |
| 2g | untrustworthy: EKF glitch flag | fresh, agrees | valid | flag 32768 set |
| 3 | untrustworthy: spoofed, no flag | unavailable | valid | no `xpos_*` fields |
| 4 | untrustworthy: spoofed, no flag | stale | valid | B frozen at A's true position 600 s ago, before the drift; `xpos_source` and an `xpos_age_s: 600` field say so |
| 5 | as 3 | unavailable | invalidated | identical inputs to 3: there is no input for invalidation (R5) |
| 6 | as 4 | stale | invalidated | identical inputs to 4 (R5) |
| 7 | untrustworthy: spoofed, no flag | fresh-looking, derived from A | invalidated | B = A + 2 m, `xpos_source` = "derived from autopilot GNSS" |
| 8 | untrustworthy: spoofed, no flag | cached | invalidated | the whole case-1 snapshot, recorded before the spoof, is replayed as current |

**Controls:**
- **C0, wiring:** `vehicle_action.py main()` on `fake:spoofed` with `--max-disagreement 25` and
  `--xpos-sigma 0` must reach the same Gate decision as the harness on the same snapshot.
- **C1, anti-vacuity:** case 2 with the cross-check on must REFUSE the `goto`, so the harness can return
  REFUSE at all.
- **C2:** the harness must refuse to run if `vehicle_action.py`, `decision.py` or `workflow.py` differ
  from commit `facadc2`.

## Predictions

Each prediction is derived from R1–R7 and can fail.

- **AB-P1:** case 1, every action and both configurations: ALLOW.
- **AB-P2:** case 2, cross-check on:
  - `goto` and `rtl`: REFUSE, with the disagreement named;
  - `goto` to the centre: REFUSE;
  - `land`: ALLOW.

  With the cross-check off, `goto` and `rtl` are ALLOWed: the R2 bypass.
- **AB-P3:** case 2g: `goto` and `rtl` REFUSE, `land` ALLOW, in both configurations. The glitch flag
  needs no B.
- **AB-P4:** case 3, cross-check on: `goto` and `rtl` REFUSE ("no independent position"), `land` ALLOW.
  Cross-check off: all ALLOW. Unavailable B is never treated as support. With the check off it is
  simply never asked for.
- **AB-P5:** case 4, cross-check on: `goto`, `rtl` and centre-`goto` ALLOW. The stale B agrees with the
  spoofed A, and the age field and label are ignored (R3). This is failure mode C, stale treated as
  fresh. It is a specification gap, not an implementation defect: nothing in the contract asks for
  freshness.
- **AB-P6:** cases 5 and 6 give decisions identical to cases 3 and 4, byte for byte. The harness
  records them as **NOT TESTABLE UNDER CURRENT CONTRACT** for the invalidation dimension, not as passes.
- **AB-P7:** case 7, cross-check on: `goto` and `rtl` ALLOW under a spoof. Dependency inheritance is
  undetected (R4), failure mode I.
- **AB-P8:** case 8, cross-check on: ALLOW. A replayed snapshot is indistinguishable from a current one.
  The verifier binds the check to the snapshot's digest, not to its time. This is failure mode J/C,
  cached evidence leaking into a current decision.
- **AB-P9 (failure mode B):** in no case is `rtl` or `goto` allowed where it would be refused with A
  trusted and the same B. Invalidating A never becomes authorization. `land` is allowed in every case,
  including case 1, so its allowance does not depend on the invalidation.
- **AB-P10 (failure mode E):** the same snapshot and action get opposite decisions with the cross-check
  on and off in cases 2, 3 and 4. That is a fail-closed bypass chosen by the requester (R2). The
  package records which configuration was used.

## What a result will and will not establish

**It will establish** what this code decides, and why, for these constructed snapshots.

**It will not establish:**
- anything about a real vehicle, a real independent sensor or a real spoofer;
- whether ArduCopter's LAND drifts (V14i, still unrun);
- recording failures (XB-1, XB-2), which are a separate question already measured there;
- anything about other code paths. The Gate contract (`sv.gate/0`) itself has no notion of sources,
  freshness or independence. Its evidence is caller-asserted booleans in `record.metadata`. That is
  reported as the deeper limitation, not tested as a defect.
