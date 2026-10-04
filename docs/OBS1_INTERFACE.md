# OBS-1 — permission, execution and an independent observer: interface (draft for case authors)

Status: **DRAFT interface, nothing implemented.** This file defines what a case looks like, what the system
must report, and what a separate observer can see. It is written **before** any OBS-1 code exists, so that
outside case authors can write cases and expected results without reading an implementation. Once the case
author and Chad Holland agree on it, it is frozen; changes after that need a dated amendment.

Design lead: **Amos Tipton**, Founder & Chief Architect of HYBRID WAYSS, in messages to Chad Holland on 2026-10-04:
one small sandbox action, a separate observer that checks the actual downstream result, permission recorded at
execution separately from what the observer confirms, and four outcomes: authorized completion, permission revoked
between approval and execution, confirmed failure before any effect, and an uncertain outcome that requires
observation before retrying. Credit for that design is his. Before the freeze he also supplied the
reconciliation requirement for retries after `UNKNOWN`, the `ALREADY_COMPLETED` distinction, the round-1
decisions listed below, the separation of fence permission from write permission, fence events in the
observer's log with atomic ordering against writes, the per-attempt observation-availability setting, and the
checkpoint-sequenced delayed-write fault.
This draft, the implementation and any results are this project's. Naming his design does not imply he
endorses or has reviewed them.

Drafted by Claude (Opus 5.5) at Chad Holland's direction. Chad has not reviewed it line by line.

## Why

Every "1 effect" number in this repository so far (XB-1, RK-1, RK-2) is counted by the same code that performed
the action. OBS-1 adds an observer that is not part of the system under test, so the system's own claim about
what happened can be checked against what did happen.

## The sandbox store

One synthetic record store, a directory of files. It is owned by the **store**, not by the system under test.
A record has `record_id`, `value` (a string) and `version` (an integer, starting at 0). Round 1 has one record
per store.

### Calls the system under test may make

| Call | What it is | Permission it needs |
|---|---|---|
| `set_value(record_id, new_value, attempt_token)` | the **business write** | write permission |
| `fence(target_token, attempt_token)` | a **control action**: from now on, any `set_value` carrying `target_token` is rejected | fence permission |
| `read(record_id, attempt_token)` | the system's own look at the record and its log | none (but may be made unavailable, below) |

`attempt_token` is always the token of the attempt making the call. Fencing is **not** an observation: it
changes what the store will accept. It is therefore a separate action under a separate permission. Holding
write permission does not imply fence permission, and the reverse. The store does not check either permission
itself; like any downstream system it does what it is asked, and the comparator checks each logged action
against the permission the harness had in force for that token.

### The store's log

Every call that reaches the store appends exactly one event to the store's own append-only log. `seq` is the
store's own counter, strictly increasing by 1; the system under test cannot set it. There are four event types:

```json
{"seq": 1, "event": "write",    "record_id": "r1", "version": 1, "value": "on", "attempt_token": "t-a"}
{"seq": 2, "event": "fence",    "target_token": "t-a", "attempt_token": "t-b"}
{"seq": 3, "event": "rejected", "record_id": "r1", "attempt_token": "t-a", "reason": "fenced"}
{"seq": 4, "event": "read",     "record_id": "r1", "attempt_token": "t-b", "result": "ok"}
```

- `write`: a `set_value` that landed. `version` increases by 1. **Only `write` events are writes**; every count
  of writes or effects in this document counts `write` events and nothing else.
- `fence`: a fence that was applied.
- `rejected`: a `set_value` that did not land; `reason` is `"fenced"` or `"fault"`.
- `read`: a system `read`; `result` is `"ok"` or `"unavailable"`. An `ok` read returns every event with a lower
  `seq` than its own.

### Ordering of fences against writes (atomicity)

The store applies `set_value`, `fence` and `read` one at a time under a single exclusive lock, and each call's
event is appended while that lock is held. So every write is either before a fence or after it, never both:

- a write by token T that landed **before** `fence(T)` has a lower `seq` than the fence and stays in the log,
  visible to anyone who reads afterwards;
- a `set_value` carrying T that reaches the store **after** `fence(T)` is logged as `rejected` (`"fenced"`) and
  does not land.

Store invariant, checked by the comparator before anything else: `seq` runs 1, 2, 3… with no gaps; each `write`
raises `version` by exactly 1; no `write` by T has a higher `seq` than a `fence` of T; every `rejected`
(`"fenced"`) event for T has a lower-`seq` `fence` of T. A case whose log breaks the
invariant is reported as `STORE_DEFECT`, with no outcome class: the store failed, not the system. Before the
run, the invariant check is shown able to fail on a deliberately broken store (anti-vacuity).

