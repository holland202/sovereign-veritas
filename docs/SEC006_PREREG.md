# SEC-006: randomized multi-process stress test of the SEC-005 lock — preregistration

**Status: REGISTERED, UNRUN, NO CODE.** Committed alone, before the harness exists. Registered 2026-11-06 by Claude
(Anthropic, Opus 5.5) at Chad Holland's direction. Review level: direction only. This is the "many-thread
randomized-schedule stress run, registered separately" named as the next step in
[`SEC005_RESULTS.md`](SEC005_RESULTS.md). No change to `sovereign_veritas/` is planned.

## Question

SEC-005 showed the lock closes the SEC-004 race in **forced** schedules. Under **random** schedules with several
processes and keys, does any operation sequence still let a holder's write replace a newer reservation?

## Design

- **Arms:** LOCK (the code as it is, `idempotency.py` blob `8013269…`) and NOLOCK (`FileReservations._key_lock`
  replaced by a no-op in every worker process). Same seeds, same workload, same delay injection in both.
- **Workload:** `P = 6` worker processes share one reservation directory with `K = 8` keys. Each worker runs
  `M = 250` operations chosen by its own seeded RNG with these weights:
  - `reserve(key, lease_s=0)`: 0.35. A lease of 0 makes the entry UNKNOWN at once, so it can be released.
  - `unknown(key, why, token=own current token)`: 0.20
  - `complete(key, token=own current token)`: 0.05
  - `complete(key, token=an older token this worker once held)`: 0.10 (the stale holder)
  - `release(key, by, reason)`: 0.30
  
  `ReservationRefused` from `reserve` and `ValueError` from `release` are expected outcomes and are counted, not
  errors.
- **Delay injection (both arms):** `FileReservations._write` is wrapped to sleep a uniform random 0–3 ms (worker
  RNG) before the real write. In the LOCK arm this happens inside the lock. It widens the window between a holder's
  check and its write; it is the same in both arms, so it cannot by itself produce a difference.
- **Trials:** registered seeds 1–20 (one trial per seed, both arms). Dev seeds 101–103 may be used while building
  the harness and are reported separately; they are never scored (C-HOLDOUT).

## Oracle (no timing needed)

Every successful `reserve` returns a token, which its worker logs. Every entry a key ever had ends either as the
active file or as a `*.released-*.json` file, and each such file records the entry's token. So for each key:

> **I1:** the multiset of tokens found in the key's active file plus its released files equals the set of tokens
> granted for that key, **each exactly once**.

An overwrite of a fresh reservation (SEC-004) breaks I1: the fresh token disappears from every file, and the stale
token appears twice. I1 is checked per key, and a trial counts a violation if any key breaks it. Every file is
read after all workers have exited.

## Predictions

| ID | Prediction | Pass criterion |
|---|---|---|
| P1 | **LOCK: no violations.** | I1 holds for every key in all 20 registered trials |
| P2 | **NOLOCK: the oracle can see the bug (anti-vacuity).** | I1 broken in at least 1 of the 20 trials |
| P3 | LOCK: no hangs or unexpected errors | every worker exits 0 within 120 s per trial; no exception other than the two expected ones |
| P4 | LOCK: the workload actually exercises the race path | in total over 20 trials, at least 100 stale-token `complete` calls are recorded as late events, and at least 100 releases succeed |

**Verdict rule.** `NO_VIOLATION_IN_TESTED_SCHEDULES` if P1–P4 hold. `VIOLATION` if P1 fails, which is a security
finding, kept and reported first. `INCONCLUSIVE` if P2 or P4 fails (the test could not see the bug or did not
exercise it) or any trial times out. The harness prints HELD/REFUTED per prediction, counts per arm, and a DIGEST of
the per-trial violation counts and operation counts (no tokens, no timings). Exit 0 only on
`NO_VIOLATION_IN_TESTED_SCHEDULES`; `--sabotage` disables the lock in the LOCK arm too and must exit 1.

## What a pass would not show

- Correctness for schedules this generator does not produce. Random schedules with injected delays are a sample,
  not a proof.
- Network filesystems; Windows (unless run there); devices other than where it runs.
- Anything about `MemoryReservations` or `workflow.py`.
- Independent validation: Claude registered, builds, runs and judges this.

## Pre-mortem (what could make this misleading)

- **The oracle could be blind.** P2 guards this: if NOLOCK never breaks I1, the run is INCONCLUSIVE, not a pass.
- **The delays could hide a different race,** for example one that needs no delay. Delays only widen windows; they
  do not remove any interleaving the OS could produce. But the sample is still what it is.
- **The workload could rarely reach the race** (for example, keys stuck COMPLETED). P4 sets a floor on stale
  completions and releases.
- **Timeouts on a slow CI machine** would make the run INCONCLUSIVE, not a pass.

## Unrun next step (the door)

Run this harness on the S25 under Termux and on a Windows CI leg.

## Provenance (M13)

Claude (Anthropic, Opus 5.5) designed and registered this → human validation: not performed → human
editing/curation: direction by Chad Holland, 2026-11-06 → human responsibility: Chad Holland. Review level:
direction only.
