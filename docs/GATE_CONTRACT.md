# Gate contract — registration and results

Status: **Registered** (2026-09-26), before any code below was written. Results are appended
under the registration and never edited into it.

Purpose: let someone other than the author build the Gate, in any language, and show it decides
exactly as this one does. The author supplied a specification written by Grok that puts this
first ("freeze the mathematical rules of G and the package invariants into CONTRACT.md",
"the existing 4608-case lattice must produce an identical digest on every port").

**The contract is taken from the code, not from that specification.** Its rule order (section 1.3)
matches `sovereign_veritas/decision.py`. Three parts of it do not match this repository and are not
used: the package layout in its section 2.2 (sv.package/0 has different fields), its evidence-state
list in section 2.3 (evidence-ledger's own vocabulary, adopted in docs/INTEGRATION.md, differs), and
"only MEASURED evidence satisfies required-evidence checks", which would change the Gate.

## Findings before any code

Read in `decision.py` and `evidence.py`, then run through both implementations (the kernel Gate,
and `replay_gate` in `tools/verify_package.py`). The two agree on every case below. They share
Python's number handling, so neither can catch these for the other.

```
quality=True         kernel=('ALLOW', ())  verifier=('ALLOW', ())
quality=False        kernel=('DEFER', ('evidence_quality_below_threshold:0.0000<0.5000',))  verifier=('DEFER', ('evidence_quality_below_threshold:0.0000<0.5000',))
quality='0.9'        kernel=('ALLOW', ())  verifier=('ALLOW', ())
quality=' 0.9 '      kernel=('ALLOW', ())  verifier=('ALLOW', ())
quality='1_0'        kernel=('DEFER', ('evidence_quality_invalid:10.0',))  verifier=('DEFER', ('evidence_quality_invalid:10.0',))
quality='nan'        kernel=('DEFER', ('evidence_quality_invalid:nan',))  verifier=('DEFER', ('evidence_quality_invalid:nan',))
quality='Infinity'   kernel=('DEFER', ('evidence_quality_invalid:inf',))  verifier=('DEFER', ('evidence_quality_invalid:inf',))
quality=1            kernel=('ALLOW', ())  verifier=('ALLOW', ())
quality=0.49999      kernel=('DEFER', ('evidence_quality_below_threshold:0.5000<0.5000',))  verifier=('DEFER', ('evidence_quality_below_threshold:0.5000<0.5000',))
quality=0.5          kernel=('ALLOW', ())  verifier=('ALLOW', ())
```

(capability floor 0.5; quality in `metadata.evidence_quality`; everything else healthy)

- **F2** A boolean quality passes a quality floor: `true` reads as 1.0. The Gate's rule everywhere
  else is identity, not truthiness (`authorized` must be the boolean `true`, evidence must be `true`).
- **F3** Quality strings go through Python's `float()`: `" 0.9 "` is 0.9, `"1_0"` is 10.0,
  `"Infinity"` is infinite. No other language parses these the same way. A non-numeric string in
  the record's top-level `evidence_quality` field makes the kernel Gate raise instead of decide.
- **F4** The below-threshold reason rounds to four places: 0.49999 is refused correctly, but the
  reason reads `0.5000<0.5000`. Ties round half-to-even on the exact binary value: 0.03125 prints
  `0.0312` in Python and `0.0313` with JavaScript's `toFixed(4)`; 2.0 prints `2.0` in Python and
  `2` in JavaScript. A port that formats the obvious way will disagree.

## Change registered (Q1), in both implementations

Quality is read only from a JSON number that is not a boolean: the record's `evidence_quality`
first, then `metadata.evidence_quality`. Anything else counts as not supplied (0.0). This fixes F2,
removes F3's dependence on Python's parser, and makes reading quality total.

- **Q1a** It only tightens. No input moves toward ALLOW: `true` and numeric strings move from ALLOW
  to DEFER; a top-level string moves from an exception to DEFER.
- **Q1b** The 4608-case digest stays `ab816905b1faf69aeaf24119b207cf7b80fcebd2ffcddac80d3edfa5e4da2d65`
  (the lattice uses 0.9 and 0.2, and the single case `"high"` already read as 0.0), so the S25's
  cross-platform result stands without a re-run.
- **Q1c** The three published packages still verify (none has a quality floor), and every existing
  test passes.

F4 is not changed. Fixing the text would change the lattice digest measured on the S25; the
contract pins the text and its formatting instead.

## Contract predictions

- **C1** Vectors: the 4608 lattice cases of `tools/gate_constraint.py`, its single cases that
  standard JSON can carry (non-finite floats cannot be written; those are excluded and listed), and
  cases pinning F2-F4 (`true`, `"0.9"`, 0.49999, 0.03125, 2.0, a top-level string). The kernel and
  the verifier agree on every vector, decision and reasons exactly. A disagreement is a finding and
  blocks freezing.
- **C2** The vector file is frozen: regenerating it from the kernel reproduces it byte for byte. Its
  sha256, and a conformance digest over the expected outputs, are written in CONTRACT.md.
- **C3** Every rule is pinned: switching off any single rule of the verifier's Gate (each REFUSE
  return and each DEFER reason) makes at least one vector fail. The null mutant passes all.
