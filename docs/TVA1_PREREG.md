# TVA-1 — a dynamic test-vacuity audit: registration

**Status:** REGISTERED, nothing built or run. Committed and pushed before `tools/test_vacuity_audit.py` exists. Baseline
`018ecda`.

**Provenance.** Designed by Claude (Opus 5.5) at Chad Holland's direction; the same model builds, runs and judges:
**self-tested**. Container (Linux x86_64) only.

## Why

`vacuity_lint` (Type A) finds verification code with no fail path. It does not detect two failures this week produced:

- **skn K2c** (fixed in skn `43710a4`). The test checks behaviour when `dilithium-py` is absent. It sat in a class whose
  `setUp` skips when `dilithium-py` is absent, so it was skipped in the only environment it is about.
- **SV `1315fbe`**. Four files the tests read were gitignored. The suite passed in the working tree and failed in any fresh
  clone (`tests/test_gate_supplement.py`), until `1fbdced`.

Both are visible only by running tests under changed conditions, not by reading them.

## What will be built

`tools/test_vacuity_audit.py REPO [TEST PATHS]` runs pytest in three ways and reads two kinds of static signal:

1. **as is**: the outcome and skip reason of every test;
2. **with skipping disabled**: `-p no:skipping`, plus a plugin that turns `unittest.TestCase.skipTest` and `pytest.skip`
   into no-ops. A test that was skipped and now *passes* was skipped for a reason its body does not need: a
   **collateral skip** (flagged). One that now fails or errors had a justified skip;
3. **in a clean checkout of HEAD** (a `git worktree`): a test that passes as is but fails, errors or skips in the clean
   checkout depends on files that are not in the commit (flagged);
4. static: test functions with no `assert`, `pytest.raises`/`warns` or `self.assert*` (review), and `assert` statements
   whose test is a bare name, call or attribute (truthiness only, review).

Exit 1 if anything is flagged, 0 if nothing is, 2 if pytest could not run.

## Predictions

| ID | Prediction | Refuted if |
|---|---|---|
| V1 | skn at `b657216`, with `dilithium-py` absent: `test_k2c_fails_closed_without_the_library` is flagged as a collateral skip | it is not flagged |
| V2 | skn at `43710a4`, `dilithium-py` absent: K2c is not flagged; every test still skipped is classified a justified skip | K2c flagged, or a still-skipped test flagged |
| V3 | SV at `1315fbe` with the then-untracked `contract/gate_vectors_supplement.jsonl` present in the working tree: tests in `tests/test_gate_supplement.py` are flagged by the clean-checkout run | not flagged |
| V4 | planted fixtures: a test with no assertion and a test that only asserts a truthy dict are reported; a test with a real comparison is not | either planted test missed, or the control reported |
| V5 | SV at the commit that adds the tool: 0 collateral skips and 0 clean-checkout differences | any (that would be a finding, not a tool failure) |

**"dilithium-py absent" is simulated, a named stand-in.** In this container `dilithium-py` is installed. A shadow
`dilithium_py` module that raises `ImportError` is put first on `PYTHONPATH`. `skn/ccpl.py` detects the library with
`try: from dilithium_py.ml_dsa import ML_DSA_65 except ImportError`, so the shadow takes the same code path as a real
absence. It would not take the same path for code that used `importlib.util.find_spec`.

Anti-vacuity: V1 and V3 are planted, known-positive cases from history; V2 and the V4 control are negatives.

## Left unrun

Repositories that use other test runners, `pytest.importorskip` with a module that is present but broken, tests whose
skip guards a hardware device, and the S25.
