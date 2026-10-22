# BT-001 registration: do the defences catch planted faults (blue), and do three gate implementations still agree (red)? Nothing run under this registration yet

Status: registration only. Written 2026-10-22 ~21:00Z, before any oracle has run on any mutant and before any
red-arm case. Baseline: main `db640a2` (544 passed, 1 skipped in 73.1 s, Linux container, Python 3.13.16; `tools/gate_contract.py --check kernel`
CONFORMS, digest `44823d0f…0628`). Claude-assisted (Claude Opus 5.5). Chad Holland asked for a long blue- and
red-team run lasting until 8 p.m. Eastern (00:00Z), weighted toward blue, and left the choice of test to Claude.
He has not reviewed this text. The merge decision is his.

## Why these two

- **Blue (most of the time).** The project's defence against a regression is its test suite and its published
  contract (4,690 vectors). Nobody has measured whether those defences notice a small wrong edit to the kernel.
  Mutation testing measures exactly that: plant one small fault, and see whether any defence fails.
- **Red.** The phone run (DIFF-001) tests code from before the OVF-1 fix. This arm runs the same unchanged
  harness against **current main** (K and V) plus the independent port from PR #86, on case indices nobody has
  used.

## Blue arm: `tools/bt001_mutate.py` (committed with this file)

- **Targets, in this order:**
  1. `decision.py` (the Gate)
  2. `verification.py`
  3. `idempotency.py`
  4. `evidence.py`
  5. `capability.py`
  6. `runtime.py`
  7. `workflow.py`

  Files not reached by the deadline are reported NOT RUN.
- **Mutants:** every point found by an AST walk, in a fixed order (`--list` prints them). Docstrings and type
  annotations are excluded. The operators are:
  - comparison swap (`<`↔`<=`, `==`↔`!=`, `in`↔`not in`, `is`↔`is not`, …);
  - `and`↔`or`;
  - dropping a `not`;
  - flipping a boolean constant;
  - adding 1 to a number;
  - `return x` → `return None`;
  - `raise …` → `pass`;
  - negating an `if`.
- **Oracles**, on a scratch copy of the repository, with bytecode caching off:
  - **T**, the whole test suite with `-x`. The test files that mention the target run first; the order changes
    only how fast a kill is found.
  - **C**, `gate_contract.py --check kernel`.

  A mutant is **killed** by an oracle that fails (non-zero exit, timeout, or no `CONFORMS`) and **survives** one
  that passes. Timeouts: T 600 s, C 120 s.
- **Controls, at every launch:**
  - `null`, the Gate file re-emitted from its own syntax tree: both oracles must PASS;
  - `always-allow`, `return Decision("ALLOW")` as the first line of `Gate.evaluate`: both oracles must FAIL.

  If either control is off, the run stops (exit 2) and nothing from that launch counts.
- **Census before running (generation only, no oracle), `--list` at this commit:** 351 mutants. `decision.py`
  88, `verification.py` 7, `idempotency.py` 72, `evidence.py` 81, `capability.py` 26, `runtime.py` 9,
  `workflow.py` 68. Two are textually identical to the original (`idempotency.py` and `evidence.py`, one each).
  They are counted, but left out of every kill rate.

## Red arm

- **Code:**
  - an overlay assembled from pinned commits: main `db640a2`, plus `ports/python_independent/independent_gate.py`
    from PR #86 `4fddb8b` (SHA-256 `01592486…e6b0`);
  - plus `experiments/DIFF-001/diff_fuzz.py` from `ade8820`, unchanged (SHA-256 `55b32b13…4095`).

  Checked before running: the harness imports the overlay's own `sovereign_veritas`, not an installed copy.
- **Cases:**
  - segment 1: `--worker 1000000000 --workers 1`;
  - segment 2: `--worker 2000000000 --workers 1`, started after segment 1 ends.

  Each segment's `--until` is set at launch, and both end by 2026-10-23T00:00:00Z. The two are disjoint from the
  tuning indices 0–2,999, from the phone's 3,010 upward, and from each other.
- **Anti-vacuity, first:** `--mutant steps-ge --cases 20000` must exit 0 (the planted port fault is caught). That
  control uses indices 0–19,999. It checks the harness and judges no claim.

## Predictions

Kill rates leave out the two identical mutants and count only mutants that ran.

| ID | Prediction | conf. | Precisely wrong if |
|---|---|---|---|
| BT-P1 | Both controls behave as stated at every launch | 0.95 | any control record has `as_expected: false` |
| BT-P2 | T kills ≥ 90% of `decision.py`'s mutants | 0.7 | under 90% |
| BT-P3 | C kills ≥ 80% of `decision.py`'s mutants | 0.6 | under 80% |
| BT-P4 | Every `decision.py` mutant that C kills, T also kills (the suite carries the contract) | 0.8 | any mutant killed by C survives T |
| BT-P5 | Across all targets that ran, T kills ≥ 80% | 0.6 | under 80% |
| BT-P6 | T kills every `raise → pass` mutant in `idempotency.py` and `workflow.py` (10 mutants). These are the "refused before execution" refusals | 0.6 | any of them survives T |
| BT-P7 | Survivors are triaged as EQUIVALENT or GAP, and at least one is a GAP. A GAP is backed by a concrete input that would expose it. An EQUIVALENT gets a one-line argument that no input can | 0.8 | every survivor is equivalent |
| RT-P1 | The anti-vacuity control exits 0 | 0.9 | it exits 1 |
| RT-P2 | Both red segments: **0 disagreements** among K, V and I | 0.6 | any disagreement. Each signature class is then a finding, reported with a replayable index |

