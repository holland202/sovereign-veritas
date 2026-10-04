# RP-1: relying-party replay vectors for a package-to-action mapping. Registration

Status: **REGISTERED, nothing run.** Committed alone, before `tools/rp1_vectors.py` exists.

Drafted by Claude (Opus 5.5) at Chad Holland's direction. Chad has not reviewed it line by line.

## Why

Joe Krausz, author of `draft-krausz-verification-state-03`, asked (email to Chad Holland, 2026-10-04) for a short
note covering how a package maps to an action, the witness's trust and scope, the retained-state assumptions
(including concurrent consumers and crashes), and accepting/refusing vector pairs. He framed it as input for a
relying-party replay section, not a commitment to any rule. He separated three things:

1. verifying a receipt again (not an error);
2. authorizing an action again (where an at-most-once policy belongs);
3. "latest in a witness log" (relative order, not wall-clock freshness).

This registration turns the note's claims into vectors run against the real code at `main` `16850f6`:
`tools/verify_package.py` (stateless), `tools/consumer.py` (state file: consumed digests and a witness anchor),
`tools/witness.py` (the author's append-only log). Two of the predictions are expected to show **gaps in this
repository**, read from the code but not yet run:

- `consumer.py` refuses a repeat **per package digest**. Nothing in `sv.package/0` names the action, so a second
  package for the same action has a new digest.
- `consumer.py` reads its state file and later rewrites it with no lock, and the rewrite is not atomic
  (`open(path, "w")`).

## Setup

- Packages from `tools/make_package.py --rounds 1000 --thermal-status normal --seed rp1` (decision ALLOW).
  Two runs with the same seed give the **same artifact and the same proposed action** (`measure` /
  `record_result`) but different digests, because the package records timing.
- Each vector writes its inputs (packages, witness log, consumer state) to `results/rp1/vectors/<id>/`, plus a
  `vector.json` with the commands, the expected exit codes and an expected substring. Unsigned throughout: the
  consumer accepts unsigned packages (IM M5, an open gap), and signing would need Chad's key.
- Linux container only. **Not run on the S25.**

## Predictions

| ID | Vector pair (accepting / refusing) | Prediction |
|---|---|---|
| P1 | **Re-verify.** `verify_package.py` on package A twice / on A with its decision changed | Both clean runs exit 0 with byte-identical output; the tampered one exits 1. Verifying again is not an error. |
| P2 | **Replay.** `consumer.py accept` A with a fresh state / the same command again | 0 then 1, reason contains `replay`; the state file's bytes are unchanged by the refusal. |
| P3 | **Same action, second package (expected gap).** A accepted, then B (same seed, same action) witnessed and accepted with the same state | B is **ACCEPTED** (exit 0). The consumer's at-most-once is per package, not per action. The refusing half of the pair is A presented again (exit 1). |
| P4 | **Relative order.** A, latest in the log, to a fresh consumer / A, after B is witnessed, to another fresh consumer that never acted on A | 0 / 1, `STALE`. Staleness is order across all of the author's packages, independent of whether A was ever acted on. |
| P5 | **Rollback and first use.** A consumer anchored on the 2-entry log, given the log cut to 1 entry (A latest again) / the same cut log to a fresh consumer | The anchored consumer refuses (exit 1, `rollback`); the fresh consumer **accepts** (exit 0). Retained state is what detects rollback; a consumer without it cannot. |
| P6 | **Concurrent consumers, forced interleaving.** Two `consumer_check` calls on one state snapshot (both read before either writes) / the second call given the first call's new state | Both interleaved calls return ok (the code has no lock); the sequential second call refuses. In-process, using the real function. |
| P7 | **Concurrent consumers, real processes.** 100 trials; in each, 8 `consumer.py accept` processes on the same package and the same fresh state file | At least 1 of 100 trials has 2 or more ACCEPTED. **May fail:** the read-to-write window is short. A failure would mean the window was not hit here, not that the consumer is safe (P6 shows the code has no lock). |
| P7c | **Anti-vacuity for P7.** Same harness, 20 trials, but each process runs the real consumer with a 0.2 s pause inserted between reading and writing the state | At least 18 of 20 trials doubled. If not, the harness cannot see a double and P7 says nothing. |
| P8 | **Crash during the state write.** State file cut to half its bytes (a torn `open("w")` write) / the intact file | Torn: exit 2 (`COULD NOT LOOK`) even for a package this consumer never saw: fail closed, no progress until a person repairs it. Intact: B accepted, exit 0. |
| P9 | **The runner can fail.** `--flip` inverts P2's expected exit codes | The runner reports P2 REFUTED and exits 1. |

## Outcome rules

- Trial counts are fixed above and are not changed after seeing results.
- A process that crashes for a reason other than a refusal is counted as an error, not as a refusal.
- A refuted prediction is kept and reported first, including if P3 or P7 come out "safe".

## What this does not test

- The executor side. RK-2 (`docs/RK2_RESULTS.md`) and MP-1 (`docs/MP1_PREREG.md`, Amendment 1) already measure a
  reserved idempotency key at execution. This note cites them; it does not rerun them.
- Signed packages, separate machines, network or Android storage.

## Next unrun test

Bind the action into the package (an action key fixed at intent and carried in `sv.package/1`) and check that the
consumer then refuses P3's second package. That is a schema change and is Chad's decision.
