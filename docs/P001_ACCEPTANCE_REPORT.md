# P-001 acceptance report (implementation milestone, not close-out)

```yaml
report: p001/acceptance-report-001
by: Claude (Opus 5.5), the implementer. This is self-tested evidence, not independent validation.
frozen_contract: coordination/p001/ACCEPTANCE.md @ 1c16e661d8a2db44bbc60a589b2348bfd8ccc936
frozen_sha256: dc54e8c1051ee32b7c03f12b4b97a4b39399ec1aef8c7fec01f9fe1e73b4d28d
code_commit: 5bec876853012c8dea5762dbd87540e1f8149c24   # branch p001/build-w1-w2, PR #66; base main 709da9e
independent_review: PENDING (Chad Holland, owner)
aggregate: NOT GREEN. W1/W2/A08 rows PASS; C01-C05, C07 and C08 are NOT_RUN (close-out, owner decisions)
```

Chad Holland directed this work (2026-10-09) and has not yet reviewed it. ChatGPT gave an advisory source-level review on #66 and did not run the code. Every row below was produced by the command shown, at `code_commit`.

## How to reproduce (any machine with Python 3.10+ and OpenSSH `ssh-keygen`)

```
git clone https://github.com/holland202/sovereign-veritas && cd sovereign-veritas
git checkout 5bec876853012c8dea5762dbd87540e1f8149c24
python -m pip install -e ".[test]"
python -m pytest -q -rA tests/test_p001_w1.py tests/test_p001_w2.py     # A01-A08, B01-B08
python tools/p001_mutants.py                                            # C06
python tools/gate_contract.py --check kernel && python tools/gate_contract.py --check verifier   # B05
python -m pytest -q                                                     # whole suite (regression)
```

Container run of those commands at `code_commit` (Linux x86_64, Python 3.13, OpenSSH):
- P-001 tests: `60 passed`.
- Whole suite: `540 passed, 1 skipped`. The skip is the pymavlink-dependent test.
- Mutants: `BASELINE PASS 60 passed`, then `M-sig-skip KILLED`, `M-self-digest KILLED`, `M-refuse-all KILLED`, `VERDICT 3 of 3 mutants killed`.

