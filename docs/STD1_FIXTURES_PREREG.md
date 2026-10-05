# STD-1 follow-up: fixtures for two surviving UNKNOWN_KEY checks. Registration

Status: **REGISTERED, nothing built.** Committed before any fixture exists. Target: `opena2a-standards/aap-conformance`
at `f0d1339` (after the maintainer's fix for issue #4), whose generator reproduces its committed fixtures byte for byte
(checked: regenerating on a clean tree changes no file).

Drafted by Claude (Opus 5.5) at Chad Holland's direction. Chad has not reviewed it line by line. The suite and its
verifiers are OpenA2A's (main author Abdel Fane); nothing here implies their review or endorsement.

## Why

STD-1 found 28 reject sites in the Python reference verifier that can be removed with every fixture passing. The suite
has **no fixture with `rejectCategory: UNKNOWN_KEY`**, and both `UNKNOWN_KEY` sites survive removal: line 242 (kid not in
the verifier's key set) and line 246 (kid names a key of a different suite than the header's `alg`).

## Fixtures (built with the suite's own generator and conventions)

- `cgt-compact-unknown-key`: the existing valid compact CGT (kid `broker-key-1`), with a verifier state whose key set
  does not contain `broker-key-1`. Expected `REJECT`, `UNKNOWN_KEY`, reason containing `not in`.
- `cgt-compact-kid-suite-mismatch`: a compact CGT whose header says `alg: EdDSA` with `kid: broker-pqc-1` (an
  ML-DSA-65 key in the verifier's set). Expected `REJECT`, `UNKNOWN_KEY`, reason containing `suite`.

## Predictions

| ID | Prediction |
|---|---|
| F1 | Both reference verifiers (Python and Node), unmodified, pass all 46 fixtures. |
| F2 | The Python verifier with line 242 made a no-op fails `cgt-compact-unknown-key`. |
| F3 | The Python verifier with line 246 made a no-op fails `cgt-compact-kid-suite-mismatch`. |
| F4 | Anti-vacuity: each of those two mutants passes all 44 fixtures at `f0d1339` (the gap exists today). |
| F5 | The suite's own checks that run without network (`schema_validation.py`, `conformance_profile.py`) still pass. |

If a fixture cannot be built as described (for example, an earlier check rejects it for another reason), that is
reported and the fixture is not offered.

## Next unrun test

The act-chain check (line 751) and the other surviving sites, one fixture each, if the maintainer wants them.
