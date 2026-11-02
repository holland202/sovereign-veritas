# SEC-005: a per-key lock for `FileReservations` (fix for SEC-004) — preregistration

**Status: REGISTERED, UNRUN, NO CODE.** This file is committed alone, before any change to
`sovereign_veritas/idempotency.py` and before the SEC-005 probe exists. Registered 2026-11-02 by Claude
(Anthropic, Opus 5.5) at Chad Holland's direction. Chad has not reviewed it line by line (review level:
direction only). Repository remains **maintenance-only, experimental, not production-ready, not independently
security-validated**. A security fix is permitted under the maintenance notice.

- **Builds on:** [`SEC004_PREREG.md`](SEC004_PREREG.md) and [`SEC004_RESULTS.md`](SEC004_RESULTS.md)
  (2026-10-11 run: `SECURITY_FAIL`, P2 held: a stale completion replaced a fresh reservation).
- **Baseline re-check, 2026-11-02, before this registration:** the unchanged SEC-004 probe was run again at
  `7e40c12` (`idempotency.py` blob `071fc3fe…`, Python 3.13.18, Linux x86_64, this sandbox). It printed
  `GATE=SECURITY_FAIL` with P0–P5 all true. The raw output is committed with the results, not here. The defect
  is present on today's code.

## The defect, in one line

`FileReservations._move()` checks the holder token, then writes; `release()` checks UNKNOWN, writes, then
renames; `reserve()` creates with `O_EXCL`. Nothing serializes these across threads or processes, so a holder
that passed its token check can write after a release and a fresh reserve, replacing the new reservation.

## The change (registered now; nothing else in the module changes)

In `sovereign_veritas/idempotency.py`, `FileReservations` only:

1. A per-key lock file `<sha256(key)>.lock` beside the entry, named with `self._path(key).with_suffix(".lock")`
   (no new hash site; JG-2 P1). It is created on first use and **never deleted**, since deleting a lock file
   reopens a race.
2. An exclusive OS lock on that file: `fcntl.flock(LOCK_EX)` on POSIX, `msvcrt.locking` on one byte on
   Windows (retried while the OS reports it busy). Released on exit, and by the OS if the process dies.
3. The lock is held across the whole of `reserve()`, `_move()` (so `complete()` and `unknown()`) and
   `release()`: read, check, write and rename happen inside one critical section. No method takes it twice.
4. Readers (`state()`, `history()`, `late_events()`, `released_history()`) stay unlocked, as now. They read
   whole files written by `os.replace`, or fail closed.

Not changed: the on-disk entry format, the late-event format, the token semantics (a holder whose token still
matches may complete an expired lease, as RK-3 allows), `MemoryReservations`, `workflow.py`.

**Why this design.** It is the file-store equivalent of the `threading.Lock` `MemoryReservations` already
holds across each operation. A compare-and-swap on file contents alone cannot cover `release()`'s rename. A
lock directory with `mkdir` would need stale-lock recovery after a crash; an OS lock is released by the kernel.

## Instrument: `tools/sec005_lock_probe.py` (to be written after this commit)

It imports the real `FileReservations` and the SEC-004 probe's own case functions (`c0_memory`, `c1_file`,
`c3_completed_refusal`, `PausedCompletion`, `snapshot`) by path; it does not copy them. `--sabotage` replaces
the new lock with a no-op context manager, in the parent and in any child process, and must change the
outcome. Fixed waits: `BLOCK_S = 3.0` (how long a blocked operation must stay blocked), `DONE_S = 20.0` (the
most any step may take before the run is INCONCLUSIVE).

| Case | Schedule | Discriminates the lock? |
|---|---|---|
| L0 | SEC-004 controls C0, C1, C3, reused unchanged | no (controls) |
| L1 | **The SEC-004 schedule.** Old holder reserves K (lease 0), starts `complete(K, token=old)` in thread A, pauses in `_write` of COMPLETED (after its token check, so inside the lock in the fixed code). Thread B, a separate store object, runs `release(K)` then `reserve(K)`. Main waits `BLOCK_S` and records whether B finished. Then A resumes; both threads are joined. | **yes** |
| L2 | Late holder after release: old holder A is paused *before it takes the lock*. B releases and reserves K, then A resumes. | no (the late-event path still works with the lock) |
| L3 | Cross-process: a child process holds K's lock and signals; the parent starts `release(K)` in a thread and records whether it finished within `BLOCK_S`; then the child is told to let go. | **yes** |
| L4 | Crash: a child process takes K's lock and exits with `os._exit(0)` without unlocking; the parent's `release(K)` must then finish within `DONE_S`. | no (no stuck lock after a crash) |

