# RK-2 registration: a reserved idempotency key, written before the effect (nothing built or run under this registration)

Status: registration only. Written 2026-10-04, before `sovereign_veritas/idempotency.py`, the workflow change and
`tools/rk2_probe.py` exist. Baseline: main 2c825b8 (457 passed, 1 skipped; contract digest `44823d0f...0628`).
Claude-assisted (Claude Opus 5.5). Chad Holland gave direction ("Yes proceed please"). He has not reviewed this
text line by line. The merge decision is his.

## Origin
RK-1 (PR #37) confirmed a retry with a fresh record_id repeats the effect, and that the ledger records FAILED where
the effect happened. The design here comes from two Moltbook comments the read-only scout found on 2026-10-04.
Both were written by AI agents, so they are leads, not evidence. `maies`: "the target persists the idempotency key
in a reservation record before it executes". `heejin`: the reservation carries `CLAIMED_IN_FLIGHT`, a key hash and
a lease TTL. The lease policy below differs from theirs: an expired lease is **not** taken over (fail closed).

## The change (to be built after this commit)
- `sovereign_veritas/idempotency.py`: two reservation stores with the same interface:
  - `MemoryReservations`, which is lock-protected and in-process;
  - `FileReservations`, which keeps one file per key hash, claimed with `O_CREAT|O_EXCL`. That create is atomic
    across threads and processes on one filesystem. A file that exists but cannot be read counts as IN_FLIGHT.
  - The states are IN_FLIGHT (with a lease expiry), COMPLETED and UNKNOWN. `reserve` refuses any key that
    already exists. An IN_FLIGHT key whose lease has expired becomes UNKNOWN and is still refused: an expired
    lease is never treated as permission to run again. `release(key, by, reason)` is the only way to run a key
    again. It is allowed only from UNKNOWN, it is meant for a human after investigating, and it is kept in the
    key's history.
- `EvidenceWorkflow(..., reservations=None)` and `run(..., idempotency_key=None)`:
  - With no key, behaviour is unchanged, byte for byte in the ledger.
  - A key with no store is refused before anything runs.
  - With a key, the workflow reserves just before `execute` (only on ALLOW). On success it marks COMPLETED,
    then writes the record. If the executor raises, it marks UNKNOWN and records `execution_status: UNKNOWN`
    (not FAILED). The key is stored in the record's metadata.
- The Gate is not touched. The package format and `tools/verify_package.py` are not touched.

## Cases (`tools/rk2_probe.py`, counting executor from XB-1/RK-1; all ALLOW, same action)
| case | what |
|---|---|
| A1 | timeout-after-effect, retry with the **same key** (same record_id) |
| A2 | timeout-after-effect, retry with a fresh record_id but the **same key** (RK-1's attack) |
| A3 | timeout-after-effect, retry with a fresh record_id **and a fresh key** (the stated limit) |
| A4 | A2 across processes: file store and file ledger, both rebuilt from disk for the retry |
| A5 | race (X4): two threads, same record_id, same key, executor delay 10 ms, 50 trials, memory store; and again with two separate `FileReservations` objects on one directory |
| A6 | X5: the effect succeeds and the record write fails (broken sink), then a retry with the same key through a working sink |
| A7 | lease expired: a key reserved with lease 0 and never completed (a crashed process), then a run with that key |
| A8 | lease live: a key reserved with lease 60 s, then a run with that key |
| A9 | after A1, `release(key, by="operator")`, then a run with the same key |
| A10 | a key given, but no store |

## Predictions (effects counted at the executor)
| ID | Prediction | conf. |
|---|---|---|
| R1 | A1: 1 effect. The retry is refused. The first record says `execution_status: UNKNOWN`, and the key state is UNKNOWN | 0.85 |
| R2 | A2: **1 effect.** The fresh record_id does not get past the key | 0.85 |
| R3 | A3: **2 effects.** A fresh key per attempt defeats it; this is stated, not hidden | 0.9 |
| R4 | A4: 1 effect | 0.8 |
| R5 | A5: 0 of 50 trials with 2 effects, for both stores (X4 had 2 effects before) | 0.8 |
| R6 | A6: 1 effect in total, the retry is refused, 0 records (X5 had 1 effect and 0 records with no protection against a retry) | 0.8 |
| R7 | A7: 0 effects, refused, state UNKNOWN | 0.85 |
| R8 | A8: 0 effects, refused, state IN_FLIGHT | 0.85 |
| R9 | A9: 2 effects in total. The second is run only after an explicit release, and the history shows the release | 0.8 |
| R10 | A10: 0 effects, refused before execution | 0.9 |
| R11 | **Anti-vacuity:** `--sabotage` swaps in a non-atomic memory store (check, 5 ms sleep, write). A5 then shows at least one trial with 2 effects, R5 fails, and the probe exits 1 | 0.8 |
| R12 | **Regression:** the existing 457 tests pass and 1 is skipped. New tests in `tests/test_idempotency.py` pass. XB-1 `--expect-fix` is 8 of 8 and RK-1 is 6 of 6 (the no-key path is unchanged, so RK-1's K2 still gives 2 effects). The contract digest is unchanged for kernel and verifier | 0.85 |

## What it cannot show
- That callers choose the key when the intent is created. RK-2 can only require it. A3 shows what happens
  otherwise.
- Behaviour on filesystems where `O_EXCL` is not atomic (some network filesystems), or across machines.
- A reservation and a ledger record are two writes, and they are not one transaction. A6 shows the reservation
  holding when the record write fails. A record without a completed reservation (a crash between the effect and
  `complete`) leaves the key IN_FLIGHT and then UNKNOWN. That is fail closed, but it needs a human to release it.
- Liveness. Keys stuck in UNKNOWN wait for a person. Nothing measures how often that would happen.
- Packages and the verifier don't carry reservations yet. `execution_status: UNKNOWN` is new, and the verifier
  has never seen it in a package.
- Container only. NOT VALIDATED on the S25 (the file store on Android storage is untested).

## Door (unrun)
RK-3: carry the reservation history in `sv.package` and make the verifier check that an ALLOW with an effect has
exactly one COMPLETED reservation for its key.
