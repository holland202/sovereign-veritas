# PV-1 — Is an OPERATOR tag evidence that anyone declared the value? Registration

**Status:** REGISTRATION. Committed before `tools/pv1_probe.py` exists. Nothing built or run at this
commit except the feasibility counts below.
**Date:** 2026-10-05. **Base:** `main` at `27ce753`.
**Direction:** Chad Holland, 2026-10-05, after reading a summary of the feasibility probe below.

## Where the question came from

Chad brought in outside research notes (prepared with another AI system) asking whether monadic or typed
"provenance contracts" could stop a DEFAULTED value from being silently strengthened to MEASURED. SV already
has such a contract: `sovereign_veritas/evidence_states.py` (`problems()`), re-implemented in
`tools/verify_package.py`. A quick probe of `problems()` (not committed) showed it refuses DEFAULTED → MEASURED
and DEFAULTED → DERIVED without a measured source, but accepts DEFAULTED → OPERATOR for the same value. PV-1
asks what that acceptance means for a package.

## Question

In an `sv.package/0`, is an `OPERATOR` evidence state evidence of a declaration by anyone, or only the word of
whoever sealed (and, if signed, signed) the package?

## What the code can express (read before registering)

- `tools/make_package.py` tags `compute_budget` / `power_status` `OPERATOR` exactly when the CLI flag is
  passed, `DEFAULTED` otherwise. Passing the default value explicitly (`--compute-budget available`) yields
  `OPERATOR` with the same value.
- `problems()` / `evidence_state_problems()` check: state allowed for the field; ABSENT carries no usable
  value; DEFAULTED carries the default; DERIVED iff thermal source is `measured`. Nothing constrains OPERATOR
  beyond being in the allowed set.
- The Gate does not read evidence states (finding F1, `docs/INTEGRATION.md`).
- `package_sha256` is `sha256(canonical_json(package minus package_sha256))`; anyone can recompute it.
  "authenticity: none - no signature; a fully consistent rewrite verifies" is already a published limit.
- A signature (`ssh-keygen`, namespace `sv-package`) covers the whole package file and names one signer.
  No package field names who declared a runtime value.

## Feasibility (run before registering, unmutated `main`, container)

```
decision ALLOW []
evidence thermal_status=OPERATOR compute_budget=DEFAULTED power_status=DEFAULTED
decision ALLOW []
evidence thermal_status=OPERATOR compute_budget=OPERATOR power_status=OPERATOR
== relabel_tags_only
FAIL  package_digest
FAIL  limitations_declared               the four statements, resource state from its evidence states
VERDICT  2 check(s) failed  freshness=NOT_PROVEN  authenticity=NOT_PROVEN
== relabel_full   (tags + regenerated resource statement + recomputed package_sha256)
VERDICT  CONSISTENT  freshness=NOT_PROVEN  authenticity=NOT_PROVEN
verify exit 0
relabelled decision ALLOW | honest-OPERATOR decision ALLOW
gate_inputs equal: True
```

## Design

All arms use the real `make_package.py` and `verify_package.py` as subprocesses, `--rounds 10
--thermal-status normal`. Packages are written to a temporary `HOME`. The checkout is never edited.

- **A0 control:** package with `compute_budget`, `power_status` DEFAULTED.
- **A1 honest OPERATOR:** same, with `--compute-budget available --power-status stable`.
- **A2 tags-only relabel:** A0 with both tags set to OPERATOR, nothing else changed.
- **A3 full relabel:** A2 plus the resource limitation statement regenerated from the new tags and
  `package_sha256` recomputed.
- **A4 MEASURED relabel (anti-vacuity):** A0 with `compute_budget` set to MEASURED, statement regenerated,
  digest recomputed — the same rewrite skill as A3, aimed at a state the contract refuses.
- **S signed:** a throwaway ed25519 key made in the temporary directory; A1 and A3 both signed by it, both
  verified with `--signature/--allowed-signers/--identity`.
- **Simplest rival:** "the verifier already catches promotion." A4 vs A3 tests it.

## Predictions

- **W1 (control).** A0 and A1 verify `CONSISTENT`, exit 0; their tags are as made.
- **W2 (anti-vacuity).** A4 exits 1 and its failing checks include `limitations_declared` or an
  evidence-state check. The contract can refuse a relabel produced by the same rewrite as A3.
- **W3.** A2 exits 1 with `package_digest` failing.
- **W4.** A3 exits 0 with `VERDICT  CONSISTENT`, tags reading OPERATOR. (This is an instance of the published
  "fully consistent rewrite verifies" limit; it is registered so the signed arm has a baseline.)
- **W5 (decision unaffected, F1).** A3's `decision` and `gate_inputs` equal A0's.
- **W6 (signed).** A1 and A3 both verify with authenticity `SIGNED`, exit 0. No key path in either package
  contains `declar`, `operator_id` or `declared_by`. A signature therefore attests who sealed the package,
  and the package has no field that could attest who declared an OPERATOR value.
- **W7 (`--sabotage`).** The harness skips the relabel in A3 (leaves DEFAULTED). W4's "tags read OPERATOR"
  and W6's A3 tag condition are then REFUTED and the harness exits 1.
- **W8 (door, unrun).** A witness for OPERATOR: a declarer identity plus a signature over that field,
  checked by `verify_package.py`, so that a sealer cannot turn DEFAULTED into OPERATOR without a declarer's
  key. A format change, so Chad's decision.

## What the predictions mean if they hold

W2 + W4 + W6 holding means: SV's provenance contract blocks promotion to states it can check (MEASURED,
DERIVED) but OPERATOR is unwitnessed. A DEFAULTED value relabelled OPERATOR is indistinguishable, even
signed, from an honest declaration; the package tells a reader "someone declared this" when nobody did. W5
holding means it changes the package's account, not the Gate's decision. These are predictions of a gap;
"n of n as registered" would be a confirmed gap, not a pass. Type-level or monadic structure would not
change any of this: the missing thing is a witness, not a transition rule.

## Limits

- Self-tested: Claude (Opus 5.5, Anthropic) writes the registration and harness.
- Container only. NOT VALIDATED on the S25.
- The rewrite is done by a party able to recompute the digest (any reader, unsigned) or holding the
  signing key (signed). An attacker without the key cannot produce a SIGNED A3; W6 is about what the
  signer's own word is worth, not about forgery.
- Only `compute_budget` and `power_status`. `thermal_status` OPERATOR follows the same rule but is not
  separately tested.

## Provenance

Question prompted by research notes Chad Holland supplied; the notes are not reproduced here. Registration
by Claude (Opus 5.5, Anthropic); direction by Chad Holland, review of a summary only, no line review before
this commit.
