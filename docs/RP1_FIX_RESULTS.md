# RP-1 fix: a lock around the consumer's state file — results

Status: **Fixed** (2026-10-07) on `tools/consumer.py`. Closes the gap `docs/RP1_RESULTS.md` (P6, P7,
P7c) and `CHALLENGE.md` published as open. This does not touch P3 (one action, two packages — a
schema question for `sv.package/1`, not this fix) or change P8's fail-closed behaviour on a
pre-existing torn state file.

Found during an independent adversarial review requested by Chad Holland, scoped to this
repository as it stood at `709da9e`. Not an external report; no issue was filed.

## The defect

`tools/consumer.py main()` read the state file (`load_state`), decided accept/refuse
(`consumer_check`), and — only on accept — rewrote it (`open(path, "w")`), with no lock around
any of it. `docs/RP1_RESULTS.md` already measured this: P6 showed two in-process calls on one
snapshot both say "accept" (the code has no lock, by inspection); P7 found it live across real
processes (4 of 100 trials doubled); P7c, pausing between the read and the write to widen the
window, doubled 18-20 of 20. The note's own "next unrun test" named the fix: "make the consumer's
state update a single atomic claim ... and rerun P6-P8."

Reproduced again before fixing anything, same technique as P7c (`load_state` monkeypatched to
sleep 0.2s after reading, 6 processes per trial, one package, one fresh state file per trial):
**15 of 15 trials doubled** (`tests/test_consumer.py::test_concurrent_accepts_do_not_double`,
run against the pre-fix code). "Act once, never go backwards" — this file's own opening line —
did not hold under concurrent use, which is a use this repository documents (RP-1, P7) rather than
disclaims.

## The fix

Two changes to `tools/consumer.py`, no change to the CLI, its exit codes, or any check's name or
behaviour:

1. **A lock around the whole load-check-write.** `_acquire_lock` claims `<state>.lock` with
   `os.open(O_CREAT | O_EXCL)` — the same atomic-create idiom `sovereign_veritas/idempotency.py`'s
   `FileReservations` already uses for keys, so no new locking primitive enters the codebase. It
   is portable (no `fcntl`/`msvcrt` split), so it runs the same way on every platform `consumer.py`
   is tested on, unlike `AnchoredFileLedger`'s POSIX-only `fcntl.flock` (skipped on Windows).
   `main()` claims the lock before `load_state`, so a second process waits and then reads the
   first's *committed* state rather than the stale snapshot P6 demonstrates. A lock that cannot be
   claimed within 30s fails closed (`COULD NOT LOOK`, exit 2) — it never proceeds unlocked.
2. **An atomic state write.** `_write_state` writes a temp file, fsyncs it, and `os.replace`s it
   into place, instead of a truncating `open(path, "w")`. This is a direct instance of the fix the
   note proposed ("a single atomic claim"); it also removes the specific non-atomic write P8's
   torn-file case was built around (the diagnostic in `docs/RP1_RESULTS.md` caught this exact write
   torn live: `JSONDecodeError: Expecting value: line 1 column 1`). P8 itself is unchanged: a state
   file torn by something else (a disk fault, an older binary) still fails closed, exit 2.

The lock is released in a `finally`, including on every existing error path (`COULD NOT LOOK`
still exits 2 with the lock released). A process killed while holding the lock leaves a stale
`<state>.lock` file: a liveness cost for a human to clear, never a double-accept — the same
trade-off `sovereign_veritas/idempotency.py` already makes and documents for the same reason.

## Regression test

`tests/test_consumer.py::test_concurrent_accepts_do_not_double`: 8 trials, 6 processes each, one
package, `load_state` paused 0.2s between read and write (P7c's own technique, reused so the test
does not depend on hitting a narrow timing window). Confirmed to fail against the pre-fix code
(8 of 8 trials doubled, run via `git stash` on `tools/consumer.py` alone) and to pass against the
fix (0 of 8).

## Results

