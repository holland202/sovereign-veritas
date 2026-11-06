# SEC-006 results: NO_VIOLATION_IN_TESTED_SCHEDULES (run1, 2026-11-06)

Registration: [`SEC006_PREREG.md`](SEC006_PREREG.md), committed and pushed alone at `25951af` before the harness
existed. Harness and raw output: `0ad469f`.

## What could have gone wrong, first

- **Self-tested.** Claude registered, built, ran and judged this. It is not independent validation.
- **The schedules are a random sample with injected delays.** A pass says nothing about schedules this generator
  does not produce.
- **The counts are not reproducible to the digit.** They depend on OS scheduling, so the DIGEST is printed for the
  record but not pinned. The verdict, not the counts, is what CI checks.
- **One extra analysis was done after the run, outside the registration** (the failure shapes below). It was run
  on a fresh set of the same 20 seeds, so its counts are from different trials than run1's, and it is labelled
  post-hoc.
- **No deviation from the registration** in the workload, seeds, oracle or verdict rule. The 3 dev seeds were run
  first while building and are reported separately; they were not scored.

## Raw output

`results/sec006/run1/`: `run.txt` (registered seeds 1–20), `sabotage.txt`, `dev_seeds.txt`, and
`posthoc_failure_shapes.{py,txt}`. Pasted from `run.txt`:

```
PYTHON=3.13.18
PLATFORM=Linux-6.18.44-fc-v242-x86_64-with-glibc2.39
IDEMPOTENCY_BLOB=8013269f8051653c4dd0c900a86927453f448cd9
WORKLOAD P=6 K=8 M=250
LOCK   trials with a violation: 0 of 20; late_complete total 2651; releases 4315
NOLOCK trials with a violation: 20 of 20; keys violated total 160
P1 HELD
P2 HELD
P3 HELD
P4 HELD
DURATION_S=25.6
VERDICT NO_VIOLATION_IN_TESTED_SCHEDULES: 4 of 4 as registered
DIGEST=fb3a3c571b7c04d69c362174262af85376ecb5eb45fd126d4ce8a0d70a8ae9f2  (not pinned: counts depend on OS scheduling)
```

`sabotage.txt` (lock removed in both arms): `P1 REFUTED`, `P3 REFUTED`, `VERDICT VIOLATION: 2 of 4 as registered`,
exit 1. Every LOCK-arm worker in run1 exited 0 with no errors.

## Predictions

| ID | Prediction | Result |
|---|---|---|
| P1 | LOCK: invariant I1 holds in all 20 trials | HELD (0 of 20 trials violated) |
| P2 | NOLOCK: I1 broken in at least 1 trial (the oracle can see the bug) | HELD (20 of 20; all 8 keys in every trial) |
| P3 | LOCK: no hangs or unexpected errors | HELD |
| P4 | LOCK: at least 100 stale completions recorded as late events and at least 100 releases | HELD (2651 and 4315) |

## What the no-lock failures are (post-hoc, not registered)

Fresh trials on the same 20 seeds, counting the three ways I1 can break:

```
lock   trials with a lost reservation: 0/20 (lost tokens total 0); trials with duplicated entries: 0/20; trials with a file missing its token: 0/20
nolock trials with a lost reservation: 20/20 (lost tokens total 410); trials with duplicated entries: 20/20; trials with a file missing its token: 14/20
```

A **lost reservation** (a granted token in no file) is the SEC-004 shape: a fresh holder's entry was overwritten.
Without the lock it also happens through `release()`'s write-then-rename, not only through `complete()`. Duplicated
entries and entries without a token are further damage from unserialised writes. With the lock, none of the three
appeared.

## What this shows and does not show

- **Shows (implementation, sampled schedules):** under 20 seeded random workloads of 6 processes on 8 keys with
  injected write delays, the SEC-005 lock kept every granted reservation recorded exactly once, while the same
  workload without it lost reservations in every trial.
- **Does not show:** correctness under all schedules; network filesystems; any platform beyond the one this ran
  on (Linux x86_64 here; the new CI workflow adds Linux, macOS and Windows); independent validation.

## CI

`.github/workflows/sec006-stress.yml` runs the registered seeds and the sabotage check on ubuntu-latest,
macos-latest and windows-latest when `idempotency.py`, the harness or the workflow changes on `main`. It is not part
of the main test suite, because its counts depend on scheduling. CI results are appended here when they arrive.

## Still open (the door)

- Run on the S25 under Termux.
- The Windows lock-loop error-handling issue found by reading the source (`except OSError: continue` retries on any
  error) is still unreproduced and left for ChatGPT's independent challenge.

## Provenance (M13)

Claude (Anthropic, Opus 5.5) designed, built, ran and wrote this up → human validation: not performed → human
editing/curation: direction by Chad Holland, 2026-11-06 → human responsibility: Chad Holland. Review level:
direction only.

## Amendment 1, 2026-11-06 (appended; the text above is unchanged): the oracle crashed on Windows CI

**What happened.** On PR #101 (head `30f886c`), the `sec006 (windows-latest)` job ran seed 1's LOCK arm cleanly
(`violations=0`, all workers exited 0), then crashed in seed 1's NOLOCK arm with `JSONDecodeError` inside
`FileReservations.late_events()`, called by the harness's oracle. Raw log excerpt:
`results/sec006/ci_windows_job127867391414_crash.txt`.

**Cause.** Without the lock, concurrent appends to a key's late-event log on Windows left a line that is not
valid JSON. `late_events()` parses every line and raises on a bad one, so the oracle stopped. The registration did
not foresee an oracle crash. **The Windows run is INCONCLUSIVE.** It is not a violation in the LOCK arm, and it is
not a pass.

**Change (harness only, `tools/sec006_stress_probe.py`).** The oracle now reads the late-event log line by line
itself and counts an unreadable line in `unreadable`, instead of calling `late_events()`. In the LOCK arm an
unreadable line therefore fails P1, which is stricter than before. Workload, seeds, predictions and the verdict
rule are unchanged. `sovereign_veritas/` is unchanged.

**Re-run on Linux after the change** (`results/sec006/amend1_linux_run.txt`, `amend1_linux_sabotage.txt`):

```
LOCK   trials with a violation: 0 of 20; late_complete total 2530; releases 4263
NOLOCK trials with a violation: 20 of 20; keys violated total 160
VERDICT NO_VIOLATION_IN_TESTED_SCHEDULES: 4 of 4 as registered
--sabotage: VERDICT VIOLATION: 2 of 4 as registered (exit 1)
```

**A side observation, not changed here.** `late_events()` raises on a corrupted line rather than skipping it.
That is loud, not silent, so it does not hide anything; with the lock held, the log is only written inside the
critical section. Whether it should report corruption explicitly is left as an open question.

**Windows result:** to be appended when CI re-runs on this change.

Provenance: Claude (Anthropic, Opus 5.5), at Chad Holland's direction (2026-11-06, direction only) → human
validation: not performed → human responsibility: Chad Holland.
