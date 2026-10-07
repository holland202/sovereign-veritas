---
name: test-vacuity-audit
description: Find tests that pass or skip for the wrong reason in a pytest or unittest suite - tests skipped because of a dependency they never use (collateral skips), tests that pass only because of files not in the commit, tests with no assertion, and truthiness-only asserts. Use when asked to audit a test suite, before reporting "N tests pass", or whenever a test's skip or pass may depend on the environment (an optional library, a local file, a platform).
license: MIT
---

# Test-vacuity audit

A passing or skipped test is a claim about the code only if it could have gone the other way. This procedure runs the
suite under changed conditions, because reading the tests misses environment-dependent cases. A typical one: a test of
the behaviour *without* a library sits in a class whose setup skips when that library is missing, so it never runs in
the one environment it is about.

## Procedure

1. **Run the audit as is.** From the Sovereign Veritas repository root:
   `python tools/test_vacuity_audit.py REPO [TEST_PATHS]`. It runs pytest three times:
   - as is;
   - with every skip disabled;
   - in a clean checkout of HEAD.

   It then compares outcomes test by test. unittest files that do not match `test_*.py` (for example `tests/run_tests.py`)
   must be passed as `TEST_PATHS`.
2. **Find the optional dependencies the suite guards on.** Grep the tests and the code for `skipTest`, `skipIf`,
   `importorskip`, `pytest.mark.skipif`, and `try: import ... except ImportError`.
3. **Re-run the audit with each dependency absent, even if it is installed here.** An installed library hides every
   defect that only appears without it. Make it absent with a shadow module:
   `mkdir shadow && echo 'raise ImportError("absent: audit stand-in")' > shadow/<module>.py`, then
   `PYTHONPATH=shadow python tools/test_vacuity_audit.py REPO ...`. Say in the report that this is a stand-in. It takes the
   same path as a real absence only for code that detects the library by importing it, not for code that uses
   `importlib.util.find_spec`.
4. **Interpret each line.** A flag is a lead, not a verdict: read the test before concluding.
   - `FLAG collateral skip`: the test passes with its skip removed, so it does not need what its skip guards. It is
     skipped where it should run. Move it out of the skipping scope, or narrow the guard.
   - `ok justified skip`: the test fails without the dependency. Keep the skip.
   - `FLAG untracked dependency`: the test passes only with files the commit lacks (check `.gitignore`). Commit the file,
     or make the test create it.
   - `review no assertion` and `review truthiness`: read each one. `assert result` also passes for `{"status": "FAIL"}`.
5. **Report with evidence.** Paste the tool's output verbatim, and state the commit, the platform, which dependencies
   were simulated absent, and what you read to confirm each flag.

## Constraints

- Never edit a test so that the audit passes. A finding is fixed in the test's scope or in the code, and the
  before/after output is kept.
- Do not report "0 flagged" without saying which dependencies were made absent. An audit of an environment where
  everything is installed says nothing about the environments where it is not.
- The tool runs the suite three times. Use `--no-clean-checkout` outside a git repository.
