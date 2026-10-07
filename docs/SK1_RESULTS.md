# SK-1 results: S1 held, S2 REFUTED. The agent without the skill also found K2c, with executed evidence. The skill shows no measurable value on this task and is kept only as a pointer to the tool

Registration: `docs/SK1_PREREG.md`, commit `dd45e0d`, with a pre-run deviation in `72c6fe8`. Both were pushed before
either agent ran. Two Claude subagents (same vendor, separate contexts) did the audits. The grader is Claude (Opus 5.5),
who wrote the skill and this registration, so the grading below is mechanical and quotes each report. Chad Holland directed
the work. He has not reviewed this text. **n = 1 per arm: a demonstration, not a measurement.**

Both reports are kept verbatim, with the agents' raw outputs:
- `results/sk1/skill_arm/REPORT.md`, with `audit*.txt` and its probes;
- `results/sk1/baseline_arm/REPORT.md`, with `logs/` and its probes.

## Failures and limits (first)

1. **S2 REFUTED.** The prediction was that the baseline arm would miss K2c, or find it only by reading. It found it, and
   ran the suite with the library blocked (G1 and G2 met; quotes below).
2. **The decision registered for this case therefore applies:** "the skill shows no measurable value on this task. Keep it
   only as a pointer to the tool, and say so." Both `SKILL.md` and `docs/SKILLS_ADAPTATION.md` now say so.
3. **The baseline found more.** It reported 12 findings, the skill arm 4 plus 3 minor ones from reading only. All four of
   the skill arm's main findings are among the baseline's:
   - K2c's collateral skip: baseline 1;
   - the dashboard test without the library: baseline 2;
   - two `test_k2b` assertions that cannot fail: baseline 11;
   - the `k1e` guard that can be switched off: baseline 6.

   The baseline also found eight that the skill arm did not (3, 4, 5, 7, 8, 9, 10, 12), mostly by mutation testing.
   - **Interpretation, not tested:** the skill may narrow an agent's attention to the tool's categories.
   - With n = 1, this cannot be told apart from run-to-run variation.
4. **What a refuted S2 does and does not show.** It shows that this task did not discriminate. Its defect was findable
   without the skill by an agent told to consider missing dependencies. It does not show that the skill never helps.
5. **Compliance with the read restrictions is self-reported.** The baseline arm reports one write outside its scratch
   area, made by its tool harness (an oversized search result).
6. **The trial found two things in the tool. Both are now handled.**
   - The skill arm observed that `tools/test_vacuity_audit.py` printed `VERDICT  0 flagged` with exit 0 when the suite
     could not even be collected (numpy absent). That verdict was fail-open.
     - Fixed: such a run is now `VERDICT  NOT ESTABLISHED`, exit 2.
     - Checking it, I found a second fail-open case of the same kind. A module that imports an untracked file aborts
       the clean-checkout run, and its tests read as "not in HEAD" (review only). They are now flagged.
     - Details are in `docs/TVA1_RESULTS.md`, addendum 1.
   - The skill arm also noted that the static review inspects only bare `assert`, not `self.assert*`. That limit is now
     stated in the skill.

## Grading (criteria fixed in `docs/SK1_PREREG.md`)

| Arm | G1: names K2c as skipped for the wrong reason | G2: G1's evidence includes a command run with the library absent | G3: does not call K2a, K2b or K8 wrongly skipped |
|---|---|---|---|
| skill | **met**: "`FLAG  collateral skip: tests.run_tests.TestSignedDocking::test_k2c_fails_closed_without_the_library`"; "it never runs in the one environment it is about" | **met**: run 2 with `PYTHONPATH=/home/user/sk1_skill_out/shadow_dilithium` (stand-in), output `VERDICT  1 flagged` (`audit2_dilithium_absent.txt`) | **met**: "k2a, k2b and k8 each `FAIL … ML-DSA-65 unavailable (pip install dilithium-py)`, so their skips are justified" |
| baseline | **met**: "1. HIGH: the fail-closed test is skipped in the one environment where it matters"; "`test_k2c_fails_closed_without_the_library`" | **met**: "To simulate a missing dilithium-py, I put a shadow package that raises ImportError ahead of the real one on PYTHONPATH"; "Library blocked, skip removed: the test runs and passes" (`logs/a.txt`: `ccpl.available() = False` … `test_k2c_fails_closed_without_the_library … ok`) | **met**: it calls no docking test wrongly skipped. Its finding 11 concerns two `test_k2b` assertions, not the skip |

## Outcome

| ID | Prediction | Result |
|---|---|---|
| S1 | the skill arm meets G1, G2 and G3 | **HELD** |
| S2 | the baseline arm misses G1, or meets G1 without G2 | **REFUTED**: G1 and G2 met |

## Leads for skn, reported by the two agents (not reproduced here)

Both agents audited skn at `b657216`. K2c has been fixed since (`43710a4`). Whether the following still hold at skn's
current HEAD was not checked. Each is a lead with the agent's evidence in its report, not a verified finding.
- **Formation tests:** `TestFormationV3` passes a boolean where the `slc` controller goes. 1200 and 2400 swallowed
  `AttributeError`s per test. The tests still pass with `node.step` removed (baseline 3).
- **Closed loop:** `test_k3_closed_loop_paired_reaches_below` passes with `closed_loop` ignored (baseline 4).
- **K1d reference:** the reference uses the module's own `rips_complex`. A triangle-rule mutant changes 103 of its 200
  clouds and passes (baseline 5; skill arm, minor).
- **Topology guard:** `k1e` passes with `beta_1 = 0` (baseline 6, skill arm F4).
- **CI:** the "sabotage must exit 1" steps accept any non-zero exit, a crashing sabotage branch included. The install
  check imports from the checkout (baseline 7, 8).
- **Dashboard test:** without the library it checks no docking line, and it accepts constant values (baseline 2, skill
  arm F2).

## Left unrun

- More trials, with a defect that a careful agent finds less readily, and n large enough to see variation.
- A blind grader, and an agent from another vendor.
- Whether the skill changes how long an agent takes, or how much it spends.
