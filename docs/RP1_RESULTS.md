# RP-1 results: relying-party replay vectors. 8 of 9 as registered; the consumer's own gaps confirmed

Registration: [`RP1_PREREG.md`](RP1_PREREG.md), committed alone at `b999ee6` before the runner existed. Runner
`tools/rp1_vectors.py`, outputs and vectors at `f84886d`, baseline `main` `16850f6`. Linux x86_64 container, 2 CPUs,
Python 3.13.16. **NOT VALIDATED on the S25.** Unsigned packages throughout.

Drafted by Claude (Opus 5.5), which also wrote and ran the runner, at Chad Holland's direction. Chad has not
reviewed it line by line. Self-tested: the runner's author also judged the results.

## What went wrong, first

- **P7 is REFUTED by the runner, though not in the predicted direction.** The consumer did let one package through
  twice: 4 of 100 trials doubled at N=8, which is what P7 predicted. But one trial also had a process that ended
  with neither "accepted" nor "refused", and the runner's judge requires zero such errors. That "no errors" condition
  is in the code, not in the registered P7 text (the outcome rules only say errors are counted). The runner's
  verdict is kept as the result of record. Read against the registered text alone, P7 would hold.
- **The runner did not save that process's output.** An unregistered diagnostic afterwards (below) captured it:
  `COULD NOT LOOK: JSONDecodeError: Expecting value: line 1 column 1 (char 0)`. One process had truncated the state
  file (`open(path, "w")`) and another read it before it was rewritten. This is the non-atomic write P8 tests,
  seen live.
- **Deviation before the run.** The first attempt stopped with `COULD NOT RUN` before any vector was judged:
  `witness.py` refuses a log that git ignores, and `*.log` is ignored. The runner's log files were renamed to
  `.txt`. No prediction or trial count changed.
- **Two expected gaps in this repository were confirmed** (P3, P6–P8). They are written up as open issues on my side,
  not as findings about the draft.

## Outcome

| ID | Prediction | Result |
|---|---|---|
| P1 | re-verifying is not an error; a changed decision is | **HELD.** Two clean runs exit 0 with identical output; changed decision exits 1 |
| P2 | the same package is refused the second time; refusal leaves state unchanged | **HELD** |
| P3 | a second package for the same action is accepted (gap) | **HELD.** B accepted after A, same state: at-most-once is per package, not per action |
| P4 | an older package is STALE to a consumer that never acted on it | **HELD** |
| P5 | an anchored consumer refuses a rolled-back log; a fresh one accepts it | **HELD** |
| P6 | two checks on one state snapshot both accept; sequential second refuses | **HELD** |
| P7 | ≥ 1 of 100 trials doubles with 8 real consumer processes | **REFUTED by the runner's no-error rule** (4 doubled, 1 error; see above) |
| P7c | anti-vacuity: the harness sees doubles when a 0.2 s pause widens the window | **HELD.** 20 of 20 doubled |
| P8 | a torn state file fails closed (exit 2) even for a new package; intact state accepts it | **HELD** |
| P9 | `--flip` makes the runner report P2 REFUTED and exit 1 | **HELD** (output below) |

## Output, registered run (verbatim, `results/rp1/run_registered.txt`)

