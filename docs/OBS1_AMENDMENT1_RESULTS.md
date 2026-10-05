# OBS-1 Amendment 1 results: the comparator now checks the final state (4 of 4 as registered)

Registration: [`OBS1_AMENDMENT1_PREREG.md`](OBS1_AMENDMENT1_PREREG.md), committed alone at `cc42193` before the change.
Change, probe and runner option at `8943ac7`. Both findings came from Amos Tipton's check of the published run
(email to Chad Holland, 2026-10-05). The registered run, its bundle (`results/obs1/run/`, `2d0766d`), the frozen
interface and his v1.0 expectations are unchanged. Linux container. **Not run on the S25.**

Drafted by Claude (Opus 5.5), which also wrote the change and judged the results, at Chad Holland's direction.
Chad has not reviewed it line by line. Amos Tipton has not reviewed this amendment.

## What was wrong

1. **Missing evidence.** The nine `store_events.jsonl` logs were not in the evidence commit: `.gitignore` excluded
   `*.jsonl`. They were retained, and are published unregenerated at `2321409` with
   [`results/obs1/run/STORE_LOGS_PROVENANCE.md`](../results/obs1/run/STORE_LOGS_PROVENANCE.md): same-second
   timestamps as the registered run, each equal event for event to the committed observer snapshot, and no hash
   recorded before 2026-10-05. `.gitignore` now keeps `results/obs1/**/store_events.jsonl`.
2. **A check that could not fail.** The comparator never compared the observer's final record with the log, so a
   final version of 99 still matched exactly. Wrong final values and write counts were not reported as inconsistent
   either.

## Outcome

| ID | Prediction | Result |
|---|---|---|
| A1 | the three mutations are each reported `FINAL_STATE_INCONSISTENT` (store defect, no class); unmutated AT-1 still matches | **HELD** |
| A2 | anti-vacuity: `0ba3aa7`'s comparator still reports no inconsistency for them | **HELD** |
| A3 | the five registered bundles, rescored, still match exactly | **HELD** |
| A4 | rerun to `results/obs1/rerun_amendment1/`: 10 of 10 on P1–P10 | **HELD** |

## Output (verbatim, `results/obs1/amendment1_probe.txt`)

```
A1  unmutated AT-1, amended comparator: match True final-state []
A1  version 99   amended:  match False store_defect True classes [] ['FINAL_STATE_INCONSISTENT: final version 99, the log gives 1', "FINAL_STATE_INCONSISTENT: last write's version 1, final 99"]
A1  value 'off'  amended:  match False store_defect True classes [] ["FINAL_STATE_INCONSISTENT: final value 'off', the log gives 'on'"]
A1  writes 5     amended:  match False store_defect True classes [] ['FINAL_STATE_INCONSISTENT: writes 5 - 0, the log has 1']
A2  version 99   0ba3aa7: match True invariant [] classes ['AUTHORIZED_COMPLETION']
A2  value 'off'  0ba3aa7: match False invariant [] classes []
A2  writes 5     0ba3aa7: match False invariant [] classes ['AUTHORIZED_COMPLETION']
A3  AT-1     registered bundle, amended comparator: match True final-state []
A3  AT-2     registered bundle, amended comparator: match True final-state []
A3  AT-3     registered bundle, amended comparator: match True final-state []
A3  AT-4     registered bundle, amended comparator: match True final-state []
A3  AT-4-DW  registered bundle, amended comparator: match True final-state []

  A1  HELD
  A2  HELD
  A3  HELD
  A4  run: python tools/obs1_run.py --out results/obs1/rerun_amendment1
VERDICT  3 of 3 as registered
exit 0
```

## A4 rerun (verbatim excerpt, `results/obs1/rerun_amendment1/run_output.txt`)

```
OBS-1 round one | implementation 8943ac79d1aa10c2a8b8d19c7f66c6787e35334e | cases v1.0 docs/external/amos-tipton_2026-10-04_obs1-cases_v1.0

  P1   HELD
  P2   HELD
  P3   HELD
  P4   HELD
  P5   HELD
  P6   HELD
  P7   HELD
  P8   HELD
  P9   HELD
  P10  HELD
VERDICT  10 of 10 as registered
exit 0
```

The rerun's bundle, with its store logs, is in `results/obs1/rerun_amendment1/`. Tokens differ from the registered
run's because they are random per run.

## Still open

The six weaknesses in [`OBS1_RESULTS.md`](OBS1_RESULTS.md) other than this one remain, as do round two's items.
