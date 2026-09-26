# The Gate contract — `sv.gate/0`

What the Sovereign Veritas Gate decides, precisely enough for someone else to build it in any
language and prove it decides the same way. The rules below are taken from the code
(`sovereign_veritas/decision.py`), and 4690 test vectors hold the code to them.

**Status: self-tested.** Two implementations exist, the kernel Gate and `replay_gate` in
`tools/verify_package.py`, and both pass every vector. Both are by the same author, so agreeing
proves less than it sounds. No outside implementation exists yet. Registration and results:
`docs/GATE_CONTRACT.md`.

## Test your implementation

Write a program, in any language, that reads one case per line on stdin and writes one line per
case, in the same order:

```
in:  {"id": "L00000000000", "input": {...}}
out: {"id": "L00000000000", "decision": "ALLOW", "reasons": []}
```

Then run the checker (Python 3.10+, standard library only):

```
python tools/gate_contract.py --check-command <your program and its arguments>
```

It lists up to ten mismatches and ends with the conformance digest and
`VERDICT  CONFORMS` or `VERDICT  N of 4690 vectors differ`. A program that crashes, prints
something that is not a decision, or answers the wrong case is reported `COULD NOT RUN` (exit 2),
never as passing. A conforming implementation prints this digest:

| | |
|---|---|
| Vectors | `contract/gate_vectors.jsonl`, 4690 vectors |
| File sha256 | `4534d15d348e54a29897677234fd3c8b28984fd836ea855dff2fafc4377edf68` |
| Conformance digest | `44823d0ff707213ae8bc310ed8b21e135f8e742fd8834e8f9474743d3a250628` |

The conformance digest is sha256 over canonical JSON of `[[id, decision, reasons], ...]` in vector
order. Canonical JSON here means: keys sorted, separators `,` and `:` with no spaces, UTF-8, no
escaping of non-ASCII characters.

## Input

A JSON object with five members. Packages store more fields; the Gate reads only these, and an
implementation must ignore any others.

| Member | Type | Read |
|---|---|---|
| `record` | object | `input_digest`, `verification` (object or null), `action` (object or null), `metadata` (object), `evidence_quality` (number or null) |
| `capability` | object or null | `name`, `authorized`, `required_evidence` (array of strings), `parent`, `min_evidence_quality` (number or null), `max_steps` (integer or null) |
| `capability_registry` | object or null | name -> capability object (or null: not registered) |
| `runtime` | object | `thermal_status`, `compute_budget`, `power_status` |
| `policy` | object or null | `allow_only` |

## Output

`decision` is `ALLOW`, `DEFER` or `REFUSE`. `reasons` is an array of strings, and its order is part
of the contract.

## Rules

Apply in this order. A REFUSE returns at once, with exactly one reason, and discards any DEFER
reasons collected so far. A DEFER reason is appended and evaluation continues. When all rules have
run, the result is DEFER with the collected reasons if there are any, otherwise ALLOW with none.

"Present" means present and truthy in Python's sense: `null`, `false`, `0`, `0.0`, `""`, `[]` and
`{}` are not present; every other value is.

1. `record.input_digest` not present -> **REFUSE** `evidence_invalid:missing_input_digest`
2. Verification status: `NOT_VERIFIED` if `record.verification` is null or has no `status` (or
   `status` is null). Otherwise the status is its value if that is exactly one of the strings
   `PASS`, `FAIL`, `REFUTED`, `INSUFFICIENT_EVIDENCE`, `NOT_VERIFIED`, `UNKNOWN` (case-sensitive;
   `"pass"`, `"PASS "` and `true` are not), and `UNKNOWN` otherwise. Then:
   - `FAIL`, `NOT_VERIFIED`, `UNKNOWN` -> **REFUSE** `verification_not_passed`
   - `REFUTED` -> **REFUSE** `verification_refuted`
   - `INSUFFICIENT_EVIDENCE` -> DEFER reason `verification_insufficient_evidence`
   - (Anything other than `PASS` left here -> **REFUSE** `verification_not_passed`. No input
     reaches this line today; it guards statuses added later.)
3. `capability` is null -> **REFUSE** `capability_missing`
4. `capability.authorized` is not the boolean `true` -> **REFUSE** `capability_not_authorized`
   (`"true"`, `1` and `"false"` are not `true`)
5. If `capability.parent` is present:
   - `capability_registry` is null -> **REFUSE** `capability_parent_requires_registry`
   - the registry has no entry for it, or the entry is null -> **REFUSE** `capability_parent_missing:<parent>`
   - the entry's `authorized` is not the boolean `true` -> **REFUSE** `capability_parent_not_authorized:<parent>`

   One level only: the parent's own parent is not checked.
6. `record.action.capability` is present and differs from `capability.name` -> **REFUSE**
   `action_capability_mismatch` (a null `action` counts as `{}`)
