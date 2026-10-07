# Supply chain: inventory, scanners shown able to fire, SAST triage (2026-10-07)

Container (Linux x86_64, Python 3.13.16). Scanners: pip-audit 2.10.1 and bandit 1.9.4, installed in a scratch virtualenv
outside the repository; they are not project dependencies. Claude-assisted (Claude Opus 5.5), **self-tested**: the same model
chose the scanners, planted the defects and triaged the findings. Raw outputs: `results/supply_chain/`. Not registered in
advance. This is an audit, and every number below is quoted from those files.

## What is weak (first)

1. **Every CI action is pinned by a movable tag, never by commit SHA.** One of them is third-party:
   `uraimo/run-on-arch-action@v3` in `xplat.yml`. A moved tag runs new code in CI with the workflow's token. Not fixed:
   the commit SHAs live in repositories outside this session's scope. **DOCUMENT ONLY here; pinning to full SHAs is the
   owner's change.**
2. **Test and CI dependencies are unpinned.** CI installs `pytest>=7`, and `pymavlink` with no version at all. Today's
   resolution has no known vulnerabilities, but a later run installs whatever is newest.
3. **`pip-audit -r` with `--no-deps` refuses unpinned requirements and exits 1 without auditing anything**
   (`pip_audit_actual.txt`: `ERROR ... requirement pytest is not pinned to an exact version`). A CI step that treats exit 1
   as "vulnerable" would fail for the wrong reason, and one that ignores the exit code would hide real findings. The
   resolved audit (`pip_audit_actual_resolved.txt`): `No known vulnerabilities found` (2026-10-07T03:17Z).
4. **Not done here:**
   - secret scanning (no scanner was available in this container);
   - an SBOM in a standard format (CycloneDX or SPDX);
   - signed releases (there is no release key: see the trust-root gap in `docs/KL1_RE1_RESULTS.md`);
   - reproducible builds.
5. **`vacuity_lint` is pinned by a 7-character commit prefix (`68355bb`), not a full SHA.**

## Inventory

| Component | Third-party dependencies | Pinning |
|---|---|---|
| `sovereign_veritas/` (kernel) | none; `dependencies = []` | — |
| `tools/verify_package.py`, `tools/consumer.py` | none; stdlib only, and nothing imported from the kernel | — |
| tests | pytest | `>=7`, unpinned |
| CI red-team job | pytest, pymavlink | unpinned |
| CI: GitHub actions | `actions/checkout@v4` ×7 and `@v5` ×6, `actions/setup-python@v5` ×7 and `@v6` ×5, `actions/upload-artifact@v4` ×2, `actions/download-artifact@v4` ×1, `actions/setup-go@v5` ×1, `uraimo/run-on-arch-action@v3` ×1 | tags |
| CI: `vacuity_lint` | cloned from GitHub | commit `68355bb` |
| `ports/go` | none (`go.mod`: module and `go 1.21` only) | — |
| `ports/rust` | none (`Cargo.lock`: 1 package, itself) | lock file |
| signatures | the system's `ssh-keygen` (OpenSSH), found on `PATH` | whatever is installed; a hostile `PATH` is outside the threat model |

`tests/test_supply_chain.py` pins the first two rows:
- the kernel imports only the standard library and itself;
- the verifier and the consumer import only the standard library;
- `dependencies = []`;
- the import check can fire (a planted `import requests` is flagged).

## Can the scanners fire? (anti-vacuity)

| Scanner | Planted input (`results/supply_chain/planted/`) | Result |
|---|---|---|
| pip-audit | `requests==2.19.0`, `urllib3==1.24.1` | exit 1, many advisories, e.g. `urllib3 1.24.1 PYSEC-2023-207 1.24.2` (`pip_audit_planted.txt`) |
| bandit | `subprocess.call(cmd, shell=True)`, `pickle.loads`, `hashlib.md5`, a hardcoded password | exit 1. B602 High, B324 High, B301 Medium, B403 Low, B105 Low (`bandit_planted.txt`) |

## bandit over `sovereign_veritas/` and `tools/` (`bandit_repo.txt`): 7 high, 9 medium, 140 low

Every high and medium finding was read in the code. Each is a claim to verify, not an order.

| Finding | Where | Verdict | Action |
|---|---|---|---|
| B324 MD5, High | `sovereign_veritas/package.py:166`, the package file name `sv_package_<md5[:12]>.json` | **real, low risk.** `write_package` overwrites with `os.replace`, so two colliding packages written to one directory would share a name. Crash atomicity, which is what the docstring claims, does not depend on MD5, and a package's identity is `package_sha256` | DOCUMENT ONLY: a file name is not an identity. A chosen-prefix collision needs control of both packages' content |
| B324 MD5, High ×6 | `tools/make_package.py:166`, `model_action.py:339`, `vehicle_action.py:465`, `thermal_probe.py:112`, `gate_constraint.py:347`, `recovery_admissibility.py:208` | false positive in context: printed or recorded fingerprints, not a control | none. Changing them would break recorded reproduction outputs |
| B102 `exec`, Medium | `tools/gate_contract.py:270` | false positive in context: it compiles AST mutants of the repository's own `replay_gate` | none |
| B306 `mktemp`, Medium | `tools/gpu4_probs.py:131` (selftest) | **real, minor**: another local user could create the name first | **fixed**: `mkstemp`; selftest output byte-identical before and after |
| B310 `urlopen`, Medium ×7 | `gpu2_probe.py`, `gpu4_probs.py`, `model_action.py`, `nvidia_challenge.py` | low: operator-supplied URLs of local model servers | none |
| B101 `assert`, Low | `sovereign_veritas/planner.py:125` | **real, minor**: `python -O` strips the check that a capability still exists after preflight | **fixed**: an explicit `ValueError`. `test_a_capability_removed_after_preflight_is_refused_without_assert` fails on the old code (AssertionError) |
| B110, B603, B607, B404, B311, B105/B106, Low | many | `except: pass` sites are commented fail-closed or best-effort counting; subprocess calls take argument lists with no shell; `random` is used in fuzzers and simulations, not for secrets; the "passwords" are words like `PASS` and attempt tokens | none |

## Decisions

| Item | Class |
|---|---|
| `mkstemp` in the probe selftest; an explicit check instead of `assert` in the planner | IMPLEMENT (done) |
| Pin GitHub actions, the third-party one first, to full commit SHAs | DOCUMENT ONLY here (outside this session's repository scope); recommended to the owner |
| Pin test and CI dependencies with hashes (pip-compile), then run `pip-audit` on the lock in CI | EXPERIMENT FIRST: decide whether CI should fail on new advisories or report them |
| Secret scanning, a standard-format SBOM, signed releases | NOT TESTED |
