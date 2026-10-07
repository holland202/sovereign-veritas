# Test-vacuity audit: /home/user/skn_sk1_plain

**Result.** The suite has 30 tests, all in `tests/run_tests.py`. I found four tests or assertions that skip or pass for the wrong reason:
- **The tool flagged one: a collateral skip.** It only shows when dilithium-py is absent.
- **Three more came from reading the tests and running mutants.** The tool cannot detect them.

The repository was not modified. Snapshots of all 155 files (sha256, size, mtime) are identical before and after, and no `__pycache__` or `.pytest_cache` was created.

## Setup
- **What was audited:** `tests/run_tests.py`, a unittest file that has to be passed to the tool explicitly.
- **Commit:** none. The directory is not a git repository (`git rev-parse HEAD` → "fatal: not a git repository").
  - Fingerprint instead: sha256 of the per-file sha256 list is 76698425c3e274ea…; `tests/run_tests.py` is 52a3d2cdb6ecd3e9….
- **Platform:** Linux 6.18.44-fc-v77 x86_64, Python 3.13.16 (/usr/bin/python3), pytest 9.1.1, numpy 2.5.3, dilithium-py 1.4.0. CI uses Python 3.12.
- **Dependency guards (skill step 2):** there is exactly one, `skn/ccpl.py:17-20`: `try: from dilithium_py.ml_dsa import ML_DSA_65 except ImportError: ML_DSA_65 = None`, exposed as `ccpl.available()`.
  - It is used in `TestSignedDocking.setUp` (`skipTest`, run_tests.py:136-139), in `TestLiveDashboard` (:210), at node.py:294 and at skn_orbital_tui.py:60.
  - There is no skipIf, importorskip or find_spec anywhere.
  - numpy is imported without a guard everywhere.
- **Simulated absent:** dilithium-py and numpy, each by a shadow module on PYTHONPATH containing `raise ImportError("absent: audit stand-in")`. This is a stand-in, not a real uninstall.
  - The code detects dilithium-py by importing it, so the stand-in takes the same path as a real absence.
  - I checked that it does: `ccpl.available()` returned False, and the dashboard subprocess printed its fail-closed line.
- **Actually absent:** scipy and matplotlib. They are declared in pyproject.toml, but nothing in skn/, tests/ or skn_orbital_tui.py imports them, so every run covers their absence. I could not test with them installed (no network).
- **Commands:** run from /home/user/sk1_skill_out with `PYTHONDONTWRITEBYTECODE=1 TMPDIR=/home/user/sk1_skill_out/tmp` set, so nothing was written into the repo:
  `python3 -P /home/user/sovereign-veritas/tools/test_vacuity_audit.py /home/user/skn_sk1_plain tests/run_tests.py --no-clean-checkout`
  - For the absence runs I added `PYTHONPATH=/home/user/sk1_skill_out/shadow_dilithium` (or `.../shadow_numpy`).
  - `--no-clean-checkout` is needed because there is no git repo.
  - `-P` only keeps the tool's own folder off `sys.path`. The tool uses only the standard library, and its pytest subprocesses are unaffected.

