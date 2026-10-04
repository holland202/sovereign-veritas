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
reconciliation requirement for retries after `UNKNOWN`, the `ALREADY_COMPLETED` distinction, and the round-1
decisions listed below. This draft, the implementation and any results are
this project's. Naming his design does not imply he endorses or has reviewed them.

Drafted by Claude (Opus 5.5) at Chad Holland's direction. Chad has not reviewed it line by line.

## Why

Every "1 effect" number in this repository so far (XB-1, RK-1, RK-2) is counted by the same code that performed
the action. OBS-1 adds an observer that is not part of the system under test, so the system's own claim about
what happened can be checked against what did happen.

## The sandbox

One synthetic record store, a directory of files. It is owned by the **store**, not by the system under test.

- A record has `record_id`, `value` (a string) and `version` (an integer, starting at 0).
- The only write is `set_value(record_id, new_value, attempt_token)`. Each write that lands increases `version`
  by 1 and appends one line to the store's own append-only write log: `{seq, record_id, version, value,
  attempt_token}`. `seq` is the store's own counter; the system under test cannot set it.
- The store has one more call, `fence(attempt_token)`. It appends `{seq, fence: attempt_token}` to the same log,
  and from then on any `set_value` carrying that token is rejected: nothing lands. A fence is how anyone (the
  system, or a person) makes sure an earlier attempt **cannot still produce an effect**, for example an attempt
  whose reply was lost and which may still be in flight.
- The store can be told to inject one fault per case (below). It never reports to the observer how a write was
  requested; it only keeps the record and its log.

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
  "attempts": 1
}
```

- `approval.granted`: whether permission was granted when the intent was approved.
- `permission_timeline`: what the permission source says at each step. The system must **re-read** permission at
  `execution`; it may not reuse the approval-time answer. If permission is revoked at execution, the required
  behaviour is `REFUSE` for that attempt (decided, see below).
- `fault`, one of:
  - `null` — no fault.
  - `"fail_before_effect"` — the store rejects the write; nothing lands.
  - `"lose_ack_after_effect"` — the write lands, then the reply to the system is lost (the system sees a timeout).
  - `"fail_record_after_effect"` — the write lands and the reply arrives, then the system's own ledger write fails.
- `attempts`: how many times the caller tries the same intent with the **same** `idempotency_key`. A retry is a
  new call, not a loop inside the system.

## Who establishes what (attribution and permission)

The observer can see that a write landed. On its own it cannot see **which attempt** caused it, or **whether
permission was in force** when it did. Neither may be taken from the system's own report, because that report is
what is being checked. So both are established by the **harness** (the program that runs the case), which is
separate from the system under test:

- **Attempt tokens.** Before each attempt, the harness creates a fresh random `attempt_token`, records it, and
  hands it to the system with the intent. The system must pass it unchanged to `set_value`. The store writes it
  into the log. A logged write is attributed to an attempt only by its token.
- **Permission ground truth.** The harness sets the permission source to the `permission_timeline` value for
  `execution` **before** it starts each attempt, and does not change it during the attempt. It records, per
  token, the permission that was in force. Round 1 does not change permission while an attempt is running (see
  open questions).

What this does not establish: a token shows which call the store received, not that the system meant it. A system
that drops or copies a token produces a write that cannot be attributed to the attempt it claims, and that is
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

- `permission_at_execution`: `GRANTED` | `REVOKED` | `NOT_READ` (`NOT_READ` when execution was not reached).
- `decision`: the Gate's decision for this attempt: `ALLOW` | `DEFER` | `REFUSE`.
- `system_status`: what the system believes happened:
  - `COMPLETED` — it believes the effect landed exactly once;
  - `FAILED` — it believes no effect landed;
  - `UNKNOWN` — it cannot tell (for example, the reply was lost);
  - `REFUSED` — it did not attempt the write;
  - `ALREADY_COMPLETED` — it did not write because an earlier attempt of the **same intent** already completed;
  - `HELD` — it did not write because an earlier attempt's outcome is unresolved and needs a person.
- `reason`: a short machine-readable reason when not `COMPLETED`.
- `reconciliation`: `null`, or what the system did to resolve an earlier `UNKNOWN` **before** this attempt wrote:
  `{"fenced_tokens": [...], "observed_at_seq": int, "observed_writes_by_fenced": int, "by": "system" | "person"}`.
  Automated, read-only reconciliation by the system is allowed; when it cannot resolve the uncertainty, the
  attempt must be `HELD` for a person (decided, see below). This field is the system's **claim**; the comparator
  checks it against the store log.

## The observer (read-only)

The observer is a separate program. It reads the store's files directly. It does not import, call or share memory
with the system under test, and it opens the store read-only. Its whole interface is one call:

```
observe(record_id) -> {"value": str, "version": int, "writes": int,
                       "log": [{"seq": int, "version": int, "value": str, "attempt_token": str | null}, ...]}
```

