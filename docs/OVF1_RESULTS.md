# OVF-1: results (appended after the fix; the registration is unchanged)

Registration: [OVF1_PREREG.md](OVF1_PREREG.md) at `584c5dc`, before any fix. Failing tests on unfixed `main`: `7a8578a` ([R1 output](../results/ovf1/R1_before_fix.txt)). Raw post-fix output: [results/ovf1/after_fix.txt](../results/ovf1/after_fix.txt). Self-tested by the author (Claude, Anthropic, Opus 5.5) on Python 3.13.16, x86_64. Human review level: direction only.

**Fix:** a four-place formatter (`_fixed4` in `sovereign_veritas/decision.py`, `fixed4` in `tools/verify_package.py`) prints an integer floor too large for a double as a signed infinity. This applies CONTRACT.md rule 10's ±infinity rule to the floor's formatting. Comparisons, other reasons and the vectors are unchanged.

| ID | Outcome | Evidence |
|---|---|---|
| R1 | HELD | `OverflowError: int too large to convert to float` at `decision.py:113` and `verify_package.py:457`; 2 failed, 2 passed |
| R2 | HELD | K and V return `DEFER ["evidence_quality_below_threshold:0.2000<inf"]` |
| R3 | HELD | floor `-(10**400)`: no quality reason and no crash (this already held before the fix) |
| R4 | HELD | `--check kernel` and `--check verifier`: `VERDICT CONFORMS`, digest `44823d0f…0628`; vectors file not edited |
| R5 | HELD | `544 passed, 1 skipped` |
| R6 | HELD | reverting the kernel half → 1 failed; reverting the verifier half → 1 failed |
| R7 | HELD | DIFF-001 harness (A1+A2, branch `research/diff-001-gate-differential` `d0890ef`) on the fixed K/V and PR #86's port: **0 disagreements in 3,000 cases** |

Additional observation, not registered: 100,000 harness cases on the fixed K/V and the #86 port gave 0 disagreements. Decisions: 4,471 ALLOW, 28,250 DEFER, 67,279 REFUSE.

**Not covered (door):** the Go port (`ports/go`), and whether Go's JSON decoding accepts `10**400` at all; the DIFF-001 registered long run; inputs outside the DIFF-001 mutation grammar.

Credit: the defect was surfaced by comparison with Putluru Sandeep's independent port (PR #86), which handles the case correctly.
