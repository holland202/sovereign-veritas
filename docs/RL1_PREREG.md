# RL-1 — Does a `release()` record show who released the key, or only what the caller wrote?

**Status: REGISTERED, UNRUN.** Committed before any probe exists. Nothing built.
Registered 2026-10-05 by Claude (Sonnet 5.5) at Chad Holland's direction. Review level: direction only. Chad
approved the scope; he has not read this registration line by line.

## Origin

`sovereign_veritas/idempotency.py` documents `release(key, by, reason)` as "the key may run again; allowed only
from UNKNOWN, meant for a human after investigating" (module docstring, line 8). The method records `by` and
`reason` in the key's history. Reading the code (lines 114-121 `MemoryReservations`, 210-217 `FileReservations`)
shows `by` is stored exactly as the caller passed it. Nothing checks that the caller is a person.

The question was prompted by an outside source. A public article on permission boundaries in a coding agent
(Vinoth Govindarajan, *The Agent Stack*, "OpenCode Architecture - Part 3: Tool Execution and Permission
Boundaries") showed that a prompt labelled "ask" can be answered automatically by the client, and a commenter
named Mira asked "who, if anyone, actually read the diff". That is the origin of the question only. Neither has
reviewed or endorsed this project, this registration or any result, and nothing here is a claim about their
software.

## The claim being tested (stated so it can be wrong)

**A `release()` history entry cannot be told apart from a human release by anything the library records.** Two
releases that pass the same `by` and `reason` strings produce entries that differ only in the timestamp,
whether the caller is a person, a script, or the system's own reconciliation code.

This is a statement about what the library records. It is not a claim that anyone has exploited it, and not a
claim that the library should authenticate people: that would be a design decision with a cost (see Doors).

If `release()` rejects an unrecognised `by`, or the entry carries a field that differs by caller kind, the claim
is refuted.

## Scope

Both reservation stores in `sovereign_veritas/idempotency.py` (`MemoryReservations`, `FileReservations`), the
real classes, imported not copied. No new code in the kernel. Linux container, Python 3.13. NOT VALIDATED on the S25.

## Cases

| ID | Case |
|---|---|
| R0 | anti-vacuity: a key that is not UNKNOWN is refused by `release()` (the method can refuse something) |
| R1 | a script calls `release(key, by="human:chad", reason="checked downstream")` on a key in UNKNOWN |
| R2 | a second script calls `release(key2, by="human:chad", reason="checked downstream")` the same way, but from a thread started by an automated loop |
| R3 | the same two calls against the other store class |

## Predictions

- **L1.** R1 and R2 are accepted (no exception) in both store classes. `by` is stored verbatim.
- **L2.** The RELEASED history entry has exactly the keys `at`, `to`, `by`, `why`. Entries from R1 and R2 are
  equal after removing `at`. There is no field for caller kind, credential or evidence, in either store class.
- **L3 (recorded, not predicted).** Before registering, a search of non-test code found three call sites that
  call `release()` automatically with `by="system"`, all in `tools/obs1_system.py` (lines 90, 106, 139). That is
  an observation made before this registration, so it is listed as context and not scored as a prediction. The
  probe will recount it with an AST scan and print the number.
- **L4 (anti-vacuity).** R0 is REFUSED in both store classes. This shows the probe's `release()` calls can fail.

## Controls and sabotage

- `--sabotage` replaces `release()` in both classes with a version that raises unless `by` is in `{"operator"}`.
  Under it, **L1 must be REFUTED and the exit code must be 1 because of L1**. The harness exits 1 under
  sabotage only if L1 is the refuted prediction. Reason: in another repository's probe (skn-v1-, K8), the
  sabotage step exits 1 even when the sabotage does nothing, because a different prediction is already refuted.
  This probe is written so that cannot happen here.
- A no-op control: running the sabotage path with the replacement being the unmodified method must give L1
  HELD and exit 0.

## Limits

- The probe shows what the library records. It does not show who really called it, and nothing it can print
  could.
- R1 and R2 run in one process. The "automated loop" is a stand-in for an automated caller, not a real
  deployment.
- This is not a finding about OBS-1. Its automated releases follow a stated reconciliation rule and carry a
  reason. The question here is only whether the record could distinguish them from a human release.

## Doors (unrun, and design decisions for Chad)

- Record a caller kind that the library sets from a verified credential, not from a string the caller supplies.
- Or: record `by` as unverified in the entry, so a reader does not mistake it for attestation.
- Or: change the docstring so it no longer says "meant for a human".
- Even a signed release shows that a key was used, not that a person was present. A script holding the key looks
  the same. Who holds the key is a separate question the library cannot answer.
- Nothing here is measured on the S25.
