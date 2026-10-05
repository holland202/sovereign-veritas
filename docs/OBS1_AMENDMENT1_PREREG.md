# OBS-1 Amendment 1: a final-state consistency check in the comparator. Registration

Status: **REGISTERED, nothing changed under it.** Committed before any change to `tools/obs1_compare.py` or
`tools/obs1_run.py`. The registered run (`0ba3aa7`, bundle `2d0766d`, results `docs/OBS1_RESULTS.md`), the frozen
interface (`04bca2d`) and Amos Tipton's cases v1.0 (`05f630c`) are unchanged by this amendment and stay as published.
This amends the comparator, not the interface and not the expectations.

Drafted by Claude (Opus 5.5) at Chad Holland's direction. Chad has not reviewed it line by line.

## The finding (Amos Tipton, email to Chad Holland, 2026-10-05)

Changing only AT-1's final observed `version` from 1 to 99 still produces an exact expected match with zero
mismatches: the comparator never checks the observer's final record against the store log. Reproduced on the
published AT-1 records before this registration (`compare()` at `0ba3aa7`, verbatim):

```
as recorded          match True mismatches 0 classes ['AUTHORIZED_COMPLETION'] effect 1 invariant []
version 99 (Amos)    match True mismatches 0 classes ['AUTHORIZED_COMPLETION'] effect 1 invariant []
value 'off'          match False mismatches 0 classes [] effect 1 invariant []
writes 5             match False mismatches 0 classes ['AUTHORIZED_COMPLETION'] effect 5 invariant []
```

The second and third neighbours were added here. A wrong final value or write count changes the outcome only
indirectly (a lost class, a wrong effect count) and is never reported as an inconsistency. The published records
themselves are correct (Amos's check and this project's both found them consistent).

He also found that the nine `store_events.jsonl` logs were missing from the evidence commit (an ignore rule). They
were retained and are published at `2321409` with a provenance note; that is not part of this amendment's tests.

## The change (fixed before the code)

Before classes are computed, the comparator replays the case's store log from the observer's **before** snapshot and
requires the observer's **after** snapshot to agree with it:

- final `version` = before `version` + number of `write` events, and equal to the last write's `version`;
- final `value` = the last write's `value` (or the before `value` if there was no write);
- `writes` after − `writes` before = number of `write` events for the record;
- the after snapshot's events start with the before snapshot's events.

Any disagreement is reported as `FINAL_STATE_INCONSISTENT: …` in the same list as the store invariant, so the case
is reported as `STORE_DEFECT` with no outcome class, as the interface does for a log that breaks the invariant. The
runner gains `--out DIR` so the rerun is written apart from the registered bundle.

## Predictions

| ID | Prediction |
|---|---|
| A1 | **Amos's mutation is caught.** On the published AT-1 records, `version 99`, `value 'off'` and `writes 5` are each reported as `FINAL_STATE_INCONSISTENT` (store defect, no class, no expected match); the unmutated records still match exactly. |
| A2 | **Anti-vacuity.** The same three mutations against `0ba3aa7`'s comparator (loaded from `git show`) still give no inconsistency, as in the finding above. |
| A3 | **No change on the real records.** All five registered case bundles, rescored from their published files with the amended comparator, still match Amos's expected results exactly. |
| A4 | **Rerun.** `python tools/obs1_run.py --out results/obs1/rerun_amendment1` at the amended commit gives 10 of 10 on the registered predictions P1–P10. |

## Limits

Same as round one. The check is only as good as the observer's snapshots, which the same project produces.

## Next unrun test

Round two's items from `docs/OBS1_RESULTS.md` (separate process for the system, per-attempt `seq` boundaries,
`fail_record_after_effect`).
