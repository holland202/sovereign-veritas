# SV-ATTACK-001: Amendment 1 (2026-10-09, before any probe code exists)

**Status: REGISTERED, UNRUN.** This amends [`SV_ATTACK_001_PREREG.md`](SV_ATTACK_001_PREREG.md) (commit `6a524e5`,
sha256 `d436a83a88762dbd4bfab35f2941fed0de32bbba80e7c00fa4e0fd05cddf4ed4`). That file is **not edited**.
Where they differ, this amendment governs.

- **Why:** ChatGPT's review of the registration (veritas-origin PR #25, note `vo/chatgpt/047`).
- **When:** written before `tools/sv_attack_001_probe.py` exists. No case has been run, so no result could
  have influenced these changes.
- **Who:** Claude (Opus 5.5), at Chad Holland's direction; not reviewed line by line by Chad.
- **No change to:** cases, predictions P1–P9, controls C1–C4, or the target hashes.

## M1. Number of executions needs the owner's explicit word

The registration says "one registered run … plus one immediate repeat". The project's owner boundary for
attack runs is one authorized execution. Replacement rule:
- The run authorization from Chad must state the number of executions.
- If it says one, or does not say, **exactly one execution** happens. The determinism repeat is dropped, and the
  "results differing between the two repeat runs" INCONCLUSIVE condition does not apply.
- If it says two, the original rule (run plus immediate repeat, both kept) applies.

## M2. Q1 is a deterministic race simulation, not a likelihood estimate

A Q1 FAIL would show only that the post-decision window exists, and what executes inside it when the shared
`parameters` object is changed there. It would say nothing about how likely a real concurrent writer is to
hit that window, in this code or in any deployment. Results must say this beside the verdict.

## M3. Q1 and Q3 are two separate weaknesses, reported separately

- **Q1** (A1, B1 execution): whether the authorization-to-execution boundary binds what runs to what was
  decided. This concerns `workflow.py`.
- **Q3** (B1 package): whether the offline package verifier checks the cross-field integrity between the
  authorized parameters and `commands_sent`. This concerns `tools/verify_package.py`. It is a separate
  component and a separate potential finding, even though the same B1 run produces the evidence for both.

Each gets its own verdict line, its own STATUS.md entry if it FAILs, and its own fix decision. Neither verdict
is folded into the other.

## M4. O1 stays an observation

O1 (a fresh run with new parameters gets a fresh ALLOW) never produces a FAIL, and never feeds Q1–Q3. It is
reported as a design property: the Gate authorizes capability and `requested`, not parameters.

## M5. Nothing touches a real file or device (clarification)

- In layer A, `"sandbox/a.txt"`, `"/etc/passwd"`, `"append"` and `"overwrite"` are **inert strings in memory**.
  The recording executor stores a deep copy of the parameters it receives and does nothing else: it opens,
  reads and writes no file.
- In layer B, every command goes only to `FakeVehicle`, an in-memory stand-in that appends the command to a
  Python list. No MAVLink link, SITL, network or hardware is involved.
- The probe must contain no `open()` of a path taken from case parameters. Its only file writes are the
  results under `results/sv_attack_001/` and packages written under a fresh temporary `HOME`. A reviewer
  can check this by reading the probe before it runs.

## M6. Re-verify the code paths against the frozen hashes before implementation

Before the probe is written, the eight target hashes are recomputed from `main`, and the line references in
the registration (workflow.py L82–87, L183–189, L222–227, L248–253, L305; contracts.py L15–18;
verify_package.py L991–1011) are re-read at those exact bytes. Any drift is recorded in a dated note before
any code is written. The probe repeats the hash check at run time, as already registered.

## Credit (restated, unchanged)

John Rodriguez contributed the concern: authorization gates can be manipulated. He did not design this attack
and has not reviewed it. ChatGPT suggested the post-authorization substitution idea, and Claude drafted the
cases.
