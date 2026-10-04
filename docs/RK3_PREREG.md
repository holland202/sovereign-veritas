# RK-3: a lost COMPLETED, a late holder, and a fixed lease in the reservation store. Registration

Status: **REGISTERED, nothing run under it.** Committed before any change to `sovereign_veritas/idempotency.py`
or `workflow.py`, and before `tools/rk3_probe.py` exists. Baseline `main` `1307da7`.

Drafted by Claude (Opus 5.5) at Chad Holland's direction. Chad has not reviewed it line by line.

## What was found (before this registration; not registered)

On 2026-10-04 a separate Claude session, asked to read the repository as a hostile Hacker News reader and to try
to get two external effects for one idempotency key, wrote two scripts outside the repository. They are kept
unedited in `results/rk3/independent_review/` (sha256 `5ed84c6b…a7ab` `lease_probe.py`, `10b32b16…86d9` `e2b.py`).
I reran both on `1307da7`. Output, verbatim:

```
t=31.0s  B retry: ReservationRefused: idempotency key 'K-e1' is UNKNOWN: refused before execution
t=31.0s  operator sees state=UNKNOWN downstream effects=0 history=['IN_FLIGHT/None', 'UNKNOWN/lease_expired']
t=31.0s  C after release: None effects=1
t=34.0s  A finished: None  EFFECTS FOR ONE KEY = 2
final state COMPLETED history ['IN_FLIGHT', 'COMPLETED', 'COMPLETED']
E3 torn file state: IN_FLIGHT history: []
E3 release: release is allowed only from UNKNOWN: 'K-e3'
trials=300 final_state_UNKNOWN_after_complete=181 COMPLETED_missing_from_history=181
```

(The reviewer's own run of `e2b.py` gave 149 of 300. Its in-process variant, `lease_probe.py E2`, gave 0 of 300 in
my rerun.)

Three findings:

- **E1. Release while the holder still runs gives two effects.** Holder A's action outlives the lease, which
  `run()` cannot set (30 s default, `workflow.py:249`). The key reads UNKNOWN. An operator checks, truthfully sees
  no effect yet, releases, and C runs. Then A's action lands. Two effects for one key. Then A's late `complete()`
  writes over C's entry, so the history shows no double.
- **E2. A late `complete()` can be lost.** `reserve()` on an existing, expired key reads the entry and writes it
  back as UNKNOWN (`lease_expired`). That read-modify-write races a `complete()` landing at the same moment. The
  later write wins, so COMPLETED can vanish: 181 of 300 trials above, with three processes deliberately hammering
  that window. The key then looks like an uncertain outcome that a person might release, which leads to E1 with no
  sign anything went wrong. This is the "suspected lost update" MP-1 listed as unrun.
- **E3. An empty reservation file blocks its key for ever.** A crash between the exclusive create and the write
  leaves a file that reads IN_FLIGHT with an infinite lease, and `release()` refuses it. Liveness only, no double.

## What changes (design, fixed before the code)

1. **`reserve()` never writes to an existing key.** It reads, computes the effective state (an expired IN_FLIGHT
   is UNKNOWN, as before), and refuses. Expiry becomes derived, not stored. This removes E2's competing write.
   `release()` records the effective state it released from, so the history still says the lease expired.
2. **Holder token.** `reserve()` returns a random token that it stores in the entry. `complete()` and `unknown()`
   take an optional token; the workflow always passes it. If the entry's token differs (the key was released and
   reserved again) or the entry is gone, the call **does not touch the entry**. It appends one JSON line
   (`late_complete` / `late_unknown`, with both tokens) to an append-only side file, readable through
   `late_events(key)`. Calls without a token keep today's behaviour.
3. **`run(lease_s=...)`.** The lease is passed through to `reserve()`. The default stays 30 s.

What this does **not** change: E1's second effect. The store cannot stop an action that is already running. That
needs the target of the action to check a fence, which is what the OBS-1 interface (frozen at `04bca2d`) tests.
E1 becomes a published limit, and RK-3 only makes it visible. E3 is not addressed; it becomes a published limit.
No locks are used, because the test matrix includes Windows.

## Predictions

| ID | Prediction |
|---|---|
| Q1 | **E2 closed.** The separate-process harness (3 hammer processes, `complete()` within ±0.5 ms of expiry, 300 trials, same as `e2b.py`) on the changed store: **0 of 300** trials lose COMPLETED. |
| Q1c | **Anti-vacuity for Q1.** The same harness, in the same run, against `main` `1307da7`'s store (loaded from `git show`): **at least 1 of 300** trials loses COMPLETED. If not, Q1 says nothing. |
| Q2 | **E1 still doubles, but visibly.** E1 through `run()` with `lease_s=1` and a 2 s holder: **2 effects** (unchanged, a published limit); C's entry history is exactly `IN_FLIGHT, COMPLETED`; `late_events` holds exactly one `late_complete` whose token is A's. |
| Q3 | **A longer lease prevents the E1 path.** With `run(lease_s=5)` and a 2 s holder: at 1 s the key is IN_FLIGHT and `release()` is refused; at the end there is **1 effect** and the key is COMPLETED. |
| Q4 | **No regression.** `tools/rk2_probe.py` 10 of 10 and `--sabotage` exits 1; `tools/mp1_probe.py` 5 of 5; the full test suite passes. |
| Q5 | **Selftest of the probe.** The probe's Q2 check fails (exit 1) if the late-event log is bypassed (`--sabotage`: `complete()` called without a token, today's behaviour), because C's history then gains a second COMPLETED. |

Trial counts are fixed above. A refuted prediction is kept and reported first.

## Limits

Linux container only, one local filesystem. **Not run on the S25.** The timing window in Q1 is deliberately
widened; the rate says the race exists, not how often it happens in use. E1 and E3 are not fixed by this change.

## Next unrun test

E1 against a fenced target: the OBS-1 round-one cases, once Amos Tipton's cases are committed.