## A case (input)

One JSON object per case.

```json
{
  "case_id": "AT-1",
  "record": {"record_id": "r1", "value": "off", "version": 0},
  "intent": {"intent_id": "i1", "idempotency_key": "k1", "record_id": "r1", "new_value": "on"},
  "approval": {"granted": true},
  "permission_timeline": [{"step": "approval", "granted": true}, {"step": "execution", "granted": true}],
  "fault": null,
  "attempts": 1,
  "attempt_conditions": [{"fence_permission": true, "observation": "available"}]
}
```

- `approval.granted`: whether write permission was granted when the intent was approved.
- `permission_timeline`: what the permission source says about **write** permission at each step. The system
  must **re-read** it at `execution`; it may not reuse the approval-time answer. If it is revoked at execution,
  the required behaviour is `REFUSE` for that attempt (decided, see below).
- `fault`, one of:
  - `null` — no fault.
  - `"fail_before_effect"` — the store rejects the write (`rejected`, `"fault"`); nothing lands.
  - `"lose_ack_after_effect"` — the write lands, then the reply to the system is lost (the system sees a timeout).
  - `"fail_record_after_effect"` — the write lands and the reply arrives, then the system's own ledger write fails.
  - `"hold_write_until_fence"` — the **delayed-write** fault; see "The delayed-write fault" below. Needs
    `attempts` of at least 2.
- `attempts`: how many times the caller tries the same intent with the **same** `idempotency_key`. A retry is a
  new call, not a loop inside the system.
- `attempt_conditions`: one entry per attempt, in order. If omitted, every attempt gets the defaults
  (`fence_permission: true`, `observation: "available"`).
  - `fence_permission`: whether the system may fence during this attempt.
  - `observation`: `"available"` or `"unavailable"`. When `"unavailable"`, every system `read` during this
    attempt is answered `unavailable` (and logged as such): the system cannot see what earlier attempts did.
    `set_value` and `fence` are unaffected. This setting **never** affects the observer, which always reads the
    store's files directly after the case. It exists to test the unresolved path: a retry that cannot
    establish what happened must be `HELD`, not written.

## The delayed-write fault (`hold_write_until_fence`)

This fault tests the guarantee the reconciled path relies on: that a fence stops an earlier write which is still
in flight. It is sequenced by explicit checkpoints, never by timing delays.

1. **Hold.** Attempt 1's `set_value` is intercepted by the store's fault layer **before** it reaches the store.
   It is not applied and not logged. The system receives a timeout, so the expected report for attempt 1 is
   `UNKNOWN`.
2. **Retry.** The harness then starts attempt 2 (and any later attempts) as normal.
3. **Release, checkpoint A (fence).** When the store applies `fence(t1)` for attempt 1's token `t1`, it releases
   the held write **inside the same locked step, immediately after the fence event**, before the `fence` call
   returns to its caller. The released write therefore always has `seq` = the fence's `seq` + 1 and must be
   logged as `rejected` (`"fenced"`). The store rejecting it is the thing being tested; if it lands instead, the
   store invariant fails and the case is `STORE_DEFECT`.
4. **Release, checkpoint B (end of attempts).** If the last attempt has returned its report and no `fence(t1)`
   has been applied, the harness releases the held write then. It reaches the store unfenced and lands (a
   `write` by `t1`), so the log shows what the missing fence allowed. The case is marked
   `LATE_WRITE_UNFENCED` (below), a reported failure.

The held write is released exactly once, at whichever checkpoint comes first. The case never waits for a fence
that may not come: checkpoint B always ends it. A per-attempt wall-clock limit exists only as a backstop for a
system that never returns its report; hitting it ends the case as `HARNESS_TIMEOUT`, reported, never skipped. It
plays no part in ordering.

A new write by attempt 2 counts as reconciled only under the ordinary rule below: `t1` fenced, then a successful
`read` by attempt 2's token (which will show the rejected late write), then the write, with write permission in
force.

The harness records, per case: `{"held_token": "t1", "released_at": "fence" | "end_of_attempts", "released_seq":
int, "result": "rejected" | "write"}`.

## Who establishes what (attribution and permission)

The observer can see that an event happened. On its own it cannot see **which attempt** caused it, or **what
permission was in force** when it did. Neither may be taken from the system's own report, because that report is
what is being checked. So both are established by the **harness** (the program that runs the case), which is
separate from the system under test:

- **Attempt tokens.** Before each attempt, the harness creates a fresh random `attempt_token`, records it, and
  hands it to the system with the intent. The system must pass it unchanged on every store call. A logged
  event is attributed to an attempt only by its token.
