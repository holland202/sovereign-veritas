# SV-FIX-001: fixes for SV-ATTACK-001 Q1 (execution boundary) and Q3 (offline verifier)

**Status: REGISTERED, UNRUN, NO CODE.** This file was committed alone, before any change to
`sovereign_veritas/workflow.py` or `tools/verify_package.py`. Registered 2026-10-09 by Claude (Opus 5.5) at
Chad Holland's direct request. Chad has not reviewed it line by line. Writing the fix, running it, and merging
it each need his authorization.

- **Builds on:** [`SV_ATTACK_001_RESULTS.md`](SV_ATTACK_001_RESULTS.md) (run1: Q1 FAIL, Q3 FAIL, Q2 PASS).
- **Repository state:** maintenance-only. These are security fixes, which the maintenance notice permits.
- **Two fixes, two verdicts.** Each finding gets its own fix and its own verdict; one passing never counts
  for the other (SV-ATTACK-001 Amendment 1, M3).

## F1: bind what executes to what was decided (Q1)

**Change, in `workflow.py` only:** on ALLOW, the executor receives a **new** `ActionProposal` built from the
decision record's frozen `action` (`capability`, `requested` and a deep, thawed copy of `parameters`). It no
longer receives the caller's original object. No change to `decision.py`, `contracts.py`, `evidence.py`, the
ledger format or the package format.

**Why this design:**
- By construction, the executor can only receive the values the Gate decided on, and the ledger records
  exactly those values.
- A change the caller makes after the decision has no effect on what runs.
- It does not refuse when the caller's dict changes. Detecting and refusing would also be defensible. It is
  not chosen because it adds a new failure path and a new record field. The owner may prefer it; if so, this
  registration is amended before any code.

**Known behaviour change:** the executor receives a copy, not the caller's object. Two consequences:
- An executor that relied on object identity, or on extra non-JSON attributes of the caller's object, would
  behave differently. `EvidenceRecord` already rejects non-JSON action contents, so the second should not
  exist.
- Tuples become lists after the thaw (`evidence._thaw`), which is JSON-equivalent.

## F2: compare sent commands with the authorization (Q3)

**Change, in `tools/verify_package.py` `vehicle_command_check` only.** When the record shows execution under
ALLOW, the parameter-bearing commands in `commands_sent` must carry exactly the authorized parameters. The
rules depend on `measurement.backend`:

- **`fake`:** `commands_sent` must equal exactly `[f"{requested} {canonical_json(parameters)}"]`. That is the
  format `FakeVehicle.run` writes.
- **`mavlink`:** every parameter-bearing command must match the authorization:
  - `NAV_TAKEOFF <alt_m>` equals the authorized `alt_m`;
  - `SET_POSITION_TARGET_GLOBAL_INT <lat_e7> <lon_e7> <alt_m>` equals the authorized values;
  - a `goto` must contain exactly one such position command, and a `takeoff` exactly one `NAV_TAKEOFF`;
  - `ARM` and `SET_MODE <name>` carry no movement parameters and are allowed;
  - any other command name fails (closed list).
- **Any other backend value:** the check fails.

The comparison uses the record's `action.parameters`, which is already checked against the request. It
never uses anything the package says about itself as a reference.

## Verification plan (all registered now)

The run uses SV-ATTACK-001's probe **unchanged except its `TARGETS` table**. The probe pins the hashes of
`workflow.py` and `verify_package.py`, and after the fix those hashes change. The new hashes are committed
in a probe-only commit before the run. The probe's cases, hook, controls and verdict rules stay
byte-identical; the diff of that commit must touch only the two hash lines.