| Run | doubled | zero | errors |
|---|---|---|---|
| Manual reproduction, pre-fix, 15 trials, N=6 (P7c technique) | 15 | 0 | 0 |
| `tests/test_consumer.py::test_concurrent_accepts_do_not_double`, pre-fix, 8 trials, N=6 | 8 | 0 | 0 |
| `tests/test_consumer.py::test_concurrent_accepts_do_not_double`, post-fix, 8 trials, N=6 | 0 | 0 | 0 |
| `tools/rp1_vectors.py` P7 (real), post-fix, 100 trials, N=8 | 0 | 0 | 0 |
| `tools/rp1_vectors.py` P7c (paused), post-fix, 20 trials, N=8 | 0 | 0 | 0 |

Rerunning `tools/rp1_vectors.py` against the fix reports P7 and P7c **REFUTED**: the predictions
registered in `docs/RP1_PREREG.md` ("at least 1 of 100 trials doubles", "at least 18 of 20 trials
doubled") no longer hold, which is the fix working, not a new gap. `docs/RP1_RESULTS.md` itself is
left as written — it is the record of the pre-fix run at baseline `16850f6` — and this file is the
dated follow-up. P1-P6, P8, P9 are unaffected (still HELD; full transcript not reproduced here).

Full suite after the fix: **481 passed, 1 skipped** (container; the 1 skip is `pymavlink`, unrelated
to this change). Before the fix, with the new test added: 480 passed + the new test failing (8 of 8
doubled, see above).

## What this does not claim

- **Not validated on Windows or macOS.** `os.open(O_CREAT | O_EXCL)` is documented as atomic
  there too, but this was run only in the same Linux container as the rest of this review.
- **Not a fix for P3.** A second, different package for the same action is still accepted; that
  needs an action identity bound into the package format (`sv.package/1`), which the note already
  says is Chad's decision, not an implementation bug.
- **Liveness, not safety, is what a crash costs now.** A process killed between claiming the lock
  and releasing it blocks that state file until a person removes `<state>.lock`. This is the same
  shape of trade-off as `idempotency.py`'s `UNKNOWN`/`IN_FLIGHT` keys, made for the same reason:
  never trade a double-accept for availability.
- **A network filesystem or Android/Termux shared storage is untested.** `FileReservations` names
  the same boundary (one local filesystem); this fix inherits it.

## Addendum (2026-10-07, later): a defect this fix introduced (K1), found and fixed

The lock above was an `os.open(O_CREAT | O_EXCL)` lock **file**, released by deleting it. A consumer killed while holding
it never deletes it. Probe (`SIGKILL` of a consumer paused inside the lock, then a fresh consumer), on `48ab26a`:

```
lock file left behind after SIGKILL: True
next consumer: exit 2 after 30.1s: COULD NOT LOOK: could not claim '/tmp/tmpmvcbgmig/s.json.lock' within 30.0s (another consumer running, or a stale lock l
```

Fail closed (no double-accept), but permanent: every later consumer on that state file failed until a person removed the
file. Any crash turned the relying party into a denial of service. The section above called this "a liveness cost for a
human to clear"; measured, it is worse than that sentence suggests, and it was avoidable.

**Fix:** an operating-system advisory lock on the same path, `fcntl.flock` (POSIX) or `msvcrt.locking` (Windows), both
released by the kernel when the holder exits or is killed. The lock file is never unlinked (unlinking a locked file lets
two processes lock two different inodes), so a zero-byte `<state>.lock` persists by design (`.gitignore`d). With neither
primitive available the consumer fails closed. **Windows path not validated.**

After: the same probe prints `next consumer: exit 0 after 0.1s: CONSUMER  ACCEPTED  (state updated)`. Regression
`tests/test_consumer.py::test_a_killed_lock_holder_does_not_block_the_next_consumer` fails on `48ab26a` (30.75 s) and passes
after; the race regression still passes; `rp1_vectors.py` P7 0/100, P7c 0/20 doubled. Container only.