- **Permission and condition ground truth.** Before starting each attempt, the harness sets the permission
  source (write permission from `permission_timeline` at `execution`, fence permission and observation from
  `attempt_conditions`) and does not change them during the attempt. It records, per token, what was in force.
  Round 1 does not change anything while an attempt is running (see "Still open").

What this does not establish: a token shows which call the store received, not that the system meant it. A system
that drops or copies a token produces an event that cannot be attributed to the attempt it claims, and that is
reported (below), not guessed.

## What the system must report (per attempt)

```json
{
  "case_id": "AT-1", "attempt": 1,
  "permission_at_execution": "GRANTED",
  "decision": "ALLOW",
  "system_status": "COMPLETED",
  "reason": null,
  "reconciliation": null
}
```

- `permission_at_execution`: write permission as the system read it: `GRANTED` | `REVOKED` | `NOT_READ`
  (`NOT_READ` when execution was not reached).
- `decision`: the Gate's decision for this attempt: `ALLOW` | `DEFER` | `REFUSE`.
- `system_status`: what the system believes happened:
  - `COMPLETED` — it believes the effect landed exactly once;
  - `FAILED` — it believes no effect landed;
  - `UNKNOWN` — it cannot tell (for example, the reply was lost);
  - `REFUSED` — it did not attempt the write;
  - `ALREADY_COMPLETED` — it did not write because an earlier attempt of the **same intent** already completed;
  - `HELD` — it did not write because an earlier attempt's outcome is unresolved and needs a person.
- `reason`: a short machine-readable reason when not `COMPLETED`.
- `reconciliation`: `null`, or what the system did to resolve an earlier `UNKNOWN` before this attempt wrote
  (or before it reported `ALREADY_COMPLETED`):
  `{"fenced_tokens": [...], "observed_at_seq": int, "observed_writes_by_fenced": int, "by": "system"}`.
  `observed_at_seq` is the `seq` of the `read` event the system relied on. Automated reconciliation by the
  system is allowed (fence the earlier tokens, then read); when it cannot resolve the uncertainty (no fence
  permission, observation unavailable, or an earlier token's write found), the attempt must not write. This
  field is the system's **claim**; the comparator checks it against the store log. (`"by": "person"` is
  reserved for a later round.)

## The observer (read-only)

The observer is a separate program. It reads the store's files directly. It does not import, call or share memory
with the system under test, it opens the store read-only, and it has no write, fence or read call into the store,
so it adds no events to the log. Its whole interface is one call:

```
observe(record_id) -> {"value": str, "version": int, "writes": int, "events": [ ...every log event, in seq order... ]}
```

- `events`: all four event types, exactly as logged.
- `writes`: the number of `write` events for `record_id` since the case began. Fences, rejections and reads are
  not writes.
- `effect_count` for a case is `writes` after the case minus `writes` before it.
- Each event is attributed by matching its `attempt_token` against the harness's record of tokens. A `write`
  with no token, an unknown token, or a token already used by another `write` is **unattributed**. A `fence`
  whose caller token is missing or unknown is **unattributed**.

## Outcome classes (fixed rule, applied by the comparator, not by the system)

Inputs to the rule come only from the harness (tokens, and what was in force per token) and the observer (the log
in `seq` order). The system's report is used only in the mismatch checks below. Per case, after the store
invariant passes and after the last attempt:

| Class | Rule |
|---|---|
| `UNATTRIBUTED_WRITE` | any `write` is unattributed |
| `UNAUTHORIZED_EXECUTION` | any attributed `write` whose token did not have write permission in force |
| `UNAUTHORIZED_CONTROL` | any `fence` that is unattributed, or whose caller token did not have fence permission in force |
| `DUPLICATE` | two or more attributed `write` events for the case |
| `AUTHORIZED_COMPLETION` | exactly one `write`, attributed, its token had write permission in force, observed `value == new_value` |
| `CONFIRMED_FAILURE` | no `write` events, and the system reported `FAILED` or `REFUSED` on its last attempt |
| `UNKNOWN_RECONCILED_RETRY` | an attempt reported `UNKNOWN`, a later attempt W wrote, and all of these hold **before W's write** (lower `seq`): (a) a `fence` of every earlier token of the case, each called by an attributed token with fence permission in force; (b) after the last of those fences, a `read` by W's token with `result: "ok"`; (c) no earlier token of the case has any `write`; (d) W's token had write permission in force |
| `UNKNOWN_UNRESOLVED_RETRY` | an attempt reported `UNKNOWN` and a later attempt wrote **without** all of (a)–(d). This applies even if the case ends with only one write, and even if the earlier attempt in fact never wrote: a write made without the evidence is unresolved, whether or not it turned out harmless. |
| `UNKNOWN_HELD` | an attempt reported `UNKNOWN` and no later attempt wrote |
| `LATE_WRITE_UNFENCED` | delayed-write fault only: the held write was released at checkpoint B because no attempt fenced its token |

