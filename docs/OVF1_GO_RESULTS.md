# OVF-1 (Go): results (appended after the fix; the registration is unchanged)

Registration: [OVF1_GO_PREREG.md](OVF1_GO_PREREG.md) at `db89dac`, before any fix. Failing test before the fix:
`92fcd2e` ([R1 output](../results/ovf1_go/R1_before_fix.txt)). Raw post-fix output:
[results/ovf1_go/after_fix.txt](../results/ovf1_go/after_fix.txt). Self-tested by the author (Claude, Anthropic,
Opus 5.5) on Python 3.13.18 and Go 1.24.7, x86_64. Human review level: direction only.

**Fix:** `fixed4` in `ports/go/main.go` prints ±Inf as `inf` and `-inf`, as Python's `format(x, ".4f")` does.
`CONTRACT.md`'s Formatting section now states this. Its status line now counts the PR #86 port. The vectors file is
not edited.

| ID | Outcome | Evidence |
|---|---|---|
| R1 | HELD | Before the fix the Go port gave `['evidence_quality_below_threshold:0.2000<+Inf']` for floors `10**400` and `2**1024`; 2 failed, 1 passed |
| R2 | HELD | After the fix both give `DEFER ["evidence_quality_below_threshold:0.2000<inf"]`, equal to the kernel's |
| R3 | HELD | Floor `-(10**400)`: `ALLOW []` before and after (the passing test in R1 and after the fix) |
| R4 | HELD | `--check-command` on the fixed Go binary: `VERDICT CONFORMS`, digest `44823d0f…0628`; vectors file unchanged against `origin/main` |
| R5 | HELD | `572 passed, 1 skipped` |
| R6 | HELD | Reverting `ports/go/main.go` → 2 failed, 1 passed |

CI: the `port-go` job runs the new test against the binary it builds. It sets `SVGATE_GO_BIN`, so a missing binary
fails rather than skips.

**Not covered (door):** a vector pinning the infinite floor, which needs a contract-version decision because it
changes the vectors file and the conformance digest. Other four-place values are also not covered. NOTE076-X1's Q4,
the 309-digit value of `10**308`, already agreed across all five implementations.

Credit: the disagreement was found by Principia-Artificialis NOTE076-X1 (PA PR #143), which compared all five
`sv.gate/0` implementations, including Putluru Sandeep's PR #86 port, off the vectors.
