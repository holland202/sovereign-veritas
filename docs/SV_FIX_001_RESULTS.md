# SV-FIX-001 results: F1 PASS, F2 PASS (one execution, container, not on the S25)

| | |
|---|---|
| Registration | [`SV_FIX_001_PREREG.md`](SV_FIX_001_PREREG.md) (`b390562`) |
| Fix code | `d63d3fd`. Related experiment: ATTACK_HARNESS Amendment 1, `8b6f93b` then `9b3f7c2` |
| Verification tooling | Probe copy `33e09a2`, driver `ce8956c`, both committed before the run |
| Execution | **One.** Chad Holland authorized it directly on 2026-10-10. No repeat |
| Environment | Fresh clone at `ce8956c`, `python3 -I`, Python 3.13.15, Linux x86-64 container. **Not run on the S25** |
| Evidence | `results/sv_fix_001/`, unedited; `SHA256SUMS` sha256 `865acdabff62582bb2f7bd4c7b3e0ad0b40a0d8e46d62c6ef86dc9a02805ba83` |

Drafted by Claude (Opus 5.5), which also wrote the fixes, the registration, the probe and the driver, at Chad
Holland's direction. Chad has not reviewed it line by line. Not independent. ChatGPT has not audited this run.

## What is weak, first

- **R6 is weaker than it looks.** Without `--legacy`, all 24 regression packages already fail under the
  unfixed verifier (exit 1 or 2) for other reasons, so "exit codes unchanged" says little on its own. A
  supplementary comparison was therefore run afterwards. It was **not registered**, and was added after
  seeing R6. With `--legacy`, both verifiers were compared on the `vehicle_check_bound` line and the final
  verdict: **24 of 24 identical**, and **21 of the real ArduCopter SITL packages verify `CONSISTENT` under the
  fixed verifier.** Those include real MAVLink `goto` (2 commands), `takeoff` (3), `land` (1) and
  zero-command refusals. So F2's MAVLink rules accept honest SITL command sequences. The file is
  `results/sv_fix_001_supplementary_r6_legacy.txt` (sha256 `14ff1d3f…bb1f`).
- **The probe prints `Q3 (offline verifier) FAIL` on the fixed code. This is expected (R3), not a
  regression.** With F1 in place nothing diverges, so B1's package honestly verifies, and the probe's
  unchanged Q3 rule calls an exit 0 a FAIL. R4 is the registered Q3 test.
- **A deviation from the registration.** The registration said the probe's hash table would be updated in a
  "probe-only commit". Editing `tools/sv_attack_001_probe.py` would have changed SV-ATTACK-001's registered
  evidence, which the same registration forbids (Run rule 4). The two hash lines were therefore changed in a
  **copy**, `tools/sv_fix_001_probe.py`. Its diff against the original is exactly those two lines, and the
  original is untouched.
- **R7 (CI) was judged on the fix code, not on this run's commit.** CI on `9b3f7c2` (the fix code plus the
  amendment): 59 of 59 success. Local `pytest` failing test names are identical to unmodified `main`
  `438e6d5`, compared name by name (73 environmental, 0 new). The later commits add only tooling and
  evidence.

## Results (pasted from `results/sv_fix_001/verify.log`)

| Check | Registered prediction | Observed |
|---|---|---|
| R1 | Q1 PASS, C1–C4 hold | `A1 … divergence False … executed [{'target': 'sandbox/a.txt', 'mode': 'append'}]`; `B1 … divergence False … lat_e7 353640993`; `controls C1 True C2 True C3 True C4 True`; **Q1 PASS** |
| R2 | Q2 PASS | **Q2 PASS** (A2 duplicate `record_id` refused; A3 `ReservationRefused`) |
| R3 | B1 package verifies, not counted for Q3 | `B1 verify_package exit 0 … CONSISTENT` (probe label "Q3 FAIL", as explained above) |
| R4 | fixed verifier on run1 `B1.json` exits 1 | **exit 1**: `FAIL vehicle_check_bound commands sent ['goto {..."lat_e7":353676966...}'] are not the authorized ['goto {..."lat_e7":353640993...}']` |
| R5 | run1 `B0.json` exits 0 | **exit 0**, `CONSISTENT` |
| R6 | 24 exit codes unchanged | **24 of 24 unchanged**; see the weakness above |
| R7 | CI green, no new local failures | 59/59 on `9b3f7c2`; failing test names identical to `main` |
| R8 | mutant F1 gives Q1 FAIL | mutant `workflow.py` sha256 `de021b0b…e022`: **Q1 FAIL**, A1 and B1 diverge again |
| R9 | mutant F2 exits 0 on R4's package | **exit 0**, `CONSISTENT` |

```
VERDICT  F1 PASS (R7 = CI, judged separately)  |  F2 PASS  |  probe Q2 PASS  Q3(B1) FAIL
```

**F1 PASS. F2 PASS**, by the registered rules.

There was one extra, unplanned confirmation of F2 in R8. In the mutant run, B1 diverged again, and the
**fixed** verifier rejected that freshly produced package (`B1 verify_package exit 1`). That is a second
divergent package caught, not only run1's.

## What this does not establish

The registration's limits apply unchanged:
- F1 closes the measured window, the caller's mutable `parameters` dict between decision and execution. It
  does not cover:
  - an executor that reads its inputs from elsewhere;
  - a malicious executor;
  - the XB-1/XB-2 race and crash cases.
- F2 covers `vehicle_command_check` with the `fake` and `mavlink` backends only.
- Unsigned packages can still be rewritten consistently. ATTACK_HARNESS P5 still holds after Amendment 1.
- Same author throughout; no outside review or reproduction yet. **NOT VALIDATED. NOT PRODUCTION-READY.**
- Merging PR #71 is Chad's decision.