- **C4** The language-neutral protocol works: a program that reads one case per line on stdin and
  writes one decision per line passes if it wraps a correct Gate; fails with a count if it is wrong
  (always ALLOW); and is reported as could-not-run (exit 2), never as passing, if it crashes or
  prints something that is not a decision.
- **C5** The kernel's conformance digest over the vectors is identical on all 9 CI jobs. The S25 run
  is left for the next phone command.

Stated limits: the vectors cover chosen cases, not every input. `evidence_required` is not part of
the contract (packages do not record it). Two implementations by one author agreeing is still one
author; the contract exists so that someone else can be the second.

## Results (container x86_64, Python 3.11.15)

### Q1 — quality read only from numbers

The same cases as the findings, after the change, in both implementations:

```
quality='True'         kernel=('DEFER', ('evidence_quality_below_threshold:0.0000<0.5000',))  verifier=('DEFER', ('evidence_quality_below_threshold:0.0000<0.5000',))
quality='0.9'          kernel=('DEFER', ('evidence_quality_below_threshold:0.0000<0.5000',))  verifier=('DEFER', ('evidence_quality_below_threshold:0.0000<0.5000',))
quality=' 0.9 '        kernel=('DEFER', ('evidence_quality_below_threshold:0.0000<0.5000',))  verifier=('DEFER', ('evidence_quality_below_threshold:0.0000<0.5000',))
quality='1'            kernel=('ALLOW', ())  verifier=('ALLOW', ())
quality=±10**400 kernel=('DEFER', ('evidence_quality_invalid:inf',))  verifier=('DEFER', ('evidence_quality_invalid:inf',))
quality=±10**400 kernel=('DEFER', ('evidence_quality_invalid:-inf',))  verifier=('DEFER', ('evidence_quality_invalid:-inf',))
top-level 'high' with metadata 0.9: kernel ('DEFER', ('evidence_quality_below_threshold:0.0000<0.5000',))  verifier ('DEFER', ('evidence_quality_below_threshold:0.0000<0.5000',))
```

(`quality='1'` is the integer 1; the label printed `str()`.)

- **Q1a confirmed.** Old and new quality readers over every pair of 23 values (top level x metadata,
  including booleans, numeric and non-numeric strings, lists, objects, NaN, infinities, 10**400):
  `529 (top-level, metadata) pairs; 212 changed; moved toward ALLOW: 0`.
- **Q1b confirmed.** `DIGEST    ab816905b1faf69aeaf24119b207cf7b80fcebd2ffcddac80d3edfa5e4da2d65`,
  unchanged.
- **Q1c confirmed.** 242 passed; the three published packages verify, `SIGNED:holland202`.
- **A bug in the change itself, caught by a pinned case:** the first version returned
  `math.copysign(math.inf, value)` for integers too large for a double, and `copysign` converts its
  argument to a double, so it overflowed exactly as the code it replaced. The 10**400 case failed
  in both implementations; both now return the infinity directly.

### C1-C4

```
wrote contract/gate_vectors.jsonl: 4690 vectors, 5030381 bytes
file sha256        4534d15d348e54a29897677234fd3c8b28984fd836ea855dff2fafc4377edf68
conformance digest 44823d0ff707213ae8bc310ed8b21e135f8e742fd8834e8f9474743d3a250628
excluded (not standard JSON): S:quality=nan, S:quality=inf
```

- **C1 confirmed.** 4608 lattice cases, 62 of the 64 single cases (the NaN and infinity ones cannot be
  written as JSON), and 20 pinned cases. The kernel and the verifier agree on all 4690; `--write`
  refuses to write if they disagree anywhere. Every lattice and single case also matches
  `gate_constraint.py`'s own evaluation of it.
