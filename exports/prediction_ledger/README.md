---
license: mit
pretty_name: Sovereign Veritas prediction ledger (verdict lines)
tags:
  - preregistration
  - reproducibility
  - negative-result
  - provenance
size_categories:
  - n<1K
configs:
  - config_name: default
    data_files: ledger.jsonl
---

# Sovereign Veritas prediction ledger (verdict lines)

Every line in [sovereign-veritas](https://github.com/holland202/sovereign-veritas)'s committed raw outputs
(`results/**/*.txt`) that states a registered prediction's outcome, as one table. It is rebuilt from the repository
by `tools/prediction_ledger.py`, which invents nothing. Each row carries its file, line number, the line itself and
the commit it was read at.

## Read this first

- **This is not a score.** A REFUTED row can be the expected result: sabotage arms exist to refute predictions, and
  several experiments registered predictions of a *gap*, so a HELD row there confirms a defect. What a row means is
  in that experiment's registration and results file in `docs/`.
- **The arm column is a hint.** It is read from the file name only (`sabotage`, `mutant`, `noop`/`flip` → control,
  `pre_`/`prefix` → baseline). `unclassified` means the file name says nothing; it is not a claim that the run was the
  registered one.
- **The parser can miss lines.** It reads two printed forms (`P3  HELD` and `HELD    P3`). Files that print a
  `VERDICT` line but gave no rows are listed in `summary.json` (5 at this commit).
- **Self-tested.** The exporter's self-test checks both forms, rejects look-alikes such as `HELDOUT` and lower-case
  `held`, and detects a sabotage file name. It was not independently reviewed.

## At commit `6db45d51398623797b2f1bcbd4e22d93d95d71f3`

From `summary.json`: 291 rows, from 49 of 86 result files, across 19 experiments.

| arm (from file name) | HELD | REFUTED | NOT RUN |
|---|---|---|---|
| unclassified | 198 | 16 | 2 |
| sabotage | 32 | 27 | 0 |
| control | 7 | 2 | 0 |
| baseline | 6 | 0 | 1 |

## Columns

| column | meaning |
|---|---|
| `experiment` | the folder under `results/` |
| `file` | the raw output file, relative to the repository |
| `line` | line number in that file |
| `id` | the prediction's ID as printed (`P3`, `KC-P2`, …) |
| `outcome` | `HELD`, `REFUTED` or `NOT RUN`, as printed |
| `arm` | hint from the file name (see above) |
| `raw` | the line itself, trimmed to 300 characters |
| `commit` | the repository commit the file was read at |

## Rebuild it

```
git clone https://github.com/holland202/sovereign-veritas && cd sovereign-veritas
git checkout 6db45d51398623797b2f1bcbd4e22d93d95d71f3
python3 tools/prediction_ledger.py out
```

## Changes

- 2026-11-07: first upload carried the card and summary but not `ledger.jsonl` (the repository ignored `*.jsonl`). Rebuilt at `6db45d5`, which adds EO-2.

## Provenance

Built by Claude (Anthropic, Opus 5.5) from the repository's own files → human validation: not performed → human
direction: Chad Holland, 2026-11-07 → human responsibility: Chad Holland. Review level: direction only.
