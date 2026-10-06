# XB-1 results — Davorin Popović's report REPRODUCED; 8 of 8 cases as registered

Registration: `docs/EXECUTION_BOUNDARY_PREREG.md` (committed 7a8351e, before the probe existed).
Probe: `python tools/execution_boundary_probe.py`. x86-64 container, Python 3.13.15.
**NOT VALIDATED on the S25.** Pinned in CI (red-team job).

## External observation

Davorin Popović identified a potential execution/evidence atomicity issue in `EvidenceWorkflow.run()`.
His reported probe prompted the XB-1 investigation. The project independently reproduced the behavior,
preregistered the experimental cases, and documented the resulting findings and limitations. Credit is
for the observation; he has not reviewed or endorsed these results or any proposed fix.

**Attribution refinement (2026-10-06), at Davorin Popović's request.** The initial finding came through an
AI-assisted private review/report identifying that `execute()` runs before the record is written; he had not
independently reproduced the probe at that point (the PREREG records it as a Codex-assisted review). He reviewed
the attribution wording only. The paragraph above is left as written.

**Attribution correction (2026-10-02).** The PREREG's open-question line reads "Davorin / Sougata".
The authority-revalidation question was raised by Davorin Popović. Sougata Roy's separate feedback, that
authorization and justification are different questions, did not concern this boundary and is not a
source of this experiment. The PREREG is left unedited because it is a frozen registration.

## Failures first

At both `386716a` (the commit Davorin cited) and `794a86b` (main after PR #6), `EvidenceWorkflow.run()`
lets the external effect happen before the ledger can refuse it:

- **X1–X3 — duplicate `record_id` → 2 external effects, 1 ledger record.** In memory, on disk, and
  across a reload of the on-disk ledger. The ledger's duplicate check works; it runs after `execute()`.
  `RECORD_REJECTED ≠ EXTERNAL_EFFECT_REVERSED`, measured.
- **X4 — two threads, same `record_id` → 2 effects, 1 record.**
- **X5 — executor succeeds, write fails → 1 effect, 0 records.** The world changed and the evidence
  chain does not know. This is the case no duplicate check can reach.

Davorin's observation moves from REPORTED to **REPRODUCED (independently, by a second probe)**. The
external party remains the origin; the reproduction is this file.

## Transcript (main, 794a86b — 386716a gave the identical eight lines)

```
XB-1 | expecting the current code
AS REGISTERED      X0   effects 2 records 2 errors 0  (registered 2/2/0)  first error: -
AS REGISTERED      X0r  effects 0 records 1 errors 0  (registered 0/1/0)  first error: -
AS REGISTERED      X1   effects 2 records 1 errors 1  (registered 2/1/1)  first error: ValueError: duplicate record_id: dup
AS REGISTERED      X2   effects 2 records 1 errors 1  (registered 2/1/1)  first error: ValueError: duplicate record_id: dup
AS REGISTERED      X3   effects 2 records 1 errors 1  (registered 2/1/1)  first error: ValueError: duplicate record_id: dup
AS REGISTERED      X4   effects 2 records 1 errors 1  (registered 2/1/1)  first error: ValueError: duplicate record_id: race
AS REGISTERED      X5   effects 1 records 0 errors 1  (registered 1/0/1)  first error: OSError: simulated write failure (disk full)
AS REGISTERED      X6   effects 0 records 1 errors 1  (registered 0/1/1)  first error: RuntimeError: executor failed before any effect
VERDICT  8 of 8 as registered
```

## What held

- X0 / X0r (anti-vacuity): distinct IDs give 2 effects and 2 records with no error; a REFUSE gives 0
  effects. The probe is not counting everything as a duplicate.
- X6: an executor that fails before any effect is recorded with `execution_status = FAILED`.

## Scope boundary (what this does not show)

- Authority revalidation at execution (T1 → T2) is not reachable through `run()`: the Gate and the
  execution share one call and there is no deferred-execution API. Door left open in the PREREG.
- Whether any real executor in this repository (`tools/*_action.py`) is exposed in practice depends on
  whether its callers can repeat a `record_id`. Not audited here.
- The fix is a separate change (`fix/xb1-refuse-before-effect`). Its registered reach is X1–X3 only.

## Fix status (updated when PR #8 merged)

| Case | Status | Mechanism |
|---|---|---|
| X1–X3 sequential repeat (memory, file, reload) | **CLOSED** — 1 effect | `EvidenceWorkflow.run()` asks `sink.has_record()` before anything runs |
| X4 concurrent race | **OPEN** | check-then-act; needs an atomic reservation |
| X5 effect, then record write fails | **OPEN** | needs a durable intent before the effect, plus a way to learn what happened |
| sink without `has_record` | **OPEN, by choice** | no pre-check (backward compatible); not "missing means deny" |

X4 and X5 are limits of the workflow and ledger, not of the Gate's decision contract (`sv.gate/0`), so
they are not filed under `sv.gate/1`. Probe: `python tools/execution_boundary_probe.py --expect-fix`
gives 8 of 8 as registered after the fix (X1–X3 at 1 effect; X4, X5 unchanged).