## Tool output (verbatim)
Run 1, as is (dilithium-py present), exit 0:
```
test_vacuity_audit | /home/user/skn_sk1_plain | as is: 30 tests, {'passed': 30, 'failed': 0, 'error': 0, 'skipped': 0}
  skipped as is: 0; with skipping disabled: 0 pass (collateral), 0 fail or error (justified)
  clean checkout: not run (skipped (--no-clean-checkout))
  review: 0 test(s) with no assertion in their body; 0 truthiness-only assert(s)
VERDICT  0 flagged (0 collateral skip(s), 0 untracked dependenc(ies))
```
Run 2, dilithium-py absent (stand-in), exit 1:
```
test_vacuity_audit | /home/user/skn_sk1_plain | as is: 30 tests, {'passed': 26, 'failed': 0, 'error': 0, 'skipped': 4}
  skipped as is: 4; with skipping disabled: 1 pass (collateral), 3 fail or error (justified)
  FLAG  collateral skip: tests.run_tests.TestSignedDocking::test_k2c_fails_closed_without_the_library  (skip reason: 'dilithium-py not installed')
  ok    justified skip:  tests.run_tests.TestSignedDocking::test_k2a_genuine_record_verifies  -> failure when un-skipped
  ok    justified skip:  tests.run_tests.TestSignedDocking::test_k2b_tamper_wrong_key_replay_all_fail  -> failure when un-skipped
  ok    justified skip:  tests.run_tests.TestSignedDocking::test_k8_no_nonce_store_refuses_and_refusals_keep_store_empty  -> failure when un-skipped
  clean checkout: not run (skipped (--no-clean-checkout))
  review: 0 test(s) with no assertion in their body; 0 truthiness-only assert(s)
VERDICT  1 flagged (1 collateral skip(s), 0 untracked dependenc(ies))
```
Run 3, numpy absent (stand-in), exit 0:
```
test_vacuity_audit | /home/user/skn_sk1_plain | as is: 1 tests, {'passed': 0, 'failed': 0, 'error': 1, 'skipped': 0}
  skipped as is: 0; with skipping disabled: 0 pass (collateral), 0 fail or error (justified)
  clean checkout: not run (skipped (--no-clean-checkout))
  review: 0 test(s) with no assertion in their body; 0 truthiness-only assert(s)
VERDICT  0 flagged (0 collateral skip(s), 0 untracked dependenc(ies))
```
Run 4, on a copy without the files `.gitignore` excludes (`assets/skn_demo.gif`, `assets/skn_demo.mp4`), as a stand-in for the clean checkout, exit 0:
```
test_vacuity_audit | /home/user/sk1_skill_out/clean_approx | as is: 30 tests, {'passed': 30, 'failed': 0, 'error': 0, 'skipped': 0}
  skipped as is: 0; with skipping disabled: 0 pass (collateral), 0 fail or error (justified)
  clean checkout: not run (skipped (--no-clean-checkout))
  review: 0 test(s) with no assertion in their body; 0 truthiness-only assert(s)
VERDICT  0 flagged (0 collateral skip(s), 0 untracked dependenc(ies))
```
The project's own runner, run the way CI runs it (`python3 tests/run_tests.py`), agrees with pytest:
- dilithium-py present: "Ran 30 tests … OK"
- dilithium-py absent: "Ran 30 tests … OK (skipped=4)"

## Findings

### F1 (tool flag): collateral skip of `TestSignedDocking::test_k2c_fails_closed_without_the_library` when dilithium-py is absent
- **What:** the test checks behaviour *without* dilithium-py: no lock, nothing committed. But its class `setUp` (run_tests.py:136-139) calls `skipTest("dilithium-py not installed")`, so it never runs in the one environment it is about.
- **Evidence:**
  - Run 2 flags it: it passes once skipping is disabled.
  - I confirmed this without the tool's plugin by calling each docking test with `setUp` bypassed and the library absent.
    - `PASS test_k2c…`.
    - k2a, k2b and k8 each `FAIL … ML-DSA-65 unavailable (pip install dilithium-py)`, so their skips are justified.
  - Read: the test body (run_tests.py:183-194) sets `ccpl.ML_DSA_65 = None` itself. A failed import produces the same value (ccpl.py:19-20), so the test needs nothing from the library.
- **What it costs (mutant M1, a scratch copy):** I made docking fail *open* without the library, changing node.py:294-295 to lock, commit and return True.
  - With the library absent, the suite still reports `Ran 30 tests … OK (skipped=4)`.
  - With `setUp` bypassed, k2c catches it: `Tuples differ: (True, True, 2) != (False, False, 1)`.
  - With the library present, k2c fails (`FAILED (failures=1)`).
- **Scope:** CI is not affected. It installs dilithium-py and fails if anything is skipped (verify.yml step "the docking tests must not have been skipped").
  - The gap is any run without the library, which README:169 presents as normal ("the docking tests need `pip install dilithium-py`").
  - In such a run, README:353-354's claim ("Without `dilithium-py` it does not lock and commits nothing. Tested: tests K2a-K2c") is not exercised.
- **Suggested fix:** move k2c to a class without that `setUp`, or put the skip only on k2a, k2b and k8 (for example `@unittest.skipUnless(ccpl.available(), …)`, or inside `dock()`).

### F2 (my review): `TestLiveDashboard::test_plain_frames_show_real_state` checks nothing about docking when dilithium-py is absent
- **What:** the only docking assertion is `if ccpl.available(): self.assertEqual(last.count("sig VALID"), 6)` (run_tests.py:210-211), with no else branch. Without the library the test passes on topology and vault strings alone.
- **Evidence (mutant M2):** I changed the dashboard's no-library branch (skn_orbital_tui.py:60-61) to print six false `SKN-00i->SKN-00j LOCK  sig VALID` lines.
  - With the library absent, the test still reports `... ok` and the suite `OK (skipped=4)`.
  - That is the false display the test's docstring says it prevents ("shows only computed values").
- **Suggested fix:** add an else branch that asserts the line "docking fails closed, no locks" and `last.count("sig VALID") == 0`.

