# TVA-1 results: the dynamic audit finds both historical cases (V1–V4 held); on SV itself V5 was refuted, by a test that passed for the wrong reason (4 of 5 as registered)

Registration: `docs/TVA1_PREREG.md`, commit `9d3f18a`, pushed before `tools/test_vacuity_audit.py` existed. Linux
container (x86_64, Python 3.13.16). Claude-assisted (Claude Opus 5.5), **self-tested**. Chad Holland directed the work. He
has not reviewed this text or the code line by line.

## Failures and limits (first)

1. **V5 REFUTED.** The prediction was 0 collateral skips in SV at `df607e1`. The audit flagged one:
   `FLAG  collateral skip: tests.test_vehicle_action::test_no_vehicle_is_could_not_run (skip reason: "could not import
   'pymavlink': No module named 'pymavlink'")` (`results/tva1/sv_df607e1.txt`).
2. **On reading, the skip was right, and the test was wrong.** The test checks that `tools/vehicle_action.py` says COULD
   NOT RUN when no vehicle answers. Without pymavlink, the tool prints `COULD NOT RUN: pymavlink is not installed` and
   exits 2, which satisfies the same assertion. So un-skipped, the test passed for the wrong reason: it could not tell an
   unreachable vehicle from a missing library. **Fixed** by requiring the vehicle reason (`no vehicle at` or
   `no heartbeat from`). Checked three ways:
   - with pymavlink (scratch virtualenv): `1 passed`;
   - without it, as is: skipped;
   - un-skipped without it: fails, and the audit now prints `ok justified skip: ... -> failure when un-skipped`.
3. **The collateral-skip rule has a false-positive mode, and V5 hit it.** "Passes with its skip removed" also covers a
   test whose assertion is met through the dependency-missing path itself. That is still worth flagging, because it
   means the assertion is too weak, but the label is wrong for it. The skill's rule "a flag is a lead, not a verdict"
   exists for exactly this.
4. **"Library absent" in V1 and V2 is a stand-in:** a shadow `dilithium_py` module that raises `ImportError`, put first on
   `PYTHONPATH`. It takes the same path as a real absence for `try: import ... except ImportError`, not for code that uses
   `find_spec`.
5. **Static review is review only.** SV has 0 test functions with no assertion in their body and 16 truthiness-only
   asserts, listed in `results/tva1/sv_df607e1.json`. Each has to be read; none was judged here.
6. **The tool runs the suite three times** (3 min 57 s for SV in this container). It was not run on the S25.

## Outcome

| ID | Prediction | Result |
|---|---|---|
| V1 | skn `b657216`, library absent: K2c flagged | **HELD**: `FLAG collateral skip: tests.run_tests.TestSignedDocking::test_k2c_fails_closed_without_the_library`; K2a, K2b and K8 justified (`results/tva1/skn_b657216.txt`) |
| V2 | skn `43710a4`: K2c not flagged; the remaining skips justified | **HELD**: `0 flagged`; 3 justified skips (`skn_43710a4.txt`) |
| V3 | SV `1315fbe` with the then-gitignored supplement present: supplement tests flagged | **HELD**: both flagged as untracked dependencies, `FileNotFoundError` in the clean checkout (`sv_1315fbe_with_untracked_supplement.txt`) |
| V4 | planted no-assertion and truthiness-only tests reported, control not | **HELD**: `no assertion: tests/test_planted.py::test_no_assertion`, `truthiness: ... assert helper()`; the control is not listed (`planted_fixtures.txt`) |
| V5 | SV `df607e1`: 0 collateral skips, 0 clean-checkout differences | **REFUTED**: 1 flag (items 1–3); 0 clean-checkout differences |

`tests/test_test_vacuity_audit.py` pins the tool on a throwaway git repository with one collateral skip, one justified
skip and one untracked dependency, plus a clean control.

## What changed in the repository

- `tools/test_vacuity_audit.py` (new).
- `tests/test_vehicle_action.py::test_no_vehicle_is_could_not_run` now asserts the reason (item 2).
- The project skill `.claude/skills/test-vacuity-audit/` (validated). Whether it helps an agent is SK-1:
  `docs/SK1_RESULTS.md`.

## Left unrun

- Other test runners.
- `importorskip` of a module that is present but broken.
- A run with every optional dependency of SV made absent at once.
- The 16 truthiness-only asserts, read one by one.
- The S25.
