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
