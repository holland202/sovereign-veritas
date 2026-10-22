# OVF-1: a too-large integer quality floor crashes the Gate. Registered before the fix

**State:** REGISTERED. The fix is NOT written at the commit that adds this file.
**Found by:** DIFF-001 smoke runs (2026-10-22, branch `research/diff-001-gate-differential`). The kernel Gate (K) and `tools/verify_package.py` `replay_gate` (V) raise `OverflowError` when `capability.min_evidence_quality` is an integer too large for a double, e.g. `10**400`, a valid JSON number, and the evidence quality is valid and below it. The independent port from PR #86 returns DEFER.
**Authors:** Claude (Anthropic, Opus 5.5), at Chad Holland's direction. Human review level: direction only. Self-tested (M10).

## Cause (read from the source; no fix written yet)

- K: `sovereign_veritas/decision.py` formats the reason with `f"...{q:.4f}<{capability.min_evidence_quality:.4f}"`. `format(10**400, ".4f")` converts the integer to a float and raises `OverflowError`. The comparison `q < 10**400` just before it does not raise.
- V: `tools/verify_package.py` has the same `{floor:.4f}` in `replay_gate`.
- [CONTRACT.md](../CONTRACT.md) rule 10 already says that "an integer too large for a double is +infinity or -infinity" for *q*. The floor is printed as "<floor, 4 places>" of a double, so an overflowing floor should print as `inf` (Python: `format(math.inf, ".4f") == "inf"`). The proposed fix applies that to the floor's formatting only. Comparisons are unchanged.

## Predictions

- **R1 (before fix).** The new tests fail on `main` (`3ff59ef`): K and V raise `OverflowError` for floor `10**400` with q = 0.2.
- **R2.** After the fix, K and V both return `DEFER` with reasons `["evidence_quality_below_threshold:0.2000<inf"]` for that input. This is the string the independent port returns.
- **R3.** A floor of `-(10**400)` gives no quality reason and no crash (q < -inf is false).
- **R4.** The 4,690 published vectors are unchanged and still conform, for K and V. The conformance digest stays `44823d0f…0628`, and `contract/gate_vectors.jsonl` is not edited.
- **R5.** The full test suite passes.
- **R6.** Reverting either half of the fix (K or V) makes its new test fail.
- **R7 (uncertain).** Re-running the DIFF-001 smoke harness (A1+A2, 3,000 cases) against K and V with this fix and the PR #86 port gives **0** disagreements. If it does not, the remaining classes are new findings, reported as such.

Out of scope: the Go port (`ports/go`). Whether its JSON decoder accepts `10**400` at all is untested here.
