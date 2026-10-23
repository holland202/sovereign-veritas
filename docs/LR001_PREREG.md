# LR-001: does the three-way Gate agreement hold through an overnight run on a phone?

**State:** REGISTERED, NOT RUN. Committed before the overnight run is launched and before any of its output exists.
**Authors:** Direction: Chad Holland (2026-10-23). Design: Claude (Anthropic, Opus 5.5). Human review level: the owner read the
opening of the draft and a summary of the rest in chat, and approved committing it. Everything run here is **self-tested** (M10).

## Why

- DIFF-001's registered run on the S23 (2026-10-22) was cut short. Both workers stopped about 30 minutes into a
  14-hour window, without writing a final summary. Cause unknown.
- BT-001 red segment 1 found 0 disagreements in 21,361,718 cases at main `db640a2`, on a container (x86). Its
  segment 2 was not run.
- Nothing has yet shown that the phone can carry a long run to its deadline, or that K, V and I agree on fixed code
  on ARM/Android over many hours.

## Code (same overlay as BT-001's red arm, one commit later)

- main `827b49b`;
- plus `ports/python_independent/independent_gate.py` from PR #86 (SHA-256 `01592486…e6b0`);
- plus `experiments/DIFF-001/diff_fuzz.py`, unchanged (SHA-256 `55b32b13…4095`).

On the phone it is built with
`git checkout -q 827b49b && git checkout 28f7973 -- ports/python_independent experiments/DIFF-001`, and both hashes
are checked before launch.

## Device

Samsung Galaxy S23 FE, Termux, aarch64, Python 3.14.8. On the charger, Termux battery set to Unrestricted, and
`termux-wake-lock` held.

## Cases

- Two workers: `--worker 4000000000` and `--worker 4000000001`, `--workers 2` (interleaved indices).
- These are disjoint from the tuning indices 0–2,999, from DIFF-001's 3,010 upward, from the shakedown's
  3,000,000,000 upward, and from BT-001's two segments.
- `--until 2026-10-24T10:30:00Z` for both workers (6:30 AM EDT), fixed here before launch. Launch is planned for
  about 22:30Z on 2026-10-23, so the run lasts about 12 hours.

## Disclosed before registration (C-EXPLORE)

**Shakedown** (2026-10-23, from about 20:50Z to 21:50Z, same code and device, indices from 3,000,000,000). It judges
no claim here. It exists to check that the phone survives an hour.

Controls at its launch, as pasted by the owner from the phone:
- conformance: digest `44823d0f…0628`, `VERDICT CONFORMS`;
- `--mutant steps-ge --cases 20000`: 221 K-I disagreements, exit 0.

Result, as pasted by the owner from the phone (`grep` of both summaries):

| Worker | cases | disagreement_cases | final | seconds |
|---|---|---|---|---|
| 3000000000 | 3,283,883 | 0 | true | 3572.0 |
| 3000000001 | 3,262,427 | 0 | true | 3572.0 |

- Both workers reached the deadline. The S1/S2 checks stated in chat before the shakedown (`"final": true`, and 0
  disagreements) both held.
- Throughput: about 1,500 cases/s per worker in the first 3½ minutes (screen on), but only about 915/s averaged over
  the hour. The rate roughly halved once the screen was off. Claude's in-chat projection of "about 10 million
  cases" for the hour was wrong: the total was 6,546,310.
- LR-P4 below was written before this result. Its 700/s threshold is kept as written, but this result is now known,
  so it is a weak test.

## Controls, run at launch

- Conformance: `tools/gate_contract.py --check-command python ports/python_independent/independent_gate.py` must
  print `VERDICT CONFORMS`, digest `44823d0f…0628`.
- Anti-vacuity: `--mutant steps-ge --cases 20000` must exit 0. Expected: 221 K-I disagreements, as in BT-001 and
  the shakedown's control.

If either control is off, nothing is launched.

## Predictions

| ID | Prediction | conf. | Precisely wrong if |
|---|---|---|---|
| LR-P1 | Both controls behave as stated | 0.95 | not CONFORMS, or the mutant run exits 1 |
| LR-P2 | Both workers reach the deadline and write `"final": true` | 0.6 | either summary ends with `"final": false` |
| LR-P3 | 0 disagreements among K, V and I | 0.8 | any disagreement. Each signature class is then a finding, with a replayable index |
| LR-P4 | Throughput over the whole run is at least half the shakedown's first-minutes rate (about 1,400 cases/s per worker) | 0.5 | either worker averages under 700 cases/s |
| LR-P5 (door, unrun) | The same counts are reproduced exactly on x86 from the same indices, as DIFF-001's phone run was | — | — |

## Interpretation rule

- A disagreement shows that at least one implementation, or the contract text, is wrong or ambiguous for that
  input. It does not say which one.
- 0 disagreements supports agreement on the inputs tried, on this device. It gives no rate for other inputs, and it
  says nothing about inputs outside DIFF-001's mutation grammar (DIFF-001 P4 stays open).

## Pre-mortem

- **Android kills the processes** (DIFF-001's run). Mitigation: charger, Unrestricted battery, wake lock, and the
  shakedown first. If it happens anyway, LR-P2 is scored as refuted and the partial counts are reported as partial.
- **Thermal throttling** shows up as a low rate. LR-P4 measures it; it is not hidden.
- **Storage:** the disagreement file is capped at 1,000 records per worker, so a fault class cannot fill the disk.
