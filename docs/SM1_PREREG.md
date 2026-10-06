# SM-1 registration: can invalid movement bind at the seam, and can a refused movement bind another way?

Status: **Registered** (2026-10-06), committed alone, before the probe exists. Nothing is built or run.
Results, when they exist, go in `docs/SM1_RESULTS.md` and never edit this file. Errors found here later are recorded there.

## Origin and credit

Terry Snyder (private LinkedIn message, 2026-10-06, paraphrased, not quoted) told this project to keep an experiment in its
own category: this code cannot test whether anyone's *starting condition* for movement is correct. It can test whether
this layer holds one bounded case at the point where a movement would become a consequence. He framed the question as:
can invalid movement bind although authority, reservation, Gate decision and evidence record all look valid? He also
asked for a frozen case, a registered claim before any run, a refusal that leaves a receipt, a replay that does not rewrite
the first receipt, and a test for whether the refused movement can bind another way. Credit is for that framing, as a
question. He has not reviewed or endorsed this registration or its results, and nothing here reproduces or tests his
own model. The design, predictions and code are this project's.

## The claim under test (one sentence)

> With the carrier frozen, the independent-position cross-check (`max_nav_disagreement_m`, V12) refuses a movement whose
> recorded state says in-bounds and whose independently observed state is far outside; the refusal leaves a receipt that
> a replay does not change; but the refusal is a proxy for standing, not standing, and some materially equivalent routes
> still bind.

This is a claim about the current code. It is not a claim about vehicles, sensors or anyone's floor.

## Frozen carrier

- Code: `tools/vehicle_action.py` at `709da9e`: `vehicle_check`, `FakeVehicle`, `EvidenceWorkflow`, `build_package`. Imported,
  not copied. The harness may construct snapshots and requests; it may not change the check.
- Backend: `fake` only. **A stand-in, not a vehicle.** The independent position is a stand-in, not a sensor. No SITL here.
- Fixed in every case: capability `vehicle_command` authorized, policy `allow_only: [takeoff, goto, land, rtl]`, limits
  `min_fix_type 3`, `min_sats 6`, `min_battery_pct 30`, `max_nav_disagreement_m 25.0` (unless the case says otherwise).
- Corridor (the declared geofence): centre `(35.3632, -96.9270)`, radius **100 m**, ceiling 120 m.
- The attempted movement: `goto` to a point 20 m north of the corridor centre at 20 m altitude (inside the corridor by
  recorded state).
- The standing condition, declared for this case: *the vehicle is within the actual permitted corridor when the movement
  would acquire consequence.* The harness can only measure it against the stand-in's "actual" position (`xpos`); it does
  not establish it. The check cannot read standing; it reads two recorded numbers and their gap.

## Cases

| Case | Recorded position | Independent position | Request | Purpose |
|---|---|---|---|---|
| A0 | centre | centre | as frozen | anti-vacuity: both inside, must ALLOW |
| A1 | 150 m north (outside, both agree) | 150 m north | as frozen | anti-vacuity: both outside, must REFUSE |
| D1 | centre (in-bounds) | 111 m north of centre (outside, gap 111 m) | as frozen, limit 25 m | the divergence |
| D0 | centre | 111 m north | as frozen, **no** `max_nav_disagreement_m` | the default layer, no cross-check |
| E1 | 95 m north of centre (in-bounds) | 105 m north of centre (outside, gap 10 m) | as frozen, limit 25 m | divergence below the limit |
| P1 | D1, then the same request again, same condition | | | replay |
| P2 | D1, then the independent position moved to centre | | | changed condition |
| R1 | D1 | | same request with the limit field omitted | route: drop the cross-check |
| R2 | D1 | | same request with the fence radius widened to 300 m | route: the requester writes the fence |
| R3 | D1 | | `rtl` instead of `goto` | route: another action |
| R4 | D1 | | the executor called directly, not through the Gate | route: bypass |

"Receipt" = the sealed evidence package (`build_package`) the run writes, identified by its sha256.

## Predictions (numbered before any run)

- **S1 (D0).** With no cross-check, the movement is ALLOWed and the vehicle state changes: invalid movement binds, every
  check passes, the package verifies. Expected to hold, on the strength of V11 in simulation.
- **S2 (D1).** With the 25 m limit, the movement is REFUSED, the check names the disagreement, no command is sent, the
  vehicle state is unchanged, and a package is written that `tools/verify_package.py` accepts.
- **S3 (P1).** Replaying D1 gives the same decision and the same refusal reason; the sha256 of the first receipt is
  unchanged afterwards and the replay is a separate file.
- **S4 (P2).** With the independent position moved to the centre, the same request is ALLOWed under a new receipt; the
  first receipt's sha256 is unchanged.
- **S5 (E1).** The movement is **ALLOWed** although the independent position is outside the corridor: the 25 m gap limit
  is a proxy and does not enforce the corridor. Registered as a prediction of failure of the proxy. If E1 is refused, S5 is
  refuted and recorded as such.
- **S6 (routes).** R1 binds, R2 binds, R3 is REFUSED, R4 binds. R1 and R2 bind because the request itself carries the
  limit and the fence; R4 binds because the Gate is a permission layer only where the executor is reachable only through
  it. R3 is expected refused on the strength of V12d. Each route that binds is a finding, not a defect of the probe.
- **S7 (anti-vacuity).** A0 is ALLOWed and A1 is REFUSED, so the instrument can return both.

"All predictions held" would not mean "the layer is safe": S1, S5 and part of S6 are predictions that it is not.

## Sabotage and control

- `--sabotage`: the cross-check rule is disabled (the check ignores `max_nav_disagreement_m`). S2 must be REFUTED, and the
  exit is 1 **only because S2 is refuted**, not because any prediction fails.
- `--sabotage-noop`: the same patching path with the check left alone. S2 must hold, exit 0. It is a control; its digest
  must equal the registered run's.
- The harness pins `RECORDED = (held tuple, digest)` in a separate commit after the first run. The digest excludes
  timestamps and tokens and contains no line numbers.

## Limits

- Simulation stand-ins only: the vehicle and the independent position are both canned. NOT VALIDATED on the S25.
- If S2 holds, the evidence is that this layer, on this stand-in, refuses a recorded/observed divergence above its limit and
  keeps the first receipt intact. It does not show the vehicle was in the corridor, and it says nothing about the origin of
  movement, about anyone's floor, or about real sensors.
- The comparison is only as independent as its second source. A second source that shares the first's fault shows no gap.
- R4 is outside the Gate's contract and is included so the boundary is stated, not discovered.

## Left unrun (the door)

- **U1.** Post-ALLOW window: the spoof begins after the check and before the consequence. V14 modelled it (117.5 m
  unbounded; about 31 m with per-reading re-check); it is not run against this carrier.
- **U2.** The same cases against ArduCopter SITL with a stand-in independent position (V12's setup).
- **U3.** A real second sensor.

## Provenance

AI participation: Claude (Sonnet 5.5, Anthropic) drafted this registration. Human validation: Chad Holland gave direction on
2026-10-06 after reading the proposed outline; he has not reviewed this text line by line. Human responsibility for the final
artifact is Chad Holland's. This is a registration, not a result, and Claude's own design is not independent validation.