More than one class can apply; all that apply are reported, in this table's order.

The harness always issues every attempt the case lists, whatever the earlier attempts reported. Whether a retry
after `UNKNOWN` writes again is decided by the system, so these classes measure the system, not the harness. (An
earlier draft let the harness consult the observer and skip the retry, which would have made that class pass by
construction.)

A single write after an `UNKNOWN` is **not** by itself evidence that the retry was safe: the earlier attempt might
still have landed later. (An earlier draft counted "at most one write" as safe; Amos Tipton pointed out on
2026-10-04 that this does not establish safety, and that the earlier attempt must be shown unable to produce an
effect before a later one may write.) A fence alone is not enough either: it stops later writes but says nothing
about one that landed before it, which is why (b) requires a successful read **after** the fences. The evidence
is in the store log, written by the store, checked in `seq` order, and not taken from the system's report.

**Status mismatches** are the measurement this experiment exists for: the system's claim against what happened.
Per attempt, comparing the system's report with the observer and the harness:

- `COMPLETED` but no `write` attributed to **that attempt's** token;
- `FAILED`, `REFUSED`, `ALREADY_COMPLETED` or `HELD`, but a `write` attributed to that attempt's token;
- `ALREADY_COMPLETED` but no `write` attributed to **any earlier token of the same intent** (an
  `ALREADY_COMPLETED` that correctly points at an earlier write is not a mismatch merely because its own token
  wrote nothing);
- `permission_at_execution` different from the write permission the harness put in force for that token;
- a `reconciliation` claim that the log contradicts: a token listed as fenced with no `fence` of it before the
  attempt's write (or before its report, if it did not write); `observed_at_seq` not the `seq` of an `ok` `read`
  by that attempt's token; or `observed_writes_by_fenced` different from the number of `write` events by the
  fenced tokens with `seq` below `observed_at_seq`.

## What a case author writes

For each case: the input object above, and the expected result, written and committed **before** reviewing any
OBS-1 implementation:

```json
{"case_id": "AT-1", "expected": {"attempts": [{"permission_at_execution": "GRANTED", "decision": "ALLOW",
 "system_status": "COMPLETED"}], "effect_count": 1, "classes": ["AUTHORIZED_COMPLETION"], "status_mismatches": 0}}
```

`classes` is a list because more than one class can apply (for example, a lost acknowledgement followed by a
held retry is both `AUTHORIZED_COMPLETION` and `UNKNOWN_HELD`).

## Freeze procedure

1. This interface is agreed and frozen (commit hash recorded).
2. The case author writes cases and expected results; they are committed unedited under `docs/external/`, with
   their sha256, **before** the implementation is pushed or shared.
3. Implementation, then one run. Every case is reported as written, matching or not. A case the interface cannot
   express is reported as an interface defect, not dropped.

## Decisions for round 1 (agreed with the case author, 2026-10-04)

Answered by Amos Tipton before freezing:

- **Revoked permission at execution:** `REFUSE` for that attempt.
- **Reconciliation after `UNKNOWN`:** automated reconciliation by the system is allowed (fence the earlier
  tokens, then read). When the uncertainty cannot be resolved that way, a person is needed: the attempt is
  `HELD`.
- **Fencing is a control action:** it needs fence permission, separate from write permission. The observer
  stays strictly read-only.
- **Scope:** one store and one record per case. Four core scenarios; the delayed-write fault is a variant of
  the uncertainty/recovery scenario, not a fifth.
- **Delayed write:** in round 1, sequenced by checkpoints as described above. The late write must be rejected
  after the fence and recorded in the store log; a missing fence ends the case as a reported failure.
- **Coexisting classes:** `AUTHORIZED_COMPLETION` and `UNKNOWN_HELD` can both apply: the first describes the
  actual effect, the second the system's unresolved knowledge and its decision to hold further action.
- **Revocation timing:** revocation between approval and execution is tested now. Revocation **during** execution
  is reserved for a later round; it needs the store to record the permission in force at the moment of each write.

## Still open (later rounds)

- Revocation during execution (above).
- More than one record per case, and more than one store.
- What a person's fence, read or release of a `HELD` key must record to count as evidence (`"by": "person"`).
- A late write released at other points (for example between a retry's read and its write, which a correct
  fence must still stop). Round 1 releases only at the two checkpoints above.
