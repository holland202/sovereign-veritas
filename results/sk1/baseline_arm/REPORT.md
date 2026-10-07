# Test-suite audit: /home/user/skn_sk1_plain

## Scope, method, baseline

**Scope.** I covered `tests/run_tests.py` (30 unittest tests) and the gates in `.github/workflows/verify.yml`: the skip guard, the K3–K9 "sabotage must exit 1" steps, and the install check.

**Method.**
- All runs used a copy at `/home/user/sk1_base_out/work/repo`, with HOME and TMPDIR pointed into scratch.
- To simulate a missing dilithium-py, I put a shadow package that raises ImportError ahead of the real one on PYTHONPATH.
- I tested the tests with single-edit mutants under `/home/user/sk1_base_out/mutants/`.
- The repo is unmodified: `diff -rq` against the copy is identical, and nothing in the repo is newer than my first scratch file.

**Environment.** Python 3.13.16, numpy 2.5.3, dilithium-py installed, scipy and matplotlib not installed. The checkout has no `.git` directory.

**Baseline results.**
- All dependencies present: `Ran 30 tests ... OK`.
- dilithium-py blocked: `OK (skipped=4)`, exit 0.

## Findings, most severe first

### 1. HIGH: the fail-closed test is skipped in the one environment where it matters
`test_k2c_fails_closed_without_the_library` (run_tests.py:183-194) belongs to `TestSignedDocking`. That class's `setUp` skips every test when dilithium-py is missing (lines 136-139). But this test simulates the missing library itself (`ccpl.ML_DSA_65 = None`), so it doesn't need the library. PREREG_2026-09-27.md:40 registers K2c as exactly the "not installed" case.

Evidence:
- **Library blocked:** the test is reported `skipped 'dilithium-py not installed'`.
- **Library blocked, skip removed:** the test runs and passes.
- **Fail-open mutant, library blocked:** I changed node.py:294-295 so docking locks and commits with no signature. The stock suite still gives `Ran 30 tests ... OK (skipped=4)`. With the skip removed, the test fails: `AssertionError: Tuples differ: (True, True, 2) != (False, False, 1)`.

The CI skip guard (verify.yml:26) would fail the job in this situation. Local runs, which README:169 instructs, exit 0. README:568 lists "no library, no lock" as tested.

### 2. MEDIUM: the dashboard test drops its docking check without dilithium-py, and can't tell computed values from constants
- Lines 209-211 read `if ccpl.available(): assert 6 x "sig VALID"`. Without the library the test reports "ok", not "skipped", so the CI skip-grep never sees it. Nothing asserts the "fails closed, no locks" line either.
- **Library blocked, mutant dashboard printing six fake `LOCK  sig VALID` lines:** the test passes.
- **Full environment, mutant with `b0, b1 = 1, 1` (skn_orbital_tui.py:74), `good = True` (line 65) and a literal `verify_chain OK` (line 109):** the test passes.
- The vault the test checks belongs to a node created just for the dashboard, with depth 1 or 2, so "verify_chain OK" is trivially true.

### 3. MEDIUM: TestFormationV3 passes the wrong argument and doesn't depend on the controller
- **Wrong argument.** Lines 85 and 89 call `formation_v3(..., 0.05, False)`. The sixth parameter is `slc`, not `verbose` (simulation_v3.py:88-89).
  - At node.py:269-278, `False.inject_labs` raises AttributeError on every node step, which `except Exception` swallows.
  - run_tests.py:6 `logging.disable(CRITICAL)` hides the log message.
  - Measured: 1200 swallowed exceptions in the tetrahedron test and 2400 in the cube test ("'bool' object has no attribute 'inject_labs'"). The verbose banner prints in the test log.
- **Controller doesn't matter.** Final error by mutant (tetrahedron / cube):
  - Shape springs off (line 124): 5.2e-05 / 2.8e-05 m. Passes.
  - `node.step` removed entirely (line 120): 1.1e-04 / 5.4e-05 m. Passes, and the full suite is 30/30 OK.
  - Only removing the direct pose write `pose -= gain*offset` (lines 119-123) fails: 0.456 / 0.426 m.

  So these tests don't verify the "natural-gradient formation control" that README:556-557 credits them with.

### 4. MEDIUM: test_k3_closed_loop_paired_reaches_below doesn't test closed loop
Lines 233-238 assert only `z < -1.0`.

| Mode | Geometry | Final z |
|---|---|---|
| Closed loop | paired | -2.18 |
| Open loop | paired | -2.43 |
| Open loop | legacy | -2.43 |
| Closed loop | legacy | +0.00 |

With a mutant that ignores `closed_loop` (node.py:261 `move = grad`), the full suite is 30/30 OK.