## Predictions

| ID | Prediction (fixed code, normal run) | Pass criterion |
|---|---|---|
| P1 | L0 controls hold | C0, C1, C3 `pass` all true |
| P2 | **L1: no fresh reservation is overwritten.** B's `release()` stays blocked while A is paused; after A resumes, A writes COMPLETED with the old token; B's `release()` is then refused (`ValueError`, the key is COMPLETED) and B never reserves | B alive after `BLOCK_S`; final active token = old, state COMPLETED; B's error is `ValueError`; no new token issued; released history empty |
| P3 | L2: a late holder is recorded, not obeyed | final token = new, state IN_FLIGHT; exactly one `late_complete` with `late_token` = old |
| P4 | L3: the lock holds across processes | parent `release()` alive after `BLOCK_S`; finishes within `DONE_S` after the child lets go |
| P5 | L4: a dead holder leaves no stuck lock | parent `release()` finishes within `DONE_S` |
| P6 | **Sabotage (anti-vacuity):** with the lock replaced by a no-op, L1 reproduces SEC-004 (B finishes during the pause, a new token is issued, final token = old: overwrite) and L3 is not blocked. Probe exits 1 | both observed, exit 1 |
| P7 | `python -m pytest -q` passes on the CI matrix (Linux, macOS, Windows; Python 3.10, 3.12, 3.14) with the change | green |
| P8 | The SEC-004 probe, unchanged, refuses to run on the fixed module: `GATE=INCONCLUSIVE_SOURCE_CHANGED`, exit 2. This is the registered instrument doing its job (it is pinned to `071fc3fe…`), not a failure. SEC-004's schedule cannot even be completed against the fixed code: B blocks inside the lock while A waits for B. That is why L1 exists | output as stated |
| P9 | JG-2 P1 still passes (no new `hashlib.sha256(` site) | `python tools/jg2_probe.py` unchanged outcome |

**Verdict rule.** `FIXED_IN_TESTED_SCHEDULES` if P1–P5 hold in a normal run and P6 holds under `--sabotage`.
`NOT_FIXED` if L1 shows an overwrite in a normal run. `INCONCLUSIVE` if any wait exceeds `DONE_S`, a control
fails, or a pause point is never reached. Anything else is `UNEXPECTED` and is investigated without editing
this file. The probe prints one HELD/REFUTED line per prediction, `VERDICT`, and a `DIGEST` (sha256 of the
canonical results with tokens and timings removed). Exit 0 only on `FIXED_IN_TESTED_SCHEDULES` (and, once
pinned, the recorded digest); 1 otherwise.

## Known consequences, disclosed now

- `tools/sv_attack_001_probe.py` and `tools/sv_fix_001_probe.py` pin `idempotency.py`'s sha256 (`b8e92c6f…`).
  After this change they report their own precondition failure (INCONCLUSIVE) if re-run. They are historical
  records and are not run by CI; they are not edited.
- A lock file per key that has ever been used stays in the reservation directory.
- Operations on one key are now serialized; a holder paused inside one blocks the others on that key. That is
  the point, and it is also a liveness cost.

## Limits (what a pass would not show)

- Local filesystems only. `flock` on NFS/SMB and other network filesystems is not tested and may not hold.
- Advisory: only code going through `FileReservations` is serialized.
- The tested schedules are forced by hooks in one sandbox and on CI. It is not a proof of linearizability.
- It does not stop a late holder's *external* effect; that still needs a fence checked by the target (OBS-1).
- `complete()`/`unknown()` without a token still skip the token check (unchanged).
- Android/Termux on the S25 is **NOT VALIDATED** until run there.
- Self-tested: Claude registered, built and attacks this. No independent validation.

## Unrun next step (the door)

Run `tools/sec005_lock_probe.py` on the S25 under Termux (Android `flock` on app storage), and a many-thread
randomized-schedule stress run that is registered separately before it is written.

## Provenance (M13)

Claude (Anthropic, Opus 5.5) drafted the design, predictions and limits → human validation: not performed →
human editing/curation: direction by Chad Holland, 2026-11-02 → human responsibility: Chad Holland. Review
level: direction only.