```
A 273d8055c74f  B d6eb8df882dc  same artifact, gate inputs and decision: True  decision ALLOW
  P1 verify A                                     exit 0 (expected 0) ok | VERDICT  CONSISTENT  freshness=NOT_PROVEN  authenticity=NOT_PROVEN
  P1 verify A again                               exit 0 (expected 0) ok | VERDICT  CONSISTENT  freshness=NOT_PROVEN  authenticity=NOT_PROVEN
  P1 verify A with decision changed               exit 1 (expected 1) ok | VERDICT  4 check(s) failed  freshness=NOT_PROVEN  authenticity=NOT_PROVEN
  P2 accept A, fresh state                        exit 0 (expected 0) ok | CONSUMER  ACCEPTED  (state updated)
  P2 accept A again, same state                   exit 1 (expected 1) ok | CONSUMER  REFUSED  (state unchanged)
  P3 accept A (log: A)                            exit 0 (expected 0) ok | CONSUMER  ACCEPTED  (state updated)
  P3 accept B, same action (log: A,B), same state exit 0 (expected 0) ok | CONSUMER  ACCEPTED  (state updated)
  P3 accept A again (log: A,B), same state        exit 1 (expected 1) ok | CONSUMER  REFUSED  (state unchanged)
  P4 A latest, fresh consumer S1                  exit 0 (expected 0) ok | CONSUMER  ACCEPTED  (state updated)
  P4 A after B witnessed, fresh consumer S2       exit 1 (expected 1) ok | CONSUMER  REFUSED  (state unchanged)
  P5 accept B (log: A,B): anchor 2 entries        exit 0 (expected 0) ok | CONSUMER  ACCEPTED  (state updated)
  P5 A with the log cut to 1 entry, anchored S    exit 1 (expected 1) ok | CONSUMER  REFUSED  (state unchanged)
  P5 A with the log cut to 1 entry, fresh S2      exit 0 (expected 0) ok | CONSUMER  ACCEPTED  (state updated)
  P6 interleaved: first True (first use; anchor now 1 entries); second on the same snapshot True (first use; anchor now 1 entries)
  P6 sequential:  second given the first's new state False (already acted on this package (replay))
  P7  real     N=8 trials=100 doubled=4 zero=0 errors=1 (25 s)
  P7c paused   N=8 trials=20 doubled=20 zero=0 errors=0 (pause 0.2 s between read and write)
  P8 accept A (builds a real state)               exit 0 (expected 0) ok | CONSUMER  ACCEPTED  (state updated)
  P8 B with the torn state T                      exit 2 (expected 2) ok | COULD NOT LOOK: JSONDecodeError: Unterminated string starting at: line 4 column 20 (char 50)
  P8 B with the intact state S                    exit 0 (expected 0) ok | CONSUMER  ACCEPTED  (state updated)

  P1   HELD
  P2   HELD
  P3   HELD
  P4   HELD
  P5   HELD
  P6   HELD
  P7   REFUTED
  P7c  HELD
  P8   HELD
mode: registered
VERDICT  8 of 9 as registered
exit 1
```

## P9: `--flip` (verbatim excerpt, `results/rp1/run_flip.txt`)

```
  P2 accept A, fresh state                        exit 0 (expected 1) NOT AS EXPECTED | CONSUMER  ACCEPTED  (state updated)
  P2 accept A again, same state                   exit 1 (expected 0) NOT AS EXPECTED | CONSUMER  REFUSED  (state unchanged)
  P2   REFUTED
mode: FLIP (P2 expectations inverted)
VERDICT  7 of 9 as registered
exit 1
```

The flip run made its own packages, so its race counts differ (`doubled=2 zero=0 errors=3`). The vector files kept
in `results/rp1/vectors/` are the registered run's.

## Unregistered diagnostic (verbatim, `results/rp1/diagnostic_unregistered.txt`)

Run after seeing P7, on the registered run's P7 package, capturing every process's output:

```
UNREGISTERED diagnostic, N=8, 100 trials
accepted-per-trial distribution: {1: 99, 2: 1}
trials doubled: 1
exit 2 x2: COULD NOT LOOK: JSONDecodeError: Expecting value: line 1 column 1 (char 0)
```

Across the three runs, doubled trials were 4, 2 and 1 of 100. The rate depends on timing and is small here; P6
shows the code has no protection, and P7c shows the harness sees doubles when the window is wider.

## The vectors

`results/rp1/vectors/P1`–`P8`, each with its inputs and a `vector.json` (commands, expected exit, expected
substring, observed exit). Commands run from the repository root; consumer state files start absent (the runner
saves its final states as `*.state.after.json`). P8's torn file `T.state.json` is the first half of `S.state.json`'s
bytes after P8's first step. All 16 saved steps were replayed from `vector.json` afterwards with identical exits.

## Next unrun test

As registered: carry an action key fixed at intent in `sv.package/1` and check that the consumer refuses P3's
second package. Added from this result: make the consumer's state update a single atomic claim (one exclusive-create
file per digest, as `FileReservations` already does for keys) and rerun P6–P8.
