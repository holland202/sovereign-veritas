# OVF-1 (Go): the Go port prints an infinite quality floor as `+Inf`. Registered before the fix

**State:** REGISTERED. The fix is NOT written at the commit that adds this file.
**Found by:** Principia-Artificialis NOTE076-X1 (2026-11-13, PA PR #143), prediction A2, refuted. Six out-of-range
probes went to five implementations at `7be4909`. The Go port (`ports/go`) returned
`DEFER ["evidence_quality_below_threshold:0.2000<+Inf"]` for a quality floor of `10**400` and of `2**1024`, with
q = 0.2. The kernel Gate (K), `replay_gate` (V), the Rust port and the independent port from PR #86 return
`…0.2000<inf`. All five conform on the 4,690 vectors, because no vector has an infinite floor. This closes the door
OVF-1 left open ("Out of scope: the Go port").
**Authors:** Claude (Anthropic, Opus 5.5), at Chad Holland's direction (2026-11-13). Human review level: direction
only. Self-tested (M10).

## Cause (read from the source; no fix written yet)

- `ports/go/main.go`: `fixed4(f)` is `strconv.FormatFloat(f, 'f', 4, 64)`. For +Inf, Go prints `+Inf`; Python's
  `format(math.inf, ".4f")` prints `inf`. The comparison and the decision are already right. The Go port does not
  crash (`toFloat` keeps `ParseFloat`'s ±Inf).
- [CONTRACT.md](../CONTRACT.md) does not say how an infinite four-place value prints. It says so for `<q>` (`inf`,
  `-inf`, through `repr`), not for the floor. So K's `inf` (since OVF-1) is the reference behaviour, but the text
  did not state it.

## Change

1. `ports/go/main.go`: `fixed4` prints ±Inf as `inf` and `-inf`. Nothing else changes.
2. `CONTRACT.md`, Formatting: one sentence saying an infinite four-place value prints as `inf` or `-inf`, as
   K and V already do. The status line is corrected to count the PR #86 port, which it says does not exist. No rule
   changes, and the vectors file is not edited.
3. A regression test, `tests/test_port_go_infinite_floor.py`, run in the `port-go` CI job.

## Predictions

- **R1 (before fix).** The new test fails on this branch before the fix: the Go port prints `0.2000<+Inf` for floors
  `10**400` and `2**1024`.
- **R2.** After the fix, it prints `0.2000<inf` for both, the string K returns.
- **R3.** A floor of `-(10**400)` gives `ALLOW []` before and after (no quality reason).
- **R4.** The Go port still conforms on the 4,690 vectors, digest `44823d0f…0628`.
  `contract/gate_vectors.jsonl` is not edited.
- **R5.** The full test suite passes.
- **R6.** Reverting the Go change makes the new test fail again.

Not covered (door): other four-place values Go and Python might print differently. NOTE076-X1's Q4 (`10**308`, a
309-digit value) already agreed across all five. No vector pins the infinite floor, because adding one changes the
vectors file and the conformance digest. That is left for a contract-version decision.