7. Runtime available: each of the three fields must be a string in its vocabulary, exactly
   (case-sensitive). Otherwise -> **REFUSE** `runtime_state_unavailable`.

   | Field | Healthy | Degraded |
   |---|---|---|
   | `thermal_status` | `normal`, `cool` | `warning`, `high`, `hot`, `critical`, `unsafe` |
   | `compute_budget` | `available`, `constrained`, `low` | `exhausted` |
   | `power_status` | `stable` | `unsafe` |
8. Any field degraded -> DEFER reason `runtime_not_healthy`
9. For each name in `capability.required_evidence`, in order: `record.metadata[name]` is not the
   boolean `true` -> DEFER reason `missing_required_evidence:<name>`
10. If `capability.min_evidence_quality` is not null, read quality *q*:
    - if `record.evidence_quality` is not null: its value if it is a number, else 0.0 (it does
      not fall through to metadata);
    - else `record.metadata.evidence_quality` if it is a number, else 0.0.

    A number is a JSON number; `true`, `false` and strings such as `"0.9"` are not numbers. An
    integer too large for a double is +infinity or -infinity. Then:
    - *q* not finite, or outside [0, 1] -> DEFER reason `evidence_quality_invalid:<q>` (`<q>` as
      in Formatting, below)
    - else *q* below the floor -> DEFER reason
      `evidence_quality_below_threshold:<q, 4 places><<floor, 4 places>`, e.g.
      `evidence_quality_below_threshold:0.2000<0.5000`
11. If `capability.max_steps` is not null and `record.metadata.step_count` exists and is not null
    (`0` counts; the truthy "present" does not apply here):
    - `step_count` is a boolean, not an integer, or below 1 -> DEFER reason
      `invalid_step_count_metadata`
    - else `step_count` greater than `max_steps` -> **REFUSE**
      `capability_max_steps_exceeded:<step_count>><max_steps>`

    An integer is a JSON number written without a fraction or exponent: `3` is, `3.0` is not.
12. `policy.allow_only` (a null `policy` counts as `{}`) exists, is not null, and is not an array
    -> **REFUSE** `policy_invalid:allow_only_must_be_a_collection`
13. `record.action.requested` is present, `allow_only` is not null, and `requested` is not an
    element of it -> **REFUSE** `action_not_permitted_by_policy`

## Formatting — where ports go wrong

The reason strings embed Python's number formatting, and the vectors pin it:

- `<q>` in `evidence_quality_invalid` is Python's `repr` of a double: the shortest decimal that
  reads back to the same double, a whole number keeps `.0` (`2.0`, not `2`), exponent form when the
  exponent is below -4 or at least 16 (`1e-05`, `1e+16`), and `inf`, `-inf`, `nan`.
- The four-place values in `evidence_quality_below_threshold` are fixed-point with exactly four
  decimals, rounded correctly from the exact binary value with ties to even: 0.03125 is `0.0312`
  (JavaScript's `toFixed(4)` gives `0.0313`), and 0.49999 is `0.5000`, so a correct refusal can
  read `0.5000<0.5000`.
- The integers in `capability_max_steps_exceeded` are plain decimal.
- `in`/equality in rule 13 is Python's, which treats `1`, `1.0` and `true` as equal.

## What the vectors cover

- The 4608-case lattice of `tools/gate_constraint.py` (11 inputs, each healthy or faulty), whose
  decisions have the same digest on the S25, Linux, macOS and Windows.
- Its single-fault cases that standard JSON can carry (62 of 64; `NaN` and `Infinity` cannot be
  written, so `S:quality=nan` and `S:quality=inf` are left out).
- 20 cases (`X:` ids) pinning how quality is read and printed, and each porting trap named in
  this document: truthiness, `1` and `"true"` for `true`, `2.0` as a non-integer, Python
  equality, a null registry entry.

Every rule above except the unreachable line in rule 2 is pinned: switching off any one of them
in the verifier's Gate changes at least one expected result
(`python tools/gate_contract.py --mutants`). Passing the vectors shows agreement on these 4690
cases, not on every possible input.

## Not in the contract

- `evidence_required`, a third output of the kernel Gate. Packages do not record it and nothing
  verifies it.
- Package checks. `tools/verify_package.py` also checks a package's digests, provenance chain,
  measurement, thermal records, evidence states, limitations, signature and witness. Of those,
  only `gate_replay`, which applies these rules to a package's recorded inputs, is frozen by this
  contract. The rest are documented in `docs/EVIDENCE_PACKAGE.md` and not yet pinned by vectors.
- Hardening the formatting (F4 in `docs/GATE_CONTRACT.md`). It would change the 4608-case digest
  measured on the S25, so it waits for a contract version `sv.gate/1`.
