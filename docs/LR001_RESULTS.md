# LR-001 results: the overnight run stopped early, with 0 disagreements in the 15.9 million cases it ran

**State:** PARTIAL RUN, scored against [LR001_PREREG.md](LR001_PREREG.md) (registration commit `1394134`, pushed
before launch). Self-tested (M10).
**Authors:** Direction and device operation: Chad Holland. Design and write-up: Claude (Anthropic, Opus 5.5). Human
review level: the owner ran every phone command and pasted the outputs used here. He had not reviewed this write-up
when it was committed.

## Failures first

1. **LR-P2 REFUTED.** Neither worker reached the deadline (2026-10-24T10:30Z) or wrote `"final": true`. Worker 0
   stopped about 2 h 04 m after launch, and worker 1 about 3 h 04 m after launch, out of a planned 12 h 14 m.
2. **Protocol deviation: the phone was not on a charger.** The registration's Device section says "On the charger",
   and its pre-mortem names the charger as a mitigation. The owner reports the phone was not charging and its
   battery died overnight. LR-P2 was therefore tested under a deviation. This run does not show whether the phone
   can last the night on a charger.
3. **The two workers stopped an hour apart** (last saves at 00:20:57Z and 01:20:59Z). A single battery death would
   have stopped both together, so something stopped worker 0 first, about an hour before the phone went down. Cause
   unknown. One possibility is Android limiting background work at low battery, but nothing here tests that.

## Scoring

| ID | Prediction | Result |
|---|---|---|
| LR-P1 | Both launch controls behave as stated | **HELD.** Conformance printed `VERDICT CONFORMS`. `--mutant steps-ge --cases 20000` gave 221 K-I disagreements and exit 0, the same as BT-001, the shakedown and a container run |
| LR-P2 | Both workers write `"final": true` | **REFUTED** (see above, including the deviation) |
| LR-P3 | 0 disagreements among K, V and I | **HELD on the cases run:** 15,920,000 cases, 0 disagreements. This is a partial run, so it says nothing about the indices it never reached |
| LR-P4 | Each worker averages at least 700 cases/s | **HELD, weak.** 874 and 850 cases/s. As the registration says, the threshold was set before the shakedown but the shakedown rate (about 915/s) was known at commit, so this is a weak test |
| LR-P5 | The same counts reproduce on x86 | NOT RUN (door) |

## Evidence

Launch, as pasted by the owner from the phone: both workers started at 2026-10-23 18:16 EDT (22:16Z). Both
summary files and both 0-byte disagreement files existed at 18:18 EDT.

Final state, as pasted by the owner from the phone after the battery died (`grep` of both summary files; worker 0
first, files in name order):

```
 "cases": 6520000,
 "disagreement_cases": 0,
 "final": false,
 "seconds": 7457.6,
 "utc": "2026-10-24T00:20:57+00:00"
 "cases": 9400000,
 "disagreement_cases": 0,
 "final": false,
 "seconds": 11059.7,
 "utc": "2026-10-24T01:20:59+00:00"
```

Derived (arithmetic on the lines above):

| Worker | Index start | Cases | Seconds | Cases/s | Start (utc − seconds) | Last save |
|---|---|---|---|---|---|---|
| 0 | 4,000,000,000 | 6,520,000 | 7,457.6 | 874 | 22:16:39Z | 00:20:57Z |
| 1 | 4,000,000,001 | 9,400,000 | 11,059.7 | 850 | 22:16:39Z | 01:20:59Z |

The summary is saved every 20,000 cases by an atomic replace, so each worker stopped less than 20,000 cases (about
23 s) after its last save. Cases after the last save were run but not recorded, and they are not counted.

**Not yet in the repo:** the raw summary and disagreement files are still on the phone. Only the owner's `grep`
paste is quoted here. The raw files should be added unedited when they can be transferred.

## What this supports (C-DESIGN)

- On the S23 FE (aarch64, Android, Termux, Python 3.14.8), the kernel Gate, the package verifier and the PR #86 port
  agreed on all 15,920,000 generated cases that ran from these two index ranges, at main `827b49b`. This is
  conformance on the inputs tried, not a rate for other inputs.
- Together with BT-001 segment 1 (21,361,718 cases at `db640a2`, x86) and the shakedown (6,546,310 cases, the same
  code and device), that is about 43.8 million generated cases with 0 disagreements since the OVF-1 fix. All of them
  come from DIFF-001's single mutation grammar, so DIFF-001 P4 (inputs from outside that grammar) is still open.

## Doors (unrun)

- **LR-002:** repeat with the phone on a charger, and with the charger's output recorded. Predict `"final": true`
  for both workers. If the charger can't keep up with two workers, test whether one worker reaches the deadline.
- **LR-P5:** reproduce both partial counts on x86 from the same indices, as was done for DIFF-001's phone run.
  That needs the `kernel_decisions` lines from the phone, which the paste above leaves out.
