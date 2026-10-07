# Differential testing of four sv.gate/0 implementations (2026-10-07)

Container (Linux x86_64, Python 3.13.16, Go 1.24.7, Rust 1.97). **S25 NOT VALIDATED.** Author session: Claude (Opus 5.5),
self-tested except where a separate agent is named.

## What was compared

| Implementation | Author / independence | Frozen 4690 vectors |
|---|---|---|
| kernel `sovereign_veritas/decision.py` | project author | the vectors are **generated from it** (`gate_contract.py --write`): agreement is a regression pin, not an independent oracle |
| verifier `tools/verify_package.py` `replay_gate` | project author | CONFORMS |
| `ports/go` | project author ("from CONTRACT.md only") | CONFORMS |
| `ports/rust` | a Claude subagent given only CONTRACT.md + vectors (`ports/rust/PROVENANCE.md`); same vendor, separate context | CONFORMS on its **first** run, no fixes; digest reproduced by `gate_contract.py --check-command` |

## Finding 1 — the frozen vectors do not pin parts of the contract

The Rust implementer built 8 deliberately wrong variants of its own Gate: **7 still matched all 4690 vectors**. The
runtime words `high`, `critical`, `unsafe` (thermal) and `low` (compute) appear in no vector; ties-to-even rounding is pinned
by one case. Reproduced in this session on the Python verifier: removing `"high"` from its vocabulary, the frozen vectors
still print `VERDICT  CONFORMS`.

**Decision: IMPLEMENT** `contract/gate_vectors_supplement.jsonl` (`tools/gate_supplement.py`): 53 in-contract cases
(every vocabulary word and near-misses, every status string and near-misses, rounding ties, floors, step counts), each
written only because **all four implementations agree**. Derived oracle (agreement, same vendor), labelled as such; the
frozen file and its digest are unchanged. With the `high` mutant the supplement reports
`MISMATCH S:thermal_status=high verifier ('REFUSE', ['runtime_state_unavailable'])`
(`tests/test_gate_supplement.py` keeps both halves of that check).

## Finding 2 — beyond the vectors, the implementations disagree

`tools/gate_differential.py --cases 3000 --extra ports/rust/dev/probes.jsonl --cmd go=… --cmd rust=…` (seed 20261007):
3022 cases, **6 DISAGREE, 1086 DOMAIN, 1930 agree** (raw: `results/differential/gate_differential_3000.{txt,jsonl}`).

**DISAGREE** (every implementation decided, differently). All six are `ports/go` against the other three, and two are
**fail-open** in Go:

| Input (outside the types the contract lists) | kernel = verifier = rust | go |
|---|---|---|
| `capability.required_evidence = "ab"` (a string) | DEFER `missing_required_evidence:a`, `:b` | **ALLOW** |
| `capability.max_steps = 2.5`, `step_count = 3` | REFUSE `capability_max_steps_exceeded:3>2.5` | **ALLOW** |
| `capability.max_steps = false` | REFUSE `capability_max_steps_exceeded:1>False` | a later rule's REFUSE |

The blind Rust port reproduced the kernel's behaviour on all six; the same-author Go port did not. The kernel's own
behaviour here is Python leaking through (a string iterated as characters; `1>False` in a reason string): fail closed, but
not designed.

**DOMAIN** (at least one implementation raised while another decided): e.g. `record.verification = false`,
`record.action = -1`, `min_evidence_quality = 10**400`. The kernel and verifier raise (fail closed: no decision, no
execution); Go and Rust decide, sometimes **ALLOW** (`action = -1`). Part of this count is the harness adapter
(`gate_contract.kernel_gate` needs every key present), not the Gate.

**Decision: DOCUMENT ONLY for sv.gate/0; EXPERIMENT FIRST for sv.gate/1.** CONTRACT.md does not define these inputs, so no
implementation is "the bug": patching Go until it agrees with Python would be fitting one implementation to another. The
remedy is in the contract: a rule 0, "a member whose type is not the listed type → REFUSE `input_malformed:<path>`",
with vectors for each. That changes decisions (e.g. `action = -1` ALLOW in two ports), so it is a contract version, and it
should be specified, then implemented independently, then compared again.

## Contract ambiguities (from `ports/rust/NOTES.md`, each with the implementer's choice there)

Rule 3 null vs `{}`; non-object values where objects are listed; registry entries `false`/`{}`; non-string `parent`; what
"differs" means in rule 6; non-array `required_evidence`; non-number floor, huge integer floor, `-0.0` printing;
non-integer `max_steps`; "array" vs "collection" in rule 12; parser behaviour (NaN, duplicate keys, lone surrogates, huge
floats); empty status; canonical JSON escapes; malformed lines. And one inconsistency: the contract's "an integer too large
for a double is ±infinity" is not CPython's behaviour (`float(10**400)` raises), so a literal Python port crashes on a
vector-adjacent input.

## What this does and does not establish

Agreement of four implementations on 4690 + 53 cases, one written with a separate context, is evidence that CONTRACT.md is
implementable as written **on those inputs**. It is not independent validation: all four are the project author's or the
same vendor's, and the frozen vectors are the kernel's output. The missing check remains an implementation by an unaffiliated
person, compared on the supplement and on differential cases.
