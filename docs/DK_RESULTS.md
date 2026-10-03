# DK results: the verifier now refuses duplicate JSON keys and NaN/Infinity

Registration: docs/DK_PREREG.md (2b7e030), committed before the probe and before the verifier change.
x86-64 container, Python 3.13.15. **NOT VALIDATED on the S25.** Claude-assisted (Claude Opus 5.5); Chad gave
direction only. Self-tested; not independent review.

## Failures and limits first
- No registered prediction failed. K1, K2 and K5 were informed by one earlier unregistered run (disclosed in the
  registration); K3, K4, K6 and the "after" values were not run before registering.
- **Stated cost (DK5):** a harmless exact duplicate (K4) is now refused in 8/8. Ambiguous input is rejected, not normalized.
- The cross-language risk (a parser elsewhere that keeps the *first* duplicate) is argued, not measured.

## Before the change (`python tools/dk_probe.py --baseline` on the unchanged verifier)
```
packages 8; K0 text identical to the original bytes: True
K0  exit codes [0, 0, 0, 0, 0, 0, 0, 0]  {0: 8}
K1  exit codes [0, 0, 0, 0, 0, 0, 0, 0]  {0: 8}
K2  exit codes [1, 1, 1, 1, 1, 1, 1, 1]  {1: 8}
K3  exit codes [0, 0, 0, 0, 0, 0, 0, 0]  {0: 8}
K4  exit codes [0, 0, 0, 0, 0, 0, 0, 0]  {0: 8}
K5  exit codes [1, 1, 1, 1, 1, 1, 1, 1]  {1: 8}
K6  exit codes [1, 1, 1, 1, 1, 1, 1, 1]  {1: 8}
HELD    DK1 (before the change)
HELD    DK2 (before the change)
```
**The gap was general:** a planted first value verified CONSISTENT in all 8 packages, at the top level (K1) and
nested inside `gate_inputs` (K3).

## After the change
```
packages 8; K0 text identical to the original bytes: True
K0  exit codes [0, 0, 0, 0, 0, 0, 0, 0]  {0: 8}
K1  exit codes [2, 2, 2, 2, 2, 2, 2, 2]  {2: 8}
K2  exit codes [2, 2, 2, 2, 2, 2, 2, 2]  {2: 8}
K3  exit codes [2, 2, 2, 2, 2, 2, 2, 2]  {2: 8}
K4  exit codes [2, 2, 2, 2, 2, 2, 2, 2]  {2: 8}
K5  exit codes [2, 2, 2, 2, 2, 2, 2, 2]  {2: 8}
K6  exit codes [2, 2, 2, 2, 2, 2, 2, 2]  {2: 8}
HELD    DK3 (after the change)
HELD    DK5 (K4 refused: the stated cost)
DIGEST d775ead0a8e2dce0eb08e77d7bbac487f4deafad80e3caeaac56f4a79adf0a8a
```
K1–K6 now exit 2 (COULD NOT LOOK: malformed input) in 8/8; the originals still verify (K0 8/8).
Sabotage (old parser swapped back in) refutes DK3 and DK5 and exits 1:
```
K6  exit codes [1, 1, 1, 1, 1, 1, 1, 1]  {1: 8}
REFUTED DK3 (after the change)
REFUTED DK5 (K4 refused: the stated cost)
DIGEST 0d050ed4dbdb7939accec329c2ead86444deacb01a4afd8d801f3fa63dace511
```

## Regression (DK4)
- `python -m pytest -q`: `452 passed, 1 skipped`, the same count as before the change.
- `python tools/nonfinite_probe.py`: `VERDICT  no fail-open, no crash over 8 package(s)` (0 FAIL-OPEN, 0 CRASH in every package).

## Change
`tools/verify_package.py::loads_bounded` now passes `object_pairs_hook` (refuses a repeated key at any depth,
including embedded artifacts) and `parse_constant` (refuses NaN, Infinity, -Infinity). `tools/consumer.py` uses the
same parser instead of its own `json.loads`. The kernel's writer is unchanged (it never emits duplicates or NaN).

## Door (M15)
Parse-differential test against Go `encoding/json` and one first-wins parser on the K1–K6 files. Unregistered.
