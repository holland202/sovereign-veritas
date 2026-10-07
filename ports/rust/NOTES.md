# rust_gate: a blind re-implementation of `sv.gate/0`, with notes

Implementer: Claude (Opus 5.5, Claude Code subagent), 2026-10-07. I worked only from `CONTRACT.md`
and `gate_vectors.jsonl` in this directory. I did not open the original code or any other
directory, and I did not search the web.

## Result (measured)

| | |
|---|---|
| Vectors file sha256 | `4534d15d348e54a29897677234fd3c8b28984fd836ea855dff2fafc4377edf68` (matches CONTRACT.md) |
| Vectors matched | **4690 of 4690** (decision and reasons, order included) |
| Conformance digest (computed by rust_gate's own SHA-256) | `44823d0ff707213ae8bc310ed8b21e135f8e742fd8834e8f9474743d3a250628` |
| Same digest computed independently (CPython `hashlib` in `dev/compare.py`) | `44823d0ff707213ae8bc310ed8b21e135f8e742fd8834e8f9474743d3a250628` |
| Digest stated in CONTRACT.md | `44823d0ff707213ae8bc310ed8b21e135f8e742fd8834e8f9474743d3a250628` (equal) |

How to run it:

```
cd /home/user/blind_gate/rust_gate && cargo build --release --offline
./target/release/rust_gate [--digest] < cases.jsonl > decisions.jsonl
```

`--digest` also prints `cases N` and `conformance_digest <hex>` to stderr. The program uses no
crates; the JSON parser, the Python-compatible formatting and SHA-256 are all hand-written
(`src/json.rs`, `src/pyfmt.rs`, `src/sha256.rs`, with the rules in `src/gate.rs`). It never reads the
vectors file, and it does not special-case ids. A malformed input line makes it exit 2 instead of
guessing a decision.

## (b) Fix log

| Iteration | Change | Vectors matched |
|---|---|---|
| 0 (first run after writing from the contract) | none | **4690 / 4690** |

No fixes were needed, so I did no tuning against the golden answers. The record has to include what
I saw of the expected outputs before that first run:

- My first command was `head -c 1500 gate_vectors.jsonl`, to see the shape of the input. It showed the
  `expect` of the first vector in full (`ALLOW`, `[]`) and of the second in part (`REFUSE`,
  `action_not_permitted_by_policy`). Before the first run I saw no other expected outputs.
- After that run I surveyed which input types appear in the vectors, using the vectors as data
  (see section (d)). That survey changed no code.
- The first run piped the vectors through a CPython re-serialization of `{"id","input"}`, which
  changes how numbers are written. So I also fed the raw vector lines in unchanged (the program
  ignores the extra `expect` member). That also gave 4690 / 4690 and the same digest.

I used CPython 3.13, installed on this machine, as a reference for *Python's own* formatting, not
for the Gate. `dev/fmt_fuzz.py` compares rust_gate's `repr(float)` and `format(x, ".4f")` output
with CPython's on 16,976 random and tie-case doubles: **0 mismatches**.

## (a) Ambiguities and underspecification, with my choices

Each item quotes the contract, says what it leaves open, and gives my choice. "Unpinned" means a
different choice still passes all 4690 vectors: I either built that alternative as a mutant and ran
it (section (d)), or the vectors never contain that input.

1. **Rule 3, null versus "present".** The text says "`capability` is null -> REFUSE
   `capability_missing`", and the contract defines "Present" as truthy. It does not say whether
   `capability: {}` counts as missing (truthiness) or falls through to rule 4.
   *Choice:* only null or absent counts as missing, so `{}` gives `capability_not_authorized`.
   **Unpinned** (mutant M-b passes 4690/4690).
2. **Non-object values where the Input table promises an object or null.** This covers `record`,
   `record.verification`, `record.action`, `record.metadata`, `capability`, `capability_registry`,
   registry entries, `runtime` and `policy`. The contract says nothing about a string or an array in
   these places. A Python `.get` on one would crash.
   *Choice:* a non-object reads as `{}`, except in these cases:
   - a non-object `verification` gives NOT_VERIFIED;
   - a non-object `runtime` gives `runtime_state_unavailable`;
   - a non-object registry has no entries;
   - a non-null, non-object registry entry is "not authorized".

   The vectors never contain these inputs.
3. **Rule 5, falsy registry entries.** The text says "the registry has no entry for it, or the entry
   is null -> `capability_parent_missing`". It does not say what happens to an entry of `false` or
   `{}`.
   *Choice:* following "is null" literally, they give `capability_parent_not_authorized:<parent>`.
   **Unpinned** (mutant M-d, which treats `false` as missing, gives byte-identical output).
4. **Rule 5, a non-string `parent`** (for example `1`). The contract does not cover the registry
   lookup or how `<parent>` is printed.
   *Choice:* a non-string parent never matches a key, and it prints as Python `str()` (`1`,
   `True`, `[1, 2]`). The vectors only contain string or null parents.
5. **Rule 6, "differs".** *Choice:* Python `!=` with Python numeric equality, the same as rule 13.
   A missing `capability.name` reads as null.
6. **Rule 9, a `required_evidence` that is not "array of strings".** *Choice:* Python iteration
   semantics.
   - A string iterates its characters.
   - An object iterates its keys.
   - Null, a missing member, a number or a bool means no requirements.
   - A non-string element never matches a metadata key, and prints as Python `str()`.

   **Unpinned** (mutant M-h passes). Every vector has an array of strings.
7. **Rule 10, a floor that is not a number or null.** The table says "`min_evidence_quality` (number
   or null)". Rule 10 defines "number" for *q* but not for the floor.
   *Choice:* a bool floor counts as 0 or 1 (Python bool is an int); a string, array or object floor
   skips the rule.
   **Unpinned** (mutant M-c, which uses floor 0.0 instead, passes). Every vector has a float floor.
