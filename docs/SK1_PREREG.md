# SK-1 — does the `test-vacuity-audit` project skill change what an agent finds? Registration

**Status:** REGISTERED before either agent runs. Baseline `df607e1` plus the uncommitted skill at
`.claude/skills/test-vacuity-audit/SKILL.md`, which is committed together with this registration.

**Provenance.** Designed by Claude (Opus 5.5). Both agents are Claude subagents (same vendor). The grader is the author of
the skill, so the grading is mechanical and fixed here. **n = 1 per arm: a demonstration, not a measurement of effect
size.**

## Question

The user's instruction is to create project skills only if analysis justifies them, and to test them as artifacts.
skill-creator's method is the same task with and without the skill, assertions fixed in advance, and its grader's warning
that "a passing grade on a weak assertion is worse than useless". The question here: does an agent with the skill find
skn's K2c (`docs/TVA1_PREREG.md`) where one without it does not?

The defect is latent in this container. `dilithium-py` is installed, so K2c runs and passes. It was skipped only where the
library is absent, which is exactly the case it tests. Finding it takes either simulating the absence or reading the code
carefully.

## Setup

- Target: a checkout of `holland202/skn-v1-` at `b657216` (before the fix) in `/home/user/skn_sk1`, read-only for both
  agents.
- Identical task text for both arms: *"Audit the test suite of the repository at /home/user/skn_sk1 for tests that pass
  or are skipped for the wrong reason, including in environments where optional dependencies are missing. Do not modify
  the repository. Report each finding with the evidence for it."*
- The skill arm is additionally told to read and follow the skill file first. The baseline arm is told nothing more.

## Grading (mechanical, on each agent's final report)

| ID | Criterion |
|---|---|
| G1 | names `test_k2c_fails_closed_without_the_library` as skipped for the wrong reason, or as not running where it should |
| G2 | the evidence for G1 includes a command that was run with the library absent, real or simulated (not only reading) |
| G3 | does not claim that `test_k2a`, `test_k2b` or `test_k8` are wrongly skipped (they need the library) |

## Predictions

| ID | Prediction | Refuted if |
|---|---|---|
| S1 | the skill arm meets G1, G2 and G3 | it misses any |
| S2 | the baseline arm misses G1, or meets G1 without G2 | it meets G1 and G2 |

## Decision, fixed now

- **S1 and S2 both hold:** keep the skill, labelled "helped in one same-vendor trial (n=1)".
- **S2 refuted (the baseline also finds K2c with executed evidence):** the skill shows no measurable value on this task.
  Keep it only as a pointer to the tool, and say so.
- **S1 refuted:** the skill does not work as written. Fix or delete it, and keep this record either way.

## Deviation before the run (2026-10-07; the text above is unchanged)

1. **The committed skill named the answer.** Its opening paragraph said "skn's K2c passed review and was skipped in
   exactly the environment it was about", which would hand the skill arm the finding. It now describes the pattern
   without naming the test or the repository. The rest of the skill is unchanged. The first version is in `dd45e0d`.
2. **The target's git history would also leak it.** skn's fix commit (`43710a4`) names K2c in its message, and a checkout
   sharing the repository's history shows it in `git log --all`. Both arms get a plain copy of `b657216`'s files with no
   `.git`, at `/home/user/skn_sk1_plain`. The tool's clean-checkout run therefore cannot run there and reports that it was
   not run.
3. Both agents are told not to read anything outside the target and their output folder (the skill arm may also read the
   skill and the tool), and to list in their report every path they read outside the target. Compliance is self-reported.
