# OBS-1 — permission, execution and an independent observer: interface (draft for case authors)

Status: **DRAFT interface, nothing implemented.** This file defines what a case looks like, what the system
must report, and what a separate observer can see. It is written **before** any OBS-1 code exists, so that
outside case authors can write cases and expected results without reading an implementation. Once the case
author and Chad Holland agree on it, it is frozen; changes after that need a dated amendment.

Design lead: **Amos Tipton**, Founder & Chief Architect of HYBRID WAYSS, in messages to Chad Holland on 2026-10-04:
one small sandbox action, a separate observer that checks the actual downstream result, permission recorded at
execution separately from what the observer confirms, and four outcomes: authorized completion, permission revoked
between approval and execution, confirmed failure before any effect, and an uncertain outcome that requires
observation before retrying. Credit for that design is his. This draft, the implementation and any results are
this project's. Naming his design does not imply he endorses or has reviewed them.

Drafted by Claude (Opus 5.5) at Chad Holland's direction. Chad has not reviewed it line by line.

## Why

Every "1 effect" number in this repository so far (XB-1, RK-1, RK-2) is counted by the same code that performed
the action. OBS-1 adds an observer that is not part of the system under test, so the system's own claim about
what happened can be checked against what did happen.

## The sandbox

One synthetic record store, a directory of files. It is owned by the **store**, not by the system under test.

- A record has `record_id`, `value` (a string) and `version` (an integer, starting at 0).
- The only write is `set_value(record_id, new_value)`. Each write that lands increases `version` by 1 and appends
  one line to the store's own append-only write log: `{record_id, version, value, write_id}`.
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
  `execution`; it may not reuse the approval-time answer.
- `fault`, one of:
  - `null` — no fault.
  - `"fail_before_effect"` — the store rejects the write; nothing lands.
  - `"lose_ack_after_effect"` — the write lands, then the reply to the system is lost (the system sees a timeout).
  - `"fail_record_after_effect"` — the write lands and the reply arrives, then the system's own ledger write fails.
- `attempts`: how many times the caller tries the same intent with the **same** `idempotency_key`. A retry is a
  new call, not a loop inside the system.

## What the system must report (per attempt)

```json
{
  "case_id": "AT-1", "attempt": 1,
  "permission_at_execution": "GRANTED",
  "decision": "ALLOW",
  "system_status": "COMPLETED",
  "reason": null
}
```

- `permission_at_execution`: `GRANTED` | `REVOKED` | `NOT_READ` (`NOT_READ` when execution was not reached).
- `decision`: the Gate's decision for this attempt: `ALLOW` | `DEFER` | `REFUSE`.
- `system_status`: what the system believes happened:
  - `COMPLETED` — it believes the effect landed exactly once;
  - `FAILED` — it believes no effect landed;
  - `UNKNOWN` — it cannot tell (for example, the reply was lost);
  - `REFUSED` — it did not attempt the write.
- `reason`: a short machine-readable reason when not `COMPLETED`.

## The observer (read-only)

The observer is a separate program. It reads the store's files directly. It does not import, call or share memory
with the system under test, and it opens the store read-only. Its whole interface is one call:

```
observe(record_id) -> {"value": str, "version": int, "writes": int, "write_ids": [str, ...]}
```

- `writes`: the number of lines for `record_id` in the store's write log since the case began.
- `effect_count` for a case is `writes` after the case minus `writes` before it.

## Outcome classes (fixed rule, applied by the comparator, not by the system)

Per case, after the last attempt:

| Class | Rule |
|---|---|
| `AUTHORIZED_COMPLETION` | permission `GRANTED` at the execution that wrote, `effect_count == 1`, observed `value == new_value` |
| `UNAUTHORIZED_EXECUTION` | `effect_count >= 1` and permission was not `GRANTED` at the execution that wrote |
| `DUPLICATE` | `effect_count >= 2` |
| `CONFIRMED_FAILURE` | `effect_count == 0`, and the system reported `FAILED` or `REFUSED` |
| `UNKNOWN_RESOLVED` | an attempt reported `UNKNOWN`; before any retry the observer was consulted; the retry happened only if the observer showed `effect_count == 0` |
| `UNKNOWN_UNSAFE` | an attempt reported `UNKNOWN` and a retry wrote without the observer confirming `effect_count == 0` |

Separately, every attempt's `system_status` is compared with the observer: a `COMPLETED` with `effect_count == 0`,
or a `FAILED` with `effect_count >= 1`, is a **status mismatch**. That is the measurement this experiment exists
for: the system's claim against what actually happened.

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

## Open questions for the case author (not decided here)

- Should a revoked permission at execution give `REFUSE` (no attempt) or `DEFER` (hold for a person)?
- After `UNKNOWN`, may the system itself call the observer, or only the caller?
- Is one store and one record enough for the first round, or should a case be able to touch two records?