GitHub CI: the checks for [5bec876](https://github.com/holland202/sovereign-veritas/commit/5bec876853012c8dea5762dbd87540e1f8149c24/checks).
- Matrix: ubuntu x86/arm, macOS and Windows on Python 3.10/3.12/3.14.
- The `tests` job runs the P-001 tests and prints the B08 transcript.
- The `red-team` job runs `tools/p001_mutants.py` and `tools/verifier_mutants.py`. The latter must kill every verifier guard, including the new `contract_binding` and `schema` guards.

## Rows

| Row | Status | Test(s) in `tests/test_p001_*.py` | Observed (container) |
|---|---|---|---|
| A01 | PASS | `test_a01_signed_bound_v1_is_accepted_once_then_replay_refused` | exit 0, `ACCEPTED authenticity=SIGNED:chad contract=BOUND:sv.gate/0`; state = one digest + expected anchor; replay exit 1, bytes unchanged |
| A02 | PASS | `test_a02_every_incomplete_invocation_is_a_usage_error` (8 cases), `test_a02_complete_but_unreadable_material_is_could_not_look` | each omission (and `--signature` alone): exit 2, `usage:` on stderr, no traceback, no REFUSED/ACCEPTED, state bytes identical or still absent |
| A03 | PASS | `test_a03_invalid_signatures_are_refused_and_the_positive_control_still_passes` | altered byte, altered signature, wrong identity, unknown key, wrong namespace: exit 1, `FAIL signature`, state unchanged; correct key then exit 0 |
| A04 | PASS | `test_a04_missing_ssh_keygen_is_could_not_look` | PATH without ssh-keygen: exit 2 `COULD NOT LOOK ... ssh-keygen`; same call with the real PATH: exit 0 |
| A05 | PASS | `test_a05_a_valid_signature_overrides_nothing_else` | not latest, forged decision validly signed, replay, rollback: exit 1, state unchanged; a distinct latest package: exit 0, state advances |
| A06 | PASS | `test_a06_no_unsigned_escape_hatch` | `--allow-unsigned` and bypass env vars: exit 2 usage; `verify_package.py` on unsigned: exit 0 `authenticity=NOT_PROVEN`, never SIGNED/ACCEPTED |
| A07 | PASS | `test_a07_trust_material_failures_fail_closed` | absent/unreadable/empty signature or allowed-signers: exit 2 COULD NOT LOOK; malformed allowed-signers, identity not trusted: exit 1; state unchanged |
| A08 | PASS | `test_a08_interrupted_write_leaves_previous_state_then_retry_succeeds` (4), `..._temp_file_is_written_in_the_state_files_directory`, `..._documentation_does_not_claim_power_loss_durability` | injected failure in serialization and just before `os.replace`, existing state and first use: exit 2, previous bytes or absence kept, temp removed; retry exit 0, valid JSON. No power-loss claim |
| B01 | PASS | `test_b01_*` (3) | v1 with exactly `{id, conformance_digest}`; both inside the body digest and covered by the signature; `TRUSTED_CONTRACTS` local and equal to the kernel's |
| B02 | PASS | `test_b02_closed_schema_fails_closed` (10), `test_b02_duplicate_keys_and_nonfinite_numbers_fail_closed` (2), `test_b02_added_an_unknown_schema_...` | every listed malformation fails; duplicate key and NaN: exit 2 COULD NOT LOOK |
| B03 | PASS | `test_b03_contract_substitution_...` (3) | wrong digest / unrelated id / `sv.gate/1`, resealed and validly signed: `PASS package_digest`, `PASS signature`, `FAIL contract_binding` naming the field; consumer refuses |
| B04 | PASS | `test_b04_*` (3) | trusted pair: full verifier exit 0 `CONTRACT BOUND:sv.gate/0`; trusted digest = recomputed from 4,690 shipped vectors; self-attestation fails |
| B05 | PASS | `test_b05_gate_decisions_unchanged_on_all_4690_vectors` (kernel, verifier), `test_b05_all_defaulted_allow_limitation_is_unchanged` | both CONFORM, digest `44823d0f...0628`; PR-1's PR5 (all-DEFAULTED ALLOW) still HELD, so W3 is unchanged |
| B06 | PASS | `test_b06_*` (4) | 55 archived files byte-identical to the manifest committed before any code change (4a2c36f); the set of v0 JSON files is unchanged; signed legacy `SIGNED:holland202` + `LEGACY_UNBOUND`; unsigned legacy `NOT_PROVEN` + `LEGACY_UNBOUND` |
| B07 | PASS | `test_b07_*` (3) | historically valid signed + witnessed v0: `PASS signature`, `PASS freshness_witness`, `FAIL schema_v1_only`, refused, no state; v0 without `--legacy` fails; a v0 with a pasted-in binding fails `schema_closed` |
| B08 | PASS on platforms with ssh-keygen | `test_b08_*` (2) | the documented commands run end to end; CI prints the transcript. A runner without ssh-keygen reports `B08 NOT_TESTED` |
| C01 | NOT_RUN | — | final STATUS and release notes are close-out work |
| C02 | NOT_RUN | — | dispositions of the six PRs need owner authorization |
| C03 | NOT_RUN | — | #34/#62 overlap, #61 raw-evidence label: close-out |
| C04 | NOT_RUN | — | dated inventory to be taken at release |
| C05 | NOT_RUN | — | scout keep/disable: owner choice |
| C06 | PASS (mutants, CI on Linux) | `tools/p001_mutants.py` | 3 of 3 killed; the regression suites pass on the CI matrix |
| C07 | NOT_RUN | — | release: owner |
| C08 | NOT_RUN | — | close-out completeness: owner |

Additive tests, which are not frozen cases (from ChatGPT's review probe 2): `test_add_malformed_nested_v1_with_a_valid_signature_...` (4) and `test_add_malformed_v1_without_ssh_keygen_...`. A malformed nested v1 package with a valid signature is never accepted, never prints a traceback and never changes state.

## What changed outside the frozen cases (failures and side effects first)

- **The verifier VERDICT line is unchanged.** Contract status is printed on its own `CONTRACT ...` line. An earlier commit (4989379) put it inside the VERDICT line, and that changed EO-1's registered E4 digest (CI red on `eo1`). It was moved, and EO-1 again reproduces its recorded digest `26dd247f...`.
- **`tools/verifier_mutants.py` found the `schema` guard SURVIVED** at 4989379, because every unknown-schema case was also caught by another check. An additive test was added, and CI now reports 28 of 28 KILLED.
- **JG-2 P7** recorded "signatures are opt-in"; W1 closes that gap. The probe now checks the fixed behaviour by default, and `--pre-w1` keeps the original expectation. Both are in an addendum to `docs/JG2_RESULTS.md`, and the original record is not edited.
- **`tools/ietf_map.py` (not in CI) now gives 12 of 14 as registered, against 14 of 14 at base.**
  - M5 changed from DIFFERS to CONFORMS, because W1 now requires the signature.
  - M13 changed from BEYOND to NOT BEYOND, because the hardened consumer refuses the v0 corpus that the probe uses.
  - Replay protection itself is shown on v1 in A01 and A05.
  - The probe is **not** edited. It is recorded here as a changed outcome.
- **Registered probes kept byte-identical to base 709da9e by inspecting their archived v0 corpus with `--legacy`:**
  - DK: digest `d775ead0...`.
  - nonfinite_probe: output identical.
  - attack_harness: P0–P15 all HELD.
- **Every other probe in every workflow** has the same exit code and tail output as base 709da9e. That was compared in the container, one run each.
- **Existing tests changed:** `test_consumer.py` now uses signed v1 packages with the same three intents. Tests that read archived v0 use `legacy=True`. The field-sweep count went from 119 to 121.
- **`tools/witness.py append`** now refuses v0, so only bound v1 packages are witnessed.

## Known limits (not fixed here; see `docs/P001_SIGNED_WORKFLOW.md`)
- Concurrent consumers sharing a state file are not serialised (a lost update is possible). Not tested.
- First use has no anchor.
- Signed is not true and not fresh.
- W3 (all-DEFAULTED gets ALLOW) and PV-1 are unchanged.
- No S25/Termux run.
- No independent replication.
- **NOT PRODUCTION-READY / NOT INDEPENDENTLY SECURITY-VALIDATED.**
