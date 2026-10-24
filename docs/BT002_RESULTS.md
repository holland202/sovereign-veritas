# BT-002 results: the 15 new tests kill all 15 shown gaps on the phone, and every registered prediction held

Registration: [`BT002_PREREG.md`](BT002_PREREG.md), commit `d2d673b`, pushed before the phone run. Raw records:
[`results/bt002/`](../results/bt002/), unedited, with [`SHA256SUMS`](../results/bt002/SHA256SUMS). The owner
transferred them from the phone on 2026-10-24 as one archive (SHA-256 `3b56f738…b550`). **Self-tested:** Claude
(Anthropic, Opus 5.5) wrote the tests, the driver, the scorer and this file, and the code under test was built with
Claude. Chad Holland chose the run and operated the phone. He has not reviewed this write-up.

## Failures and gaps first

1. **No battery or temperature data.** All 180 device-log lines read `"source": "termux-battery-status", "error":
   "TimeoutExpired"`: the command exists on the phone but never answers (the Termux:API app is likely missing).
   Two other routes failed before launch: `termux-battery-status` returned nothing, and `/sys/class/power_supply` was
   `Permission denied`. Each log attempt also held the logging thread for 20 s. That does not touch the verdicts,
   which come from separate subprocesses.
2. **Charging was asked for but not confirmed.** The owner was asked to put the phone on the charger; no transcript
   line shows it.
3. **70 of 351 mutants were NOT RUN** (64 in `workflow.py`, 6 in `runtime.py`), because 4 hours ran out. All 51
   BT-001 survivors ran first, as registered, so every prediction is fully answered. BT-001 killed all 70 unreached
   mutants. Any total that includes them leans on BT-001 and is labelled as a projection.
4. **One survivor of the argued group was killed in passing** (`capability.py#15`, `return None` in `check`). The
   new `capability.py#16` test unpacks `check`'s result, and `None` breaks that. This was within BT2-P4's allowance,
   and is the case the registration named as an example.

## Verdicts

| ID | Prediction | Result |
|---|---|---|
| BT2-P1 | Both controls behave as stated | **HELD.** `control null: T PASS C PASS as_expected=True`; `control always-allow: T FAIL C FAIL as_expected=True` |
| BT2-P2 | All 15 shown-gap mutants KILLED by T | **HELD: 15 of 15** |
| BT2-P3 | The 7 argued-EQUIVALENT mutants still SURVIVE T | **HELD: 7 of 7 survive** |
| BT2-P4 | At most 3 of the 27 argued-not-run GAPs killed | **HELD: 1 of 27** (`capability.py#15`) |
| BT2-P5 | Every BT-001-killed mutant reached is still killed | **HELD: 230 of 230** |
| BT2-P6 | The run ends by itself and writes `end.json` | **HELD:** `{"end": "deadline reached", "launch": 1, "mutants_this_launch": 281, "utc": "2026-10-24T15:25:07+00:00"}` |
| BT2-P7 | Same verdicts on x86 | NOT RUN (door). Partial cross-check: the C oracle's verdict equals BT-001's (container, x86) for **281 of 281** mutants run |

No T or C timeouts. The SHA-256 of every mutant run equals BT-001's.

## Numbers (from `results/bt002/blue.jsonl`)

Mutants identical to the original are left out, as in BT-001 (the two such survivors ran and survived).

| Target | Ran | T-killed | Rate on this run | BT-001 rate (all mutants) |
|---|---|---|---|---|
| decision.py | 88 | 83 | 94.3% | 93.2% (82/88) |
| verification.py | 7 | 7 | 100.0% | 100.0% (7/7) |
| idempotency.py | 71 | 58 | 81.7% | 76.1% (54/71) |
| evidence.py | 80 | 70 | 87.5% | 80.0% (64/80) |
| capability.py | 26 | 24 | 92.3% | 80.8% (21/26) |
| runtime.py | 3 of 9 | 2 | not comparable: survivors ran first | 88.9% (8/9) |
| workflow.py | 4 of 68 | 2 | not comparable: survivors ran first | 94.1% (64/68) |
| **All run** | **279** | **246** | **88.2%** | |

- **Survivors went from 49 to 33** (non-identical): the 15 shown gaps plus `capability.py#15` are now killed.
- **Projection, all 349:** 316 of 349 = **90.5%**, against BT-001's 300 of 349 = 86.0%. This assumes the 70
  unreached mutants, all killed in BT-001, are still killed, which BT2-P5's 230 of 230 supports but did not test.
- **Phone timing** (S23 Ultra SM-S918U, Python 3.14.8): a surviving mutant runs the whole suite in a median 269 s
  (max 275); a killed one stops in a median 9 s. The `null` control took 212 s. In the container the same suite
  takes about 45 s.

## What this supports (C-DESIGN)

This was a mutation audit with registered predictions, run on one device. On it, the 15 new tests close every gap
BT-001 showed with an input, and they cost no previously caught fault. It does not show that the remaining 33
survivors are harmless: 7 are argued equivalent, and 26 are known, argued gaps, mostly immutability and
public methods returning `None`.

## Doors (unrun)

- **BT2-P7:** re-run all 351 on x86 with the new tests, and compare verdicts mutant by mutant.
- **BT-003:** tests for the 26 argued gaps, starting with the `frozen=False` immutability group (6 mutants), which
  one shared test pattern would cover.
- **Device telemetry:** install the Termux:API app (or set up Shizuku's `rish`) before the next long run, and check
  that `termux-battery-status` answers before launch.
