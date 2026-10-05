# STD-1 follow-up results: two UNKNOWN_KEY fixtures for aap-conformance (5 of 5 as registered, one with a caveat)

Registration: [`STD1_FIXTURES_PREREG.md`](STD1_FIXTURES_PREREG.md), committed at `bf553c3` before the fixtures existed.
Target `opena2a-standards/aap-conformance` at `f0d1339`. The change is a commit in a local clone (`ebc567c`), kept here as
[`results/std1/fixtures_unknown_key/0001-pin-unknown-key.patch`](../results/std1/fixtures_unknown_key/0001-pin-unknown-key.patch).
**Not yet offered upstream.** Linux container only.

Drafted by Claude (Opus 5.5), which also built the fixtures and judged the results, at Chad Holland's direction. Chad
has not reviewed it line by line. The suite is OpenA2A's (main author Abdel Fane); nothing here implies their review.

## What to know first

- **The mutants are caught by crashing, not by a wrong verdict.** With line 242 removed, the next line looks up the
  missing key and raises `KeyError`; with line 246 removed, verification under the wrong suite raises
  `AttributeError`. The verifier's run then exits 1, so the suite does catch both, as F2 and F3 predicted. But in the
  Python verifier these checks are partly protected by the code after them. The fixtures matter most for an
  independent implementation where a missing or mismatched key does not raise (for example, one that falls back to
  another key). This is stated in the patch's commit message.
- **The spec references are this project's choice** (§9.3, §9.2, §9.5, §8.2); the maintainer may prefer others.

## Outcome

| ID | Prediction | Result |
|---|---|---|
| F1 | both reference verifiers pass all 46 | **HELD**: Python 46/46, Node 46/46 |
| F2 | line-242 mutant fails `cgt-compact-unknown-key` | **HELD, by crash**: `KeyError: 'broker-key-1'`, exit 1 |
| F3 | line-246 mutant fails `cgt-compact-kid-suite-mismatch` | **HELD, by crash**: `AttributeError: 'NoneType' object has no attribute 'verify'`, exit 1 |
| F4 | each mutant passes all 44 at `f0d1339` | **HELD**: 44/44 each |
| F5 | `schema_validation.py` and `conformance_profile.py --check` pass | **HELD** |

## Output (verbatim lines; the labels on the left are added)

```
F1  python   PASS  fixtures/cgt-compact-kid-suite-mismatch.json  [cgt]
F1  python   PASS  fixtures/cgt-compact-unknown-key.json  [cgt]
F1  python   summary: 46 pass, 0 fail (46 fixtures)
F1  node     PASS  fixtures/cgt-compact-kid-suite-mismatch.json  [cgt]
F1  node     PASS  fixtures/cgt-compact-unknown-key.json  [cgt]
F1  node     summary: 46 pass, 0 fail (46 fixtures)
F2  line 242 removed: exit 1 ... KeyError: 'broker-key-1'
F3  line 246 removed: exit 1 ... AttributeError: 'NoneType' object has no attribute 'verify'
F4  line 242 removed, f0d1339: summary: 44 pass, 0 fail (44 fixtures)
F4  line 246 removed, f0d1339: summary: 44 pass, 0 fail (44 fixtures)
F5  schema_validation.py: summary: 0 mismatches (46 fixtures)
F5  conformance_profile.py --check: conformance.json is current
```

The suite's generator reproduced its committed fixtures byte for byte before the change, so the two new fixtures come
from the same deterministic process.

## Next unrun test

The act-chain check (line 751), if the maintainer wants more; and the same mutants against the Node verifier.
