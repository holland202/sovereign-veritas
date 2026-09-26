# Integration with the author's other repositories

Status: **Registered** (2026-09-26), before any code below was written. Results are appended
under the registration and never edited into it.

Source of the plan: an outside review (AI-written, supplied by the author) recommending this
repository as the integration kernel. It said to pull vocabulary and tests up from
`evidence-ledger`, `eace` and `vacuity_lint.py`, and to keep every other repository separate
("do not create a giant monorepo"). So there is no new combined repository. The other
repositories stay independent; what is taken from them is named here with the commit it came from.

| From | Commit | What is taken | Where it lands |
|---|---|---|---|
| [eace](https://github.com/holland202/eace) | `1991750` (`mutation_check.py`) | Switch off each verifier guard in turn; the tests must fail | `tools/verifier_mutants.py` |
| [evidence-ledger](https://github.com/holland202/evidence-ledger) | `ccf9144` (`SPEC.md` section 2) | Evidence-state vocabulary; no implicit promotion | `resource_state.evidence_states`, verifier check `evidence_states` |
| [vacuity_lint.py](https://github.com/holland202/vacuity_lint.py) | `68355bb` | Static scan for verification code with no fail path | CI job `vacuity-lint` |

Not taken: EACE's 37-case corpus is built for EACE's own verifier and its inputs; the method
ports, the corpus does not. The review's other suggestions (veritas-eval-harness, edge-ai-primitives,
veritas-science, the sentinel repositories) are not started here.

## Finding before any code (F1)

`tools/make_package.py` never sets `compute_budget` or `power_status`. Every package it makes,
including all three in `evidence/`, carries the `RuntimeState` defaults `available` and `stable`,
and the Gate counts them as healthy:

```
5bfc70dfcfa2 {'thermal_status': 'normal', 'compute_budget': 'available', 'power_status': 'stable'} {'thermal_status_source': 'declared'}
118a02b75646 {'thermal_status': 'normal', 'compute_budget': 'available', 'power_status': 'stable'} {'thermal_policy': 's25-uncalibrated-v0', 'thermal_status_source': 'measured'}
45c6ad182584 {'thermal_status': 'hot', 'compute_budget': 'available', 'power_status': 'stable'} {'thermal_policy': 's25-uncalibrated-v0', 'thermal_status_source': 'measured'}
```

The packages say runtime fields are "declared by the caller", and the measured-thermal statement
added earlier today says "compute_budget and power_status declared by the caller". Neither is
accurate: nobody declared them. In evidence-ledger's terms they are `DEFAULTED`, and a `DEFAULTED`
value supporting ALLOW is the implicit promotion its SPEC forbids.

What this step does: new packages tag every runtime field with its evidence state, so a package
says in machine-readable form that these two are defaults, and the verifier holds the tags honest.
What it does not do: change the Gate (making `DEFAULTED` inputs block ALLOW changes the Gate's
contract and its 4608-case digest), or change `make_package.py`'s defaults while an outside
reproduction of the current quick start is in progress. Both are the next decision, not taken here.

## Registered predictions

**I1 — verifier guard mutants** (method from EACE `mutation_check.py`). Each guard is switched off
where its result enters the verdict (forced to PASS), in a copy of the repository, and the test
files that load the verifier are run against the copy.

- **M0** The null mutant (the same rewrite, naming no guard) passes those tests: the tool can
  report SURVIVED, so KILLED means something.
- **M1** Every guard is KILLED: switching off any one of the 21 (22 once I2 adds one) makes at least
  one of those tests fail. A SURVIVED guard is a finding: recorded here, given a test, re-run.
- **M2** The tool never touches the working tree; it mutates a copy.

**I2 — evidence states** (vocabulary from evidence-ledger `SPEC.md` section 2).

- **E1** `make_package.py` tags: `--thermal-status normal` -> `thermal_status` OPERATOR,
  `compute_budget` DEFAULTED, `power_status` DEFAULTED; `--thermal-status measured` -> DERIVED; no
  flag -> ABSENT, and the Gate REFUSEs; new flags `--compute-budget` / `--power-status` -> OPERATOR.
  Every such package verifies, with an `evidence_states` PASS line.
- **E2** Laundering, after evidence-ledger's `adversarial/evidence_state_laundering.py`, each
  resealed (every digest recomputed): `compute_budget` DEFAULTED -> MEASURED; a declared thermal
  status OPERATOR -> DERIVED; a measured one DERIVED -> OPERATOR; ABSENT carrying a healthy value
  (with the matching ALLOW); DEFAULTED carrying a value other than the default (with the matching
  decision). Each fails `evidence_states`.
- **E3** The fourth limitation line is generated from the tags. Changing the tags without the line,
  or the line without the tags, fails `limitations_declared`.
- **E4** Packages without tags (the three published, the test fixture) verify exactly as before;
  the fixture sweep stays 119 rewrites, 44 verified unsigned, 0 signed.
- **E5** Stated limit: an unsigned rewrite that deletes the tags and restores the old line verifies.
  Only the signature closes that.

**I3 — vacuity_lint in CI.**

- **L0** Its `--selftest` passes on the CI runner, and a planted file with no fail path makes the
  scan exit 1 (the gate can fire).
- **L1** The scan of this repository: findings are not predicted. Each is triaged here (fixed, or
  marked intentional with the reason the tool requires), and CI gates on the scan only after that.

## Results

### I1 — verifier guard mutants (container x86_64, Python 3.11.15)

First run, as registered: test files naming `verify_package`, 21 guards.

```
verifier_mutants | 21 guards | tests: tests/test_package.py tests/test_package_recovery.py tests/test_published_evidence.py tests/test_signature.py tests/test_thermal_policy.py tests/test_witness.py
  (null mutant)                      SURVIVED  72 passed, 1 skipped in 7.95s
  artifact_digest                    SURVIVED  72 passed, 1 skipped in 8.20s
  provenance_chain                   SURVIVED  72 passed, 1 skipped in 7.61s
VERDICT  19 of 21 KILLED, 2 SURVIVED  (84 s)
exit=1
```

(The other 19 lines read KILLED.) **M0 confirmed; M1 refuted; M2 confirmed** (`git diff` on the
verifier empty afterwards, no temporary copies left).

- **The two survivors were test gaps, not dead guards.** Each stops an attack nothing else stops,
  checked by listing the failing guards for each attack:
  - `artifact_digest`: swap in different artifact bytes, keep the claimed sha256, recompute the
    measurement from the new bytes, reseal. Only `artifact_digest` fails. Without it, a package
    could carry bytes other than the ones its decision record names, and everything else would agree.
  - `provenance_chain`: edit a record and recompute only the package digest; or give two records the
    same id and reseal fully. Only `provenance_chain` fails, in both.
  All three are now tests in `tests/test_verifier_guards.py`.
- **The tool had a gap of its own:** selecting test files by the name `verify_package` skipped
  `test_field_sweep.py`, which loads the verifier through `tools/field_sweep.py`. It now runs every
  test file.

Re-run after both changes:

```
verifier_mutants | 21 guards | 29 test files
  (null mutant)                      SURVIVED  225 passed, 1 skipped in 14.88s
  artifact_digest                    KILLED    tests/test_verifier_guards.py::test_artifact_bytes_swapped_under_the_old_digest
  capability_named_in_record         KILLED    tests/test_field_sweep.py::test_unbound_fields_are_exactly_the_pinned_set
  decision_record_is_artifact        KILLED    tests/test_field_sweep.py::test_unbound_fields_are_exactly_the_pinned_set
  decision_record_matches            KILLED    tests/test_field_sweep.py::test_unbound_fields_are_exactly_the_pinned_set
  execution_only_if_allowed          KILLED    tests/test_package.py::test_execution_recorded_only_under_allow
  freshness_not_overclaimed          KILLED    tests/test_field_sweep.py::test_unbound_fields_are_exactly_the_pinned_set
  gate_replay                        KILLED    tests/test_field_sweep.py::test_unbound_fields_are_exactly_the_pinned_set
  limitations_declared               KILLED    tests/test_field_sweep.py::test_unbound_fields_are_exactly_the_pinned_set
  measurement_in_chain               KILLED    tests/test_field_sweep.py::test_unbound_fields_are_exactly_the_pinned_set
  measurement_names_artifact         KILLED    tests/test_field_sweep.py::test_unbound_fields_are_exactly_the_pinned_set
  measurement_recomputed             KILLED    tests/test_field_sweep.py::test_unbound_fields_are_exactly_the_pinned_set
  package_digest                     KILLED    tests/test_package_recovery.py::test_r2_no_single_bit_flip_is_accepted
  provenance_chain                   KILLED    tests/test_verifier_guards.py::test_record_edited_and_only_the_package_digest_recomputed
  schema                             KILLED    tests/test_field_sweep.py::test_unbound_fields_are_exactly_the_pinned_set
  thermal                            KILLED    tests/test_field_sweep.py::test_unbound_fields_are_exactly_the_pinned_set
  thermal_before                     KILLED    tests/test_package.py::test_thermal_before_is_checked
  thermal_status_derived             KILLED    tests/test_thermal_policy.py::test_t3_status_rewritten_to_normal_with_matching_allow_fails
  verifier_identity_not_overclaimed  KILLED    tests/test_field_sweep.py::test_unbound_fields_are_exactly_the_pinned_set
  verifier_provenance                KILLED    tests/test_field_sweep.py::test_unbound_fields_are_exactly_the_pinned_set
  freshness_witness                  KILLED    tests/test_witness.py::test_w1_earlier_entry_becomes_stale
  signature                          KILLED    tests/test_signature.py::test_s2_wrong_key_identity_namespace_or_package_fails
VERDICT  21 of 21 KILLED, 0 SURVIVED  (128 s)
exit=0
```

The 1 skip is `test_committed_log_path_is_not_git_ignored`, which needs a `.git` directory the copy
does not have. Twelve guards are killed first by the same test, the pinned fixture sweep: one
broad test standing behind many guards. That is coverage, but thin; a guard that only that sweep
protects is one careless re-pin away from inert.