- `writes`: the number of lines for `record_id` in the store's write log since the case began.
- `effect_count` for a case is `writes` after the case minus `writes` before it.
- Each logged write is attributed by matching its `attempt_token` against the harness's record of tokens. A write
  with no token, an unknown token, or a token already used by another logged write is **unattributed**.

## Outcome classes (fixed rule, applied by the comparator, not by the system)

Inputs to the rule come only from the harness (tokens, permission in force per token) and the observer (logged
writes and fences, in `seq` order). The system's report is used only in the mismatch checks below. Per case,
after the last attempt:

| Class | Rule |
|---|---|
| `UNATTRIBUTED_WRITE` | any logged write is unattributed |
| `UNAUTHORIZED_EXECUTION` | any attributed write whose token had permission not in force |
| `DUPLICATE` | two or more attributed writes for the case |
| `AUTHORIZED_COMPLETION` | exactly one write, attributed, its token had permission in force, observed `value == new_value` |
| `CONFIRMED_FAILURE` | no writes, and the system reported `FAILED` or `REFUSED` on its last attempt |
| `UNKNOWN_RECONCILED_RETRY` | an attempt reported `UNKNOWN`; a later attempt wrote; and **before that write** (lower `seq`) the log holds a fence for every earlier token of the case, no earlier token has a logged write, and the writing token had permission in force |
| `UNKNOWN_UNRESOLVED_RETRY` | an attempt reported `UNKNOWN` and a later attempt wrote **without** that evidence (an earlier token unfenced at the time of the write, fenced only afterwards, or itself wrote). This applies even if the case ends with only one write. |
| `UNKNOWN_HELD` | an attempt reported `UNKNOWN` and no later attempt wrote |

More than one class can apply; all that apply are reported, in this table's order.

The harness always issues every attempt the case lists, whatever the earlier attempts reported. Whether a retry
after `UNKNOWN` writes again is decided by the system, so these classes measure the system, not the harness. (An
earlier draft let the harness consult the observer and skip the retry, which would have made that class pass by
construction.)

A single write after an `UNKNOWN` is **not** by itself evidence that the retry was safe: the earlier attempt might
still have landed later. (An earlier draft counted "at most one write" as safe; Amos Tipton pointed out on
2026-10-04 that this does not establish safety, and that the earlier attempt must be shown unable to produce an
effect before a later one may write.) The evidence required is in the store log, written by the store, and is
checked against `seq` order, not taken from the system's report.

**Status mismatches** are the measurement this experiment exists for: the system's claim against what happened.
Per attempt, comparing the system's report with the observer and the harness:

- `COMPLETED` but no write attributed to **that attempt's** token;
- `FAILED`, `REFUSED`, `ALREADY_COMPLETED` or `HELD`, but a write attributed to that attempt's token;
- `ALREADY_COMPLETED` but no write attributed to **any earlier token of the same intent** (an `ALREADY_COMPLETED`
  that correctly points at an earlier write is not a mismatch merely because its own token wrote nothing);
- `permission_at_execution` different from the permission the harness put in force for that token;
- a `reconciliation` claim that the log contradicts: a token listed as fenced with no fence in the log before the
  attempt's write, or `observed_writes_by_fenced` different from the log's count at `observed_at_seq`.

## What a case author writes

For each case: the input object above, and the expected result, written and committed **before** reviewing any
OBS-1 implementation:

```json
{"case_id": "AT-1", "expected": {"attempts": [{"permission_at_execution": "GRANTED", "decision": "ALLOW",
 "system_status": "COMPLETED"}], "effect_count": 1, "class": "AUTHORIZED_COMPLETION", "status_mismatches": 0}}
```

## Freeze procedure

1. This interface is agreed and frozen (commit hash recorded).
2. The case author writes cases and expected results; they are committed unedited under `docs/external/`, with
   their sha256, **before** the implementation is pushed or shared.
3. Implementation, then one run. Every case is reported as written, matching or not. A case the interface cannot
   express is reported as an interface defect, not dropped.

## Decisions for round 1 (agreed with the case author, 2026-10-04)

Answered by Amos Tipton before freezing:

- **Revoked permission at execution:** `REFUSE` for that attempt.
- **Reconciliation after `UNKNOWN`:** automated, read-only reconciliation by the system is allowed (fence the
  earlier tokens, then observe). When the uncertainty cannot be resolved that way, a person is needed: the attempt
  is `HELD`.
- **Scope:** one store and one record per case.
- **Revocation timing:** revocation between approval and execution is tested now. Revocation **during** execution
  is reserved for a later round; it needs the store to record the permission in force at the moment of each write.

## Still open (later rounds)

- Revocation during execution (above).
- More than one record per case, and more than one store.
- What a person's release of a `HELD` key must record to count as evidence.