### 5. MEDIUM: test_k1d's "independent reference" isn't independent
- The reference builds its complex with the module's own `rips_complex` (line 125), uses only 2-D clouds (line 124), and 196 of its 200 clouds have b1 = 0.
- This contradicts PREREG_2026-09-27.md:25 ("a reference that builds the complex") and README:566.
- **Triangle-rule mutant** (topology.py:50, triangles need edges < 0.9r): (b0, b1) changes on 103 of the test's own 200 clouds. The test still passes, and so does the full suite (30/30).
- **Edge rule 1.2r, or z ignored:** all five K1 tests pass. Only test_k5 catches these, and it checks b0 only.

### 6. MEDIUM: test_k1e passes with the topology guard disabled
- Lines 130-132 assert only that the guard fired 0 times (`frp_events == 0`). The registered contrast, that the old guard fires, is missing.
- **Mutant with swarm.py:56 `beta_1 = 0`:** 30/30 OK. On a ring with a real hole, stock code reports `beta_1=1`; the mutant reports 0.
- The old-guard mutant does fail (`30 != 0`), so the test tells old from new, but not new from dead.

### 7. MEDIUM: CI "sabotage must exit 1" steps accept any non-zero exit (verify.yml:29-56)
- In this checkout, the K3, K4 and K8 probes exit 2 in both normal and sabotage runs ("COULD NOT LOOK ... git show"). With dilithium-py blocked, K8 and K9 exit 2 in both. Run verbatim, the CI step logic returns 0 (pass).
- A sabotage branch that crashes is also accepted. In a mutant with a typo in the k6 sabotage line, the normal run exits 0 and the sabotage run exits 1 with an AttributeError traceback. The step passes.
- In the current workflow, each normal step runs first, so the exit-2 cases would already fail the job. The crash case is not covered.

### 8. LOW-MEDIUM: the "installs from pyproject.toml alone" check (verify.yml:57-58) proves neither claim
- With skn not installed, the CI command run from the checkout root prints `install ok` and imports `skn` from `.../repo/skn/__init__.py` (`sys.path[0] = ''`).
- `dilithium_py` was already installed by line 20, so importing it says nothing about pyproject.

### 9. LOW: the skip reason is hard-coded
skn/ccpl.py:17-20 swallows any ImportError. With a shadow package where dilithium-py is present but its `ml_dsa` import fails, `import dilithium_py` works, yet the tests are skipped as "dilithium-py not installed".

### 10. LOW: test_het_bounded is unseeded and checks only the upper bound
Lines 14-16. With the upper HET clip removed (node.py:57), the test still passed 6145 of 20000 runs, and the full suite passed 3 of 12 runs.

### 11. LOW: two test_k2b assertions can no longer fail
Lines 161 and 167 call `verify_dock` without a nonce store. Since K8, an untampered record with the right key also returns `(False, 'no nonce store ...')`. Coverage is currently rescued by line 166 (reason string) and test_k8 lines 179-180.

### 12. LOW: test_convergence passes only in open loop, with a thin margin
Line 80. The final distance is 0.4920 against a 0.5 threshold. With actuators in the loop it fails: 0.6912 (legacy), 0.6311 (paired). Open loop is the documented default.

## Checked and sound
- The vault tamper tests: a mutant with `verify_chain` returning True fails 4 tests, and one with `verify_file` returning True fails test_k6.
- test_k5 covers both branches (13 connected clouds, 37 fragmented).
- The ISRU tests.
- The CI skip guard does fail when dilithium-py is missing.
- No test uses scipy or matplotlib; the suite passes here without them.

Logs are in `/home/user/sk1_base_out/logs/`. Harness scripts are in `/home/user/sk1_base_out/` (`mutate.py`, `runtests.py`, `env.sh`, `*_probe.py`).

## Paths read outside /home/user/skn_sk1_plain
- **`/home/user/sk1_base_out/`:** my scratch area (copies, mutants, logs, scripts).
- **Read implicitly by programs I ran (I opened none of these myself):**
  - `/usr/bin/python3` and `/usr/bin/python` (via `which`)
  - `/usr/lib/python3.13/`
  - `/usr/local/lib/python3.13/dist-packages/` (numpy, dilithium_py, pytest; lookups for scipy and matplotlib failed)
  - `/usr/bin/git`, called by the K3, K4 and K8 probes. Repository discovery was stopped at `/home/user/sk1_base_out/work`, the system config was disabled, and HOME pointed into scratch.
  - `/proc/meminfo`, `/proc/loadavg` and `/sys/class/thermal/thermal_zone*/temp`, read by `skn_orbital_tui.py` `device()` during test runs
  - shell utilities in `/usr/bin` and their libraries, plus `/dev/null`
- **Not read:**
  - `/home/user/principia-artificialis/CLAUDE.md` appeared only as context injected by the harness.
  - The tool harness saved one oversized Grep result to `/root/.claude/projects/-home-user/77c30d9b-52c8-5aa8-979f-1cd1655ce439/tool-results/toolu_01PA5XaqqGmvypWnQHaUCFWV.txt`. That is the only write outside `/home/user/sk1_base_out`.