**Outcome rule, fixed now:**
- Kill rates and counts come from the results JSONL. RT-P2 comes from the harness's own summary files.
- Results quote the raw lines. At least one raw record per prediction is opened before results are written.
- **A GAP is reported, not fixed tonight.** The fix is a proposed test (the door below).

## Trigger table (CONTROLS.md, as amended by Amendment 4 if merged)

| Trigger | Answer |
|---|---|
| C-FEAS | about 3 hours on 2 container cores; one core per arm |
| C-NOISE | the oracles are deterministic. The null control is the same-input check. A flaky test would show up as a killed null and stop the run |
| C-STAT | kill rates describe this operator set on this code. No sampling, no p-values |
| C-INDEP | **self-tested.** Claude wrote the mutator, the predictions and the triage, and the code under test was built with Claude. Nothing here is independent |
| C-EXT | none |
| C-DEVICE | Linux container, x86, Python 3.13.16. **Not the phone** |
| C-BUILD | the controls stop the run when off. The red control must exit 0 before segment 1 starts |
| C-EXPLORE | before this commit: `--list` (generation only), `--show` on four mutants (below), the overlay's import check and the baseline runs quoted above. No oracle ran on any mutant |
| C-PRIVATE | no people's data |
| C-DESIGN | a fault-injection audit and a differential test of fixed code. It supports existence claims ("this planted fault goes unnoticed", "this input splits the implementations") and conformance on the inputs tried. It **does not** support a rate of real-world bugs |
| C-HOLDOUT | blue: nothing is chosen from results; targets, operators and thresholds are fixed here. Red: the generator was tuned on indices 0–2,999, and this run judges on indices ≥ 1,000,000,000 |
| C-SYNTH | the census above gives counts by file. Looked at before registering: `decision.py#3` (`value > 0` → `value > 1` in the overflow branch), `decision.py#47` (negated required-evidence check), `idempotency.py#20` (`reserve` returns None instead of its token) and `workflow.py#9` (negated "key without a store" refusal). Red: the decision mix is read from the summary |

## Pre-mortem: how this could record nothing, or the wrong thing

1. **Stale bytecode** could hide a mutant, so the original code is what gets tested. Mitigations: `-B`,
   `PYTHONDONTWRITEBYTECODE`, and `__pycache__` cleared before each oracle. The `always-allow` control would
   come out PASS if this failed.
2. **The wrong package is imported.** This container has an editable install of another checkout. Both arms
   import from the working tree. The blue control would catch the wrong import, and for the red arm it was
   checked directly.
3. **Kills that come from breakage, not detection.** A mutant that breaks import is "killed" by every oracle.
   The exit code is recorded (pytest 2/4 means a collection error), and such kills are reported separately.
4. **The container stops between turns.** The blue arm resumes from its JSONL, and the red arm runs in two
   segments.

## Amendment A1 (2026-10-22 ~21:05Z, after launch 1 stopped itself; no mutant has run)

- **What happened.** Launch 1 (`d193c00`) ran only the `null` control, and the control failed:
  `T FAIL rc 1, "1 failed, 425 passed, 3 skipped in 68.17s"`, `C PASS`. The run stopped with exit 2, as
  registered. **BT-P1 is REFUTED for launch 1 and kept.**
- **Cause, found by rerunning on the scratch copy:**
  - The unmutated copy passes: `542 passed, 3 skipped`. Two tests skip there because the copy is not a git
    checkout (`test_gate_contract.py:114`, `test_witness.py:116`); `pymavlink` is missing for the third.
  - With `decision.py` re-emitted from its AST, `tools/gate_constraint.py --target <copy>` is `VERDICT CLEAN`
    (rc 0), but `--mutants` reports `M15 INVALID anchor matched 0x` and `M17 INVALID anchor matched 0x`, and
    "instrument NOT validated".
  - The test `test_gate_constraint_instrument_kills_its_mutants` finds its patches by exact source text. AST
    re-emission changes quoting and drops comments, so that test would fail on every mutant, whatever the
    mutant does. Every kill would have been fake.
- **Instrument changes (no prediction changes):**
  1. Each mutant is now a **minimal text edit**: only the mutated node's source span changes, and every other
     byte is kept. Every mutant's text is checked to parse to exactly the same AST as the registered mutation;
     a mismatch stops the tool. All 351 passed that check, and the census is unchanged (same counts by file and
     operator, and the same two textually-null mutants).
  2. `null` is now the target byte-for-byte unchanged. `always-allow` is the same text edit, applied to
     `Gate.evaluate`'s first statement.
  3. T leaves out that one test (`--deselect`). It checks gate_constraint's own instrument by source text, not
     the kernel's behaviour, so it fails on any edit to an anchored line. Leaving it out can only lower T's
     kills, never raise them.
  4. T in the scratch copy runs 541 tests and skips 3. The two git-only tests do not take part.
- **Records:** launch 1's control record stays in `blue_launch1.jsonl`. The amended run writes `blue_a1.jsonl`.

## Door (unrun)

**BT-002:** turn each GAP into a test that fails on that mutant and passes on main. Then re-run BT-001's
operators on the same targets, and predict that every GAP is killed with no new survivors.
