# MP-1 — one key, many processes: does the file reservation store hold? (registration)

Status: **Registered, UNRUN.** Committed alone, before `tools/mp1_probe.py` exists. Results go in a dated amendment;
this text is not edited after commit.

Registered 2026-10-04 on top of `2b7f8a2` (PR #38, RK-2, not merged). Drafted by Claude (Opus 5.5) at Chad
Holland's direction. Chad has not reviewed it line by line.

## Why

RK-2 measured 0 of 50 doubled races for `FileReservations`, but every race ran as **threads in one process**, and
its sabotage control covered only the memory store, so nothing showed that race harness could ever double a
file store. The public Round 2 challenge (Track A) names exactly this as the weak spot, and two outside reviews
(2026-10-04, AI-generated, provided by Chad) ranked a multi-process race first. `FileReservations.reserve()`
claims with `os.open(O_CREAT | O_EXCL)`, which the docstring says is atomic "across threads and processes on one
local filesystem". This tests that claim and nothing wider.

## Setup

- Each worker is a **separate OS process** (`subprocess`, its own Python interpreter), running
  `EvidenceWorkflow.run(..., idempotency_key=K)` with its own `FileReservations(DIR)` on a shared directory and its
  own in-memory ledger.
- All workers in a trial wait for one shared start instant (wall clock, set by the parent ~1 s ahead), then call
  `run()` together.
- **Effects are counted outside the system**: the executor appends one line to an effect log opened with
  `O_APPEND` before returning. The parent counts lines after all workers exit. The reservation store and the
  ledger are not used to count.
- Local filesystem: the container's `tempfile` directory. Android storage and network filesystems are out of
  scope here (left unrun).

## Predictions

- **P1 — race, real store.** With the unchanged `FileReservations`, for N = 2 (200 trials), N = 8 (100 trials) and
  N = 32 (30 trials): **0 trials with more than one effect**, and every trial has exactly one effect.
- **P2 — anti-vacuity.** The same harness with a SABOTAGE file store (check `exists()`, sleep 5 ms, then create
  without `O_EXCL`) shows **at least one trial with two or more effects** at N = 8. If P2 fails, the harness cannot
  detect a doubled race across processes and P1 is void.
- **P3 — killed before the effect.** A worker reserves the key, then is killed with SIGKILL while its executor
  sleeps before writing the effect. Then 8 workers retry the same key: **0 effects in total**, and all 8 report
  refused before execution.
- **P4 — killed after the effect.** A worker writes the effect, then is SIGKILLed before `run()` returns. Then 8
  workers retry: **exactly 1 effect in total**, and all 8 report refused.
- **P5 — a fresh key still runs.** Control for P3/P4: one worker with a different key after the kills writes one
  effect. If it does not, the refusals in P3/P4 may mean the store or harness is broken rather than holding.

## Outcome rules

- Any trial with two or more effects under the real store is a **break of the RK-2 claim**, kept and reported.
- A worker that crashes for a reason other than a refusal is reported as an error, not counted as a refusal.
- Trial counts above are fixed. They are not increased or decreased after seeing results.

## Left unrun

- Android shared storage (`~/storage/shared`, FUSE) and Termux's own folder on the S25.
- A holder whose lease expires while it is still running, racing a late `complete()` against the expiry write
  (a suspected lost update, from reading `FileReservations._move` and `reserve()`; not tested here).
- Network filesystems and separate machines.

---

## Amendment 1 — 2026-10-04 (UTC), the registered run

Nothing above this line was edited. Probe `tools/mp1_probe.py` at `ce5fee4`, run once with the registered trial
counts. Linux x86_64 container, 2 CPUs, Python 3.13.16. **NOT VALIDATED on the S25.**

Before the registered run, one smoke run (`--quick`, a twentieth of the trials) found a **probe bug**: the kill
cases started their holder process without its mode, so it finished before it could be killed and the probe
crashed (`ProcessLookupError`). Fixed in `ce5fee4` before the registered run. No prediction or trial count changed.

| | Result |
|---|---|
| **P1** race, real store | **HELD.** N=2: 0 of 200 trials doubled. N=8: 0 of 100. N=32: 0 of 30. Every trial had exactly one effect; no worker errors. |
| **P2** anti-vacuity | **HELD.** The sabotage file store doubled 100 of 100 trials at N=8. The harness can see a doubled race across processes. |
| **P3** killed before the effect | **HELD.** 0 effects; all 8 retries refused before execution. |
| **P4** killed after the effect | **HELD.** 1 effect; all 8 retries refused before execution. |
| **P5** fresh-key control | **HELD.** A different key ran after each kill case. |

Output, verbatim:

```
P1 real     N=2   trials=200  doubled=0 zero=0 errors=0
P1 real     N=8   trials=100  doubled=0 zero=0 errors=0
P1 real     N=32  trials=30   doubled=0 zero=0 errors=0
P2 sabotage N=8   trials=100  doubled=100 zero=0 errors=0
P3 killed before effect  marker=True same-key effects=0 retries=['refused']x8 fresh-key=ran
P4 killed after effect   marker=True same-key effects=1 retries=['refused']x8 fresh-key=ran

  P1  HELD
  P2  HELD
  P3  HELD
  P4  HELD
  P5  HELD
VERDICT  5 of 5 as registered
```

**What this shows:** on one local Linux filesystem, `O_CREAT|O_EXCL` held one key to one effect across up to 32
separate processes, and a killed holder left the key refused rather than re-runnable. **What it does not show:**
Android storage (Termux folder or FUSE shared storage), network filesystems, separate machines, and the
lease-expiry/late-complete race listed as unrun. P3 and P4 also show the cost already stated in RK-2: after a
crash the key stays blocked until a person releases it.
