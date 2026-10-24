# BT-002 registration: do tests for BT-001's 15 shown gaps kill those mutants on the phone, and does nothing else regress? Nothing run under this registration yet

**State:** REGISTERED, NOT RUN on the phone. Committed before the phone run starts and before any phone output
exists.
**Authors:** Direction: Chad Holland (2026-10-24; he chose this run). Design, tests and driver: Claude (Anthropic,
Opus 5.5). Human review level: direction only. Everything run here is **self-tested** (M10).

## Why

BT-001 ([results](BT001_RESULTS.md)) found 15 mutants of the kernel that the test suite does not notice, each shown
with a concrete input (its "15 GAPs shown by an input"). Its door, BT-002, was to turn each of those inputs into a
test that fails on its mutant and passes on main, then re-run the audit. This run does that, on the owner's phone.

## What is added

- [`tests/test_bt002_gap_pins.py`](../tests/test_bt002_gap_pins.py) (SHA-256 `6b81206e…f08479`): 15 tests, one per
  shown gap. The inputs follow `tools/bt001_confirm.py`. They pin current behaviour, and they pin the CONTRACT.md text
  where it states the rule (the step boundary, rule 11: REFUSE only when `step_count` is greater than `max_steps`).
  One extra control test checks that a step count one over the limit still refuses.
- [`tools/bt002_run.py`](../tools/bt002_run.py) (SHA-256 `45f621be…efef`). It imports `tools/bt001_mutate.py`
  unchanged (SHA-256 `3dfae449…964b`): the same mutants, the same oracles T and C, the same controls and the same
  deselected instrument test. It changes three things:
  - **order:** BT-001's 51 T-survivors (49 counted, plus the two mutants identical to the original) run first,
    then the rest in BT-001's order;
  - **flushing:** each record is flushed and fsynced as it is written;
  - **device log:** a line goes to `device.jsonl` every 60 s, from `termux-battery-status` or Shizuku's `rish -c
    "dumpsys battery"` when either exists, otherwise `"source": "unavailable"`.
- The kernel is unchanged since BT-001. All 351 mutants match BT-001's by ID and SHA-256 (checked here).

## Device and procedure (phone)

- **Device:** Galaxy S23 Ultra (SM-S918U, SM8550), Termux, Python 3.14.8. Before launch:
  - on the charger;
  - `pkill ollama`, and the result recorded;
  - Shizuku on (owner's choice), so the device log can read the battery.
- **Code:** a fresh clone of this branch at the commit that adds this file, with `pip install pytest`.
- **Run:** `python tools/bt002_run.py --until <launch + 4 h> --out $HOME/bt002`. The `--until` value is recorded in
  the launch record, from the owner's transcript, before any output is read.
- On the phone the signature tests should run (`ssh-keygen` is present). Here 49 of them were skipped, so phone
  timings are expected to be longer than container ones.

## Disclosed before registration (C-EXPLORE)

1. **Gap check in the container** (Linux x86, Python 3.13.17): each of the 15 mutants run against the new test
   file alone gave 15 of 15 killed. The null copy passed (15 passed). This is the basis for BT2-P2, which the
   phone run replicates on a second device and with the whole suite as oracle T.
2. **Full suite with the new tests**, container: `510 passed, 49 skipped, 1 deselected in 42.06s`.
3. **Driver smoke run**, container, 150 s: both controls behaved as expected (`null` T PASS C PASS;
   `always-allow` T FAIL C FAIL). Three mutants ran and their verdicts were not read. The device log read
   `unavailable` (no phone).

## Predictions

| ID | Prediction | conf. | Precisely wrong if |
|---|---|---|---|
| BT2-P1 | Both controls behave as stated on the phone | 0.9 | either control has `as_expected: false` (the driver then stops with exit 2) |
| BT2-P2 | All 15 shown-gap mutants are KILLED by T | 0.9 | any of them has T PASS |
| BT2-P3 | The 7 argued-EQUIVALENT mutants still SURVIVE T: `decision.py#2`, `#3`, `#18`; `evidence.py#21`, `#29`, `#30`; `idempotency.py#5` | 0.95 | any of them is killed by T |
| BT2-P4 | At most 3 of BT-001's 27 argued-not-run GAPs are killed by T. The new tests target other mutants; a few may be caught in passing, for example a `return None` that breaks tuple unpacking | 0.6 | 4 or more are killed |
| BT2-P5 | Every mutant that BT-001's T killed and that this run reaches is still killed (adding tests cannot un-kill one) | 0.95 | any such mutant has T PASS |
| BT2-P6 | The run ends by itself (deadline or all done) and writes `end.json` | 0.7 | no `end.json`, meaning the phone stopped it |
| BT2-P7 (door, unrun) | The same verdicts reproduce on x86 for every mutant the phone ran | — | — |

**Outcome rule:** kill rates count only mutants that ran. Mutants not reached by the deadline are NOT RUN. A T
timeout counts as a kill, as in BT-001, and timeouts are reported separately.

## Pre-mortem

- **Android stops the processes** (DIFF-001, LR-001). Mitigations: charger, Ollama stopped, and every record
  flushed. BT2-P6 scores it.
- **pytest missing or a different version** on the phone. The null control would then fail and the run stops
  (exit 2). That is a setup failure, recorded as such.
- **Slow phone:** the survivors each run the whole suite. If 4 hours covers only part of the survivors, P2/P3/P4
  are scored on the ones reached, and the rest are NOT RUN.