### F3 (my review): two assertions in `test_k2b_tamper_wrong_key_replay_all_fail` cannot fail
- **What:** line 161 is `assertFalse(verify_dock(bad, pk)[0], field)` and line 167 is `assertFalse(verify_dock(rec, other.dock_public_key)[0])`. Both call `verify_dock` with no nonce store.
  - Since K8 (ccpl.py:76-77), that call returns False for every record. test_k8 line 176 itself asserts this for a genuine record.
  - The tool's "0 truthiness-only" says nothing here: it only inspects bare `assert` statements, and this suite uses only `self.assert*`.
- **Evidence:** a probe with the real library:
  ```
  L161 as written (target_id tampered), no store : (False, 'manifest does not hash to manifest_sha3_512')
  L161 with NO tampering,              no store : (False, 'no nonce store: replay cannot be checked (fail closed)')
  L167 as written (other node's key),  no store : (False, 'record names a different public key')
  L167 with the RIGHT key,             no store : (False, 'no nonce store: replay cannot be checked (fail closed)')
  ```
  The two reasons these lines appear to test, "manifest does not hash…" and "record names a different public key", are asserted in no test (grep count 0).
- **Impact is limited:**
  - The test still has real checks: line 166 (`"signature does not verify"`) and lines 168-170 (replay, with a store).
  - test_k8 covers tampering and the wrong key with a store, when it runs.
- **Suggested fix:** assert the reason strings, or pass a store.

### F4 (my review): the topology guard can be switched off and the suite still passes
- **What:** `test_k1e_guard_does_not_cut_links_in_rendezvous` only asserts `frp_events == 0`, and no test ever makes the guard fire.
- **Evidence (two mutants):**
  - M3 makes `compute_betti_one` return 0 (swarm.py:93): all 30 tests pass (`Ran 30 tests … OK`).
  - M3b restores the pre-K1 count (`graph_cycle_rank`): k1e fails with `AssertionError: 30 != 0`.
  - So k1e does catch the regression it was registered for, but a guard that never fires passes everything.
- **Suggested fix:** add a case with a real hole (b1 > 0) and assert the guard fires.

### Minor (from reading only, not verified by running)
- `test_commit_returns_bytes` (L25-27) checks only `len(h) == 64`, not the type. A 64-character string would pass.
- `test_k1d` (L111-129) takes its edges and triangles from `skn.topology.rips_complex`, the module under test. Only the rank step is checked independently.
- `test_k6` (L240-254) leaves its `mkdtemp()` directory behind and two files unclosed (a ResourceWarning appears in the baseline run). This is housekeeping only.

## Not findings, and limits
- **Justified skips:** k2a, k2b and k8 fail when un-skipped (message quoted under F1).
- **numpy absent:** the suite fails loudly at collection (pytest reports 1 error; the runner raises ImportError and exits 1). The tool still prints "0 flagged" for that run, so read run 3 as "the suite cannot run", not as "clean".
- **Untracked-dependency check:** the tool could not run it because there is no `.git`. Run 4 is only an approximation: it assumes every file not excluded by `.gitignore` would be committed. The suite opens only files it creates under tempfile.

## Scratch files
All under /home/user/sk1_skill_out/:
- tool output: `audit*.txt` and `audit*.json`
- runner and mutant output: `unittest_*.txt`, `m1_*.txt`, `m2_absent.txt`, `m3*_present.txt`
- mutant copies (M1, M2, M3, M3b): `mutants/`
- stand-ins: `shadow_dilithium/`, `shadow_numpy/`
- scripts: `direct_unskipped.py`, `k2b_probe.py`, `make_mutants.py`, `gitignore_approx.py`
- approximate clean checkout: `clean_approx/`
- before/after repo snapshots: `snapshot_{before,after}_{stat,sha}.txt`
- temp files: `tmp/`

## Paths read outside /home/user/skn_sk1_plain (other than the skill file and the tool)
- **Read on purpose outside the two permitted directories:** none.
- **Under /home/user/sk1_skill_out/** (permitted scratch, listed because it is outside the repo):
  - its directory listing
  - the stand-in files, the four scripts and the `.txt` outputs listed above
  - the snapshot files
  - the mutant copies, which I diffed and ran, and `clean_approx/`, where the tool ran
  - `tmp/`
  - The `--json` outputs were written but not read back.
- **Read implicitly by programs I ran (contents not inspected):**
  - /usr/bin/python3 with its standard library and installed packages (pytest, numpy, dilithium_py), plus their package metadata for the version numbers
  - `which`, which searched PATH
  - git, run once in the repo: it looked for a `.git` in /home/user, /home and / and may have read its system or global config
  - `ls -la`, which showed the parent directory's metadata
  - skn_orbital_tui.py, run by the dashboard test and by me: it reads /proc/meminfo, /sys/class/thermal/thermal_zone*/temp and the load average
  - the Bash tool's shell startup profile
- **Harness:** /home/user/principia-artificialis/CLAUDE.md was loaded into my context at session start. I did not open it, and it played no part in the audit.
