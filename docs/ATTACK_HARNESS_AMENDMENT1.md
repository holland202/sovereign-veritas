# Attack harness: Amendment 1 (2026-10-10). A5 becomes a fully consistent rewrite

**Status: REGISTERED before the code change.** This amends [`ATTACK_HARNESS.md`](ATTACK_HARNESS.md). That
file, its classes and its predictions P0–P15 are **not edited**. Registered by Claude (Opus 5.5).

**Owner decision.** On 2026-10-10 at 05:11 CDT, Chad Holland chose option A, directly to Claude, from the
three options on sovereign-veritas PR #71 (note `sv/claude/071-1`).

## Why (a dated note on what changed underneath this experiment)

SV-FIX-001 F2 (commit `d63d3fd`, [`SV_FIX_001_PREREG.md`](SV_FIX_001_PREREG.md)) made `verify_package.py`
compare `commands_sent` with the authorized parameters.

A5 as originally written:
- rewrites the request's `goto` 100 m east;
- recomputes every digest;
- **but leaves `commands_sent` holding the original position command**.

At `d63d3fd`, D0 now rejects all four A5 packages on that mismatch, so registered P5 ("D0 accepts at least
one") no longer holds. Claude-run, `python3 -I tools/attack_harness.py`, pasted:
```
main 438e6d5:   A5   4   4/4   0/4   0/4   -                     P5  HELD
fix  d63d3fd:   A5   4   0/4   0/4   0/4   vehicle_check_bound   P5  FAILED
```
That outcome is recorded here as a fact about the old, partial A5: **F2 catches a rewrite that forgets to
rewrite the commands.** It is not evidence that unsigned packages resist rewriting. A rewrite that is fully
consistent should still pass D0, which is what P5 was registered to show.

## Change (one class, one code block)

In `tools/attack_harness.py`, the A5 block also rewrites `measurement.commands_sent` consistently:
- every `SET_POSITION_TARGET_GLOBAL_INT <lat> <lon> <alt>` line is replaced by the same line with the
  rewritten request's `lat_e7`, `lon_e7` and `alt_m`, formatted exactly as `MavlinkVehicle.run` formats it;
- this happens before `recompute_all`, so the package is resealed over the new commands;
- all 21 corpus packages are MAVLink SITL, and the backend is not changed.

No other class, defender, corpus file or prediction changes.

## Predictions, made before the change

- **P5 holds again**, with A5's row reading `4 4/4 0/4 0/4 -`. D0 accepts the consistent rewrites, while D1
  (signature) and D2 (signature and witness) refuse all of them.
- **Every other row and P-line of the harness output is byte-identical** to the output at `d63d3fd`, which is
  itself identical to `main` apart from the A5 row and P5.
- **`tests/test_attack_harness.py` passes.** CI's `red-team` job (`verifier_mutants.py`, whose null mutant
  runs the test files) passes.

If any of these fails, the result is kept and reported, and the code is not adjusted to fit.

## What this does not establish

- Anything about signed packages beyond what D1 and D2 already measure.
- That F2 stops a determined forger. It does not: unsigned packages can be rewritten consistently, which is
  exactly what P5 records.