8. **Rule 10, a floor that is an integer too large for a double.** The ±infinity rule is stated
   for *q* only. *Choice:* the floor becomes ±inf and prints as `inf`. CPython's `format(10**400,
   ".4f")` would raise `OverflowError` here. Not in the vectors.
9. **Rule 10, `-0.0`.** It is not mentioned, but it lies inside [0, 1]. *Choice:* it prints as Python
   does, `-0.0000`. **Unpinned** (mutant M-f, which drops the sign, passes).
10. **Rule 11, a `max_steps` that is not an integer.** The table says "integer or null", and the
    Formatting section only covers integers.
    *Choice:* Python comparison and `str()`.
    - A float compares exactly: `3>2.5`.
    - A bool counts as 0 or 1 and prints `True`.
    - A string, array or object skips the comparison.

    **Unpinned** (mutant M-g passes). Every vector has an integer.
11. **Rule 11, large `step_count`.** The contract does not say how big an integer can be.
    *Choice:* arbitrary-precision comparison and printing, as Python does. `-0` is an integer equal
    to 0, so it is below 1.
12. **Rule 12, "is not an array"**, while the reason string says `allow_only_must_be_a_collection`.
    JSON can produce only one collection type, so this makes no observable difference. A non-object
    `policy` reads as `{}` (item 2).
13. **The JSON layer.** The contract quotes Python's behaviour but never says which JSON parser to
    use. My choices follow CPython's `json.loads`:
    - It accepts `NaN`, `Infinity` and `-Infinity`. The contract says standard JSON cannot carry
      them, but Python's parser accepts them.
    - The last duplicate key wins.
    - `1e2` is a float, because the contract defines an integer as having "no fraction or exponent".
    - A float literal too large for a double, such as `1e400`, becomes ±inf. The contract states the
      ±inf rule only for integers.
    - A lone UTF-16 surrogate becomes U+FFFD. This is a deliberate deviation, because a Rust string
      cannot hold one.
14. **Rule 2, an empty-string `status`.** It is unclear whether `""` means "no status"
    (NOT_VERIFIED) or UNKNOWN. Both lead to `verification_not_passed`, so no output depends on it.
15. **Rule 7's "vocabulary"** I read as the union of the Healthy and Degraded columns. Anything else
    gives `runtime_state_unavailable`. That includes a missing field, null, a non-string, and wrong
    case.
16. **Canonical JSON for the digest.** The contract says "no escaping of non-ASCII" but not how to
    escape control characters or how to write a non-string `id`.
    *Choice:* CPython `json.dumps` conventions (`\n`, `\u001f`, and so on). The vectors' ids are
    plain strings.
17. **The I/O protocol.** The contract does not say how to handle blank lines or malformed lines.
    *Choice:* skip blank lines; a malformed line is fatal (exit 2). `id` is echoed back as the parsed
    value.
18. **Python `repr` of strings** is only needed for a non-string `parent` or evidence name that
    contains strings (item 4 and item 6). It is approximated: Unicode `isprintable` is replaced by
    "a C0 or C1 control character is not printable". The vectors do not use it.

## (c) Final

**4690 / 4690. Digest `44823d0ff707213ae8bc310ed8b21e135f8e742fd8834e8f9474743d3a250628`**, equal
to the contract's digest. I measured this both from rust_gate's own SHA-256 and from CPython hashlib.

## (d) Inconsistencies, and what the vectors do not pin

- **Nothing had to be learned from the vectors.** The text alone was enough to reproduce all 4690
  results on the first run. The three formatting traps the Formatting section warns about (repr
  exponent form, ties-to-even `.4f`, Python equality in `in`) were the ones that needed care. The
  contract states each of them explicitly.
- **The contract says "Every rule ... is pinned", which is true per rule but not per stated
  behaviour.** I built mutants of my own implementation and ran each one on all 4690 vectors:

  | Mutant | Matched |
  |---|---|
  | M-a: drop thermal `high`, `critical`, `unsafe` and compute `low` from the vocabulary | 4690 |
  | M-b: rule 3 by truthiness | 4690 |
  | M-c: non-numeric floor gives 0.0 | 4690 |
  | M-d: a `false` registry entry counts as missing | 4690 (byte-identical) |
  | M-e: `.4f` ties away from zero (`toFixed`-like) | **4689** (exactly one vector pins it) |
  | M-f: `-0.0` printed unsigned | 4690 |
  | M-g: non-integer `max_steps` skips the comparison | 4690 |
  | M-h: string `required_evidence` gives no requirements | 4690 |

  M-a is the notable one. The contract's own vocabulary table lists `high`, `critical` and `unsafe`
  for `thermal_status` and `low` for `compute_budget`, and none of those four strings appears in any
  vector. An implementation that refused them as unavailable would still print CONFORMS. The
  ties-to-even rule rests on a single vector, `X:quality=0.03125`.
- **It partly frames itself as Python but departs from CPython in one place.** The contract says
  "Present means present and truthy in Python's sense", and describes equality and repr the same
  way. But rule 10's "An integer too large for a double is +infinity or -infinity" is not what
  CPython's `float(int)` does: that raises `OverflowError`. So the original must convert some other
  way. An implementer who simply "does what Python does" would crash on vector
  `X:quality=10**400`. The contract does state the rule, so I followed it, and the vector agrees.
- **The vocabulary is mixed: "present" (truthy), "is null", "exists and is not null".** Each use is
  explicit, but rule 3 ("is null") sits next to a contract-wide definition of "present". The
  difference is observable (item 1) and unpinned.
- **The Input table says `record.evidence_quality` is "number or null", but rule 10 handles a string
  there**, and two vectors contain one. So the Input table describes typical inputs; it does not
  constrain which inputs are valid. This affects how far an implementer can rely on the table for
  items 2, 6, 7 and 10.
- **The reason name says "collection" while the rule text says "array"** (item 12). This makes no
  observable difference in JSON.

### Outputs for unpinned inputs (for comparison with the original)

`dev/probes.jsonl` holds 22 cases that the vectors do not cover, each built from the first vector
with one change. `dev/probes_out.jsonl` holds rust_gate's answers to them. Examples:

| Input change | rust_gate output |
|---|---|
| `capability={}` | REFUSE `capability_not_authorized` |
| `parent=1` | REFUSE `capability_parent_missing:1` |
| `required_evidence="ab"` | DEFER `missing_required_evidence:a`, `missing_required_evidence:b` |
| floor `true` | DEFER `evidence_quality_below_threshold:0.9000<1.0000` |
| floor `10**400` | DEFER `evidence_quality_below_threshold:0.9000<inf` |
| `max_steps=2.5`, `step_count=3` | REFUSE `capability_max_steps_exceeded:3>2.5` |
| `max_steps=true`, `step_count=2` | REFUSE `capability_max_steps_exceeded:2>True` |
| `max_steps="3"` | ALLOW |
| `step_count=10**30` | REFUSE `capability_max_steps_exceeded:1000000000000000000000000000000>3` |
| `evidence_quality=-0.0` | DEFER `evidence_quality_below_threshold:-0.0000<0.5000` |

If the original Gate is run on these cases, any disagreement is a place where the contract is
underspecified. These cases would make good additions to the vectors.

## Files

- `rust_gate/`: the cargo project, with no dependencies. It builds with `cargo build --release
  --offline`.
- `dev/compare.py`: the development harness. It feeds the vectors without `expect`, compares the
  answers and computes the digest independently.
- `dev/fmt_fuzz.py`: checks number formatting against CPython.
- `dev/probes.jsonl`, `dev/probes_out.jsonl`: the inputs the vectors do not cover, and rust_gate's
  answers.
