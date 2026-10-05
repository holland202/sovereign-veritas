# PV-1 — results: an OPERATOR tag is the sealer's word, not a declaration

**Status:** Draft, self-tested. 6 of 6 as registered; W7 (`--sabotage`) exit 1 as registered. These were
predictions of a gap, so this confirms the gap; it is not a pass.
**Registration:** `docs/PV1_PREREG.md` (`5eaa134`). **Harness:** `tools/pv1_probe.py` (`bb59f20`, pinned at
`0b58503`). **Base:** `main` at `27ce753`.

## What could have gone wrong, first

1. **Self-tested.** Claude (Opus 5.5, Anthropic) wrote the registration, harness and this file. No independent
   party has run it.
2. **Container only.** Python 3.13.16, Linux. NOT VALIDATED on the S25.
3. **W4 restates a published limit.** "A fully consistent rewrite verifies" was already in the package's own
   limitations. W4 is there as the baseline for W6; it is not a new finding on its own.
4. **W2's failing check was narrower than its wording allowed.** The registration accepted
   `limitations_declared` *or* an evidence-state check. Only `evidence_states` failed; the regenerated
   limitation statement passed. The harness tests the registered disjunction.
5. **W3 failed one more check than predicted.** A2 failed `package_digest` (registered) and also
   `limitations_declared`, as the committed feasibility output already showed. The prediction did not
   exclude extra failures.
6. **Throwaway key.** The signed arm uses an ed25519 key created per run, not Chad's key in `keys/`.
7. No deviations from the registration in design, constants or predictions.

## Raw output (`results/pv1/run.txt`)

```
PV-1 | registered run | python 3.13.16
  A0: {"exit": 0, "failed": [], "tags": {"compute_budget": "DEFAULTED", "power_status": "DEFAULTED", "thermal_status": "OPERATOR"}, "verdict": "VERDICT  CONSISTENT  freshness=NOT_PROVEN  authenticity=NOT_PROVEN"}
  A1: {"exit": 0, "failed": [], "tags": {"compute_budget": "OPERATOR", "power_status": "OPERATOR", "thermal_status": "OPERATOR"}, "verdict": "VERDICT  CONSISTENT  freshness=NOT_PROVEN  authenticity=NOT_PROVEN"}
  A2: {"exit": 1, "failed": ["limitations_declared", "package_digest"], "tags": {"compute_budget": "OPERATOR", "power_status": "OPERATOR", "thermal_status": "OPERATOR"}, "verdict": "VERDICT  2 check(s) failed  freshness=NOT_PROVEN  authenticity=NOT_PROVEN"}
  A3: {"exit": 0, "failed": [], "tags": {"compute_budget": "OPERATOR", "power_status": "OPERATOR", "thermal_status": "OPERATOR"}, "verdict": "VERDICT  CONSISTENT  freshness=NOT_PROVEN  authenticity=NOT_PROVEN"}
  A4: {"exit": 1, "failed": ["evidence_states"], "tags": {"compute_budget": "MEASURED", "power_status": "DEFAULTED", "thermal_status": "OPERATOR"}, "verdict": "VERDICT  1 check(s) failed  freshness=NOT_PROVEN  authenticity=NOT_PROVEN"}
  S_A1: {"exit": 0, "failed": [], "tags": {"compute_budget": "OPERATOR", "power_status": "OPERATOR", "thermal_status": "OPERATOR"}, "verdict": "VERDICT  CONSISTENT  freshness=NOT_PROVEN  authenticity=SIGNED:pv1-throwaway@example.invalid"}
  S_A3: {"exit": 0, "failed": [], "tags": {"compute_budget": "OPERATOR", "power_status": "OPERATOR", "thermal_status": "OPERATOR"}, "verdict": "VERDICT  CONSISTENT  freshness=NOT_PROVEN  authenticity=SIGNED:pv1-throwaway@example.invalid"}
  W5: {"decision_equal": true, "gate_inputs_equal": true}
  W6_declarer_paths: []

  W1  HELD
  W2  HELD
  W3  HELD
  W4  HELD
  W5  HELD
  W6  HELD
VERDICT 6 of 6 as registered (W7 is --sabotage; W8 is the door)
DIGEST d45a5437a660af555e40b4de0cc96101d9b26e84605a50616539e654f7958dd9
```

Sabotage (`results/pv1/sabotage.txt`): W4 and W6 REFUTED, `VERDICT 4 of 6`, exit 1. Full suite on the branch:
`481 passed`.

## Predictions

| | prediction | outcome |
|---|---|---|
| W1 | A0, A1 verify CONSISTENT, tags as made | HELD |
| W2 | MEASURED relabel (same rewrite) refused | HELD (`evidence_states`) |
| W3 | tags-only relabel fails `package_digest` | HELD (+ `limitations_declared`) |
| W4 | full relabel to OPERATOR verifies CONSISTENT | HELD |
| W5 | decision and gate inputs unchanged | HELD |
| W6 | signed honest and signed relabelled both SIGNED; no declarer field exists | HELD |
| W7 | `--sabotage` exits 1 | HELD |
| W8 | OPERATOR witness | door, unrun |

## What this shows

- **Implementation claim, supported here:** SV's provenance contract refuses promotion to the states it can
  check (MEASURED; DERIVED without a measured source, per the pre-registration probe), but accepts
  DEFAULTED → OPERATOR. After that rewrite a package verifies CONSISTENT, and, when signed, SIGNED; nothing in
  it distinguishes the relabel from an honest declaration (A1 vs A3).
- **What OPERATOR means today:** "the party that sealed or signed this package says someone supplied this
  value". The package has no field that could name the declarer, so a signature attests the sealer only.
- **Gate impact:** none in this case (W5, finding F1). The harm is to the package's account: a reader is told
  a value was declared when it was the default.
- **For the outside question that prompted this:** the missing piece is a witness, not a transition rule.
  Monadic, typed or state-machine plumbing would leave the result unchanged, because OPERATOR has nothing to
  check.

## What it does not show

- Nothing about an attacker without the signing key; W6 measures the signer's own word, not forgery.
- Nothing about `thermal_status` OPERATOR, ABSENT relabels, or values other than the defaults.
- Nothing on the S25.

## Candidate fix (proposal; format change, Chad's decision)

W8: give OPERATOR a witness — a declarer identity and a signature by that declarer over the field and value,
checked by `verify_package.py` against an allowed-declarers file. Until then, a cheaper option is a fifth
limitation sentence: "OPERATOR records that the sealer reports a declaration; no declarer is identified."
Either breaks pinned package outputs.

## Still open

W8 unrun. The same question applies to any state a sealer can assert without a check (UNVERIFIED, INFERRED if
ever admitted on runtime fields).

## Provenance

AI participation: Claude (Opus 5.5, Anthropic) wrote the registration, harness and this file. Human
validation: Chad Holland directed the work on 2026-10-05 after a summary of the feasibility probe; review was
of summaries, not line by line. Chad is responsible for the final artifact.