- **Found while writing CONTRACT.md:** the first vector set pinned 10 extra cases, and the contract
  text named more porting traps than that: `0` as a missing digest, `1` and `"true"` for `true`,
  `2.0` as a non-integer (which JavaScript's `JSON.parse` cannot tell from `2`), Python equality in
  the allow-list, exponent layout in reasons, a null registry entry. A port could have broken any of
  them and still passed. Ten more cases pin them; 4690 in all.
- **C2 confirmed.** Regenerating reproduces the file byte for byte (`test_c1_c2_...`), and
  CONTRACT.md's sha256, conformance digest and count are checked against the file by a test.
- **Found by `tools/verifier_mutants.py`:** `.gitignore` ignores `*.jsonl`, so git would have left
  the vectors out of the commit without a word. The mutant tool copies tracked files, its null mutant
  failed the contract tests in the copy, and it refused to run. Same defect class as the witness log
  on 2026-09-26 (hidden by `*.log`). Fixed the same way: an exception in `.gitignore`, a test, and
  `--write` refuses a git-ignored path. Removing the exception fails the test and makes `--write`
  exit 1.
- **C3 refuted for one rule, which no input can reach:**

```
gate_contract mutants | 23 rules in replay_gate | 4690 vectors
  (null mutant)                                                            passes
  if not rec.get("input_digest"):                                          KILLED by 2307
  if status in REFUSE_STATUS:                                              KILLED by 1
  if status == "INSUFFICIENT_EVIDENCE":                                    KILLED by 769
  if cap is None:                                                          KILLED by 1
  if cap.get("authorized") is not True:                                    KILLED by 773
  if parent:                                                               KILLED by 389
  if action.get("capability") and action.get("capability") != cap.get("n   KILLED by 193
  if not runtime_available(runtime):                                       KILLED by 77
  if not runtime_healthy(runtime):                                         KILLED by 28
  if floor is not None:                                                    KILLED by 29
  if max_steps is not None:                                                KILLED by 70
  if allow is not None and not isinstance(allow, list):                    KILLED by 1
  if requested and allow is not None and requested not in allow:           KILLED by 33
  elif status != "PASS":                                                   EQUIVALENT (unreachable)
  if registry is None:                                                     KILLED by 1
  if pcap is None:                                                         KILLED by 2
  if pcap.get("authorized") is not True:                                   KILLED by 386
  if meta.get(name) is not True:                                           KILLED by 21
  if not (math.isfinite(q) and 0.0 <= q <= 1.0):                           KILLED by 5
  if steps is not None:                                                    KILLED by 70
  elif q < floor:                                                          KILLED by 24
  if isinstance(steps, bool) or not isinstance(steps, int) or steps < 1:   KILLED by 5
  elif steps > max_steps:                                                  KILLED by 65
VERDICT  22 of 23 rules pinned by the vectors, 1 listed as unreachable, 0 SURVIVED
exit=0
```

  `elif status != "PASS":` survives because every status except `PASS` and `INSUFFICIENT_EVIDENCE` is
  refused by the rule before it; it guards statuses added later. That is the blind spot vacuity_lint
  documents (a fail path that exists but cannot fire). It is listed with its reason in
  `gate_contract.py`, and the tool fails if a listed rule ever becomes reachable. Several rules are
  pinned by a single vector each (a missing capability, a missing registry, a non-list allow-list,
  REFUTED's distinct reason): pinned, but thinly.
- **C4 confirmed.**

```
== a correct program (wraps the verifier's Gate)
gate_contract sv.gate/0 | python3 tools/gate_contract.py --serve verifier | 4690 vectors
conformance digest 44823d0ff707213ae8bc310ed8b21e135f8e742fd8834e8f9474743d3a250628  (expected 44823d0ff707213ae8bc310ed8b21e135f8e742fd8834e8f9474743d3a250628)
VERDICT  CONFORMS
exit=0
== always ALLOW
gate_contract sv.gate/0 | python3 /tmp/claude-0/-home-claude-sovereign-veritas/f7690649-cc21-5164-b21d-dbfc016c2d26/scratchpad/always_allow.py | 4690 vectors
  MISMATCH L00000000001: expected REFUSE ['action_not_permitted_by_policy'], got ALLOW []
  MISMATCH L00000000010: expected REFUSE ['capability_max_steps_exceeded:5>3'], got ALLOW []
VERDICT  4675 of 4690 vectors differ
exit=1
== crashes
COULD NOT RUN: python3 /tmp/claude-0/-home-claude-sovereign-veritas/f7690649-cc21-5164-b21d-dbfc016c2d26/scratchpad/crash.py: exit 3, 0 lines for 4690 cases
exit=2
```

  (15 vectors expect ALLOW; the always-ALLOW program gets the other 4675 wrong.) Output that is not
  JSON, one line short, or answering the wrong case id are also `COULD NOT RUN`, exit 2 (tests).

After all of the above: 261 passed; `tools/verifier_mutants.py` 22 of 22 guards killed across 31
test files; vacuity_lint 0 findings.