| ID | Check | Predicted outcome |
|---|---|---|
| R1 | Probe rerun on the fixed code (new label) | **Q1 PASS**: A1 and B1 execute the authorized parameters (`sandbox/a.txt`/`append`; `lat_e7 353640993`), no divergence. C1–C4 hold. C2 still shows the hook firing once, before execution |
| R2 | Same rerun | **Q2 PASS** (unchanged) |
| R3 | Same rerun | B1's package now verifies (exit 0), because no divergence exists to catch. **This does not count for Q3**: it is not evidence that F2 works |
| R4 | **The real Q3 test:** fixed `verify_package.py` on run1's committed `results/sv_attack_001/run1/packages/B1.json`, made by the unfixed code, whose `commands_sent` diverge | **exit 1**, with `vehicle_check_bound` failing on the command content. Q3 PASS if so, FAIL if exit 0 |
| R5 | Fixed `verify_package.py` on run1's `B0.json` (honest package) | exit 0 (no false alarm) |
| R6 | Regression: fixed `verify_package.py` on every committed package with `vehicle_command_check` outside `results/sv_attack_001/` (counted at registration). That is 24 files: 3 in `evidence/attacks/issue-005/`, 10 in `runs/vehicle_sitl/`, 4 in `runs/vehicle_sitl_v11/`, 6 in `runs/vehicle_sitl_v12/` and 1 in `runs/vehicle_sitl_v13/` | Every exit code is the same as with the unfixed verifier. Both sets are recorded in the same run. Any change is reported per file, and an unexplained change is a FAIL of F2 |
| R7 | Full test suite: CI on the fix commit | All jobs green. Locally, the same failure count as unmodified `main` in the same environment, with failing test names compared one by one this time (not counts only) |
| R8 | Anti-vacuity for F1 | The run1 evidence (unfixed code, same probe) already shows the attack succeeding. Additionally, a mutant `workflow.py` that passes the caller's object again, run through the rerun probe with that mutant's hash, must give **Q1 FAIL**. The mutant lives only in a temporary copy and is never committed to `sovereign_veritas/` |
| R9 | Anti-vacuity for F2 | A mutant `verify_package.py` with the new content comparison removed must give exit 0 on R4's package |

**Verdicts:**
- **F1 PASS** if R1 shows Q1 PASS with C1–C4 holding, R7 is green, and R8 gives Q1 FAIL. **F1 FAIL** if R1
  shows divergence or R7 regresses. INCONCLUSIVE otherwise.
- **F2 PASS** if R4 exits 1, R5 exits 0, R6 shows no unexplained change, and R9 exits 0. **F2 FAIL** if R4
  exits 0, R5 exits non-zero, or R6 shows an unexplained change. INCONCLUSIVE otherwise.

## Run rules

1. Code is written only after Chad authorizes it, in a commit separate from this registration.
2. The probe hash-only commit comes next, and then the run. The run happens once unless Chad states
   otherwise (the M1 rule from SV-ATTACK-001 carries over).
3. Evidence goes in `results/sv_fix_001/`, committed unedited, with `SHA256SUMS`. Logs are force-added past
   the `*.log` ignore rule.
4. SV-ATTACK-001's registration, amendment, probe and run1 evidence are never edited. STATUS.md's open
   findings are moved to fixed only if the matching verdict is PASS, and the wording keeps the link to the
   run1 failure.
5. No merge without Chad.

## What this cannot establish

- **Only the tested path.** F1 closes the specific window SV-ATTACK-001 measured, the shared mutable
  `parameters` between decision and execution in `EvidenceWorkflow.run()`. It does not address:
  - an executor that reads its real inputs from elsewhere (a file, a network);
  - a malicious executor;
  - a compromised process;
  - the race and effect-without-record cases left open by XB-1 and XB-2.
- **Only the tested backends.** F2 covers `vehicle_command_check` with the `fake` and `mavlink` backends.
  Other measurement kinds keep their own binding checks, unchanged.
- **Not authenticity.** Packages remain unsigned unless signed. A consistent forgery of a whole package still
  verifies (a known limit).
- **Not independent.** Claude wrote the attack, the fixes, the probe and this registration.
- **NOT VALIDATED. NOT PRODUCTION-READY.**

## Credit

Motivated by SV-ATTACK-001. That test was motivated by John Rodriguez's external-review concern about gate
manipulation. **He did not design the attack or these fixes, and has not reviewed them.** ChatGPT suggested
the substitution idea and audited the run.
