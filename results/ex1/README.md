# results/ex1 — every EX-1 run, in order, kept as written

Registration: `docs/EX1_PREREG.md` (commit `9f92326`). Results and interpretation: `docs/EX1_RESULTS.md`.

**Provenance gap, stated first.** The code under test was not committed between runs. Every file below names the code
state it ran against (S0–S4, defined at the end). Only S4 (final) is in a commit: the commit that adds this directory. The
defects of S0–S3 are re-planted in memory by `tools/ex1_test_mutants.py`, `tools/ex1_fuzz.py --plant/--sabotage-deep`
and `tools/ex1_poc_binding.py`. Some reruns were printed but never saved to a file; they are listed as **log only**.

## Files, in the order they were produced

| File | State | Instrument | What it shows |
|---|---|---|---|
| `campaign_registered.txt` | S0 | campaign v1 | 6 of 6 as registered |
| `campaign_sabotage.txt` | S0 | campaign v1 | 4 of 6: **X4 HELD under sabotage**, so the X4 check could not fail; the sabotage called the executor twice (effects 2 to 3 in every row). Deviation 1 |
| `campaign_registered_v2.txt` | S0 | campaign v2 | 6 of 6 (identical to v1) |
| `campaign_sabotage_v2.txt` | S0 | campaign v2 | 3 of 6: X1, X4, X8 REFUTED; effects=2 and dispatched_recorded=False at before_append:DISPATCHED |
| `fuzz_registered.txt` | S0 | fuzz v1 | **The registered X7 run: REFUTED (I8)**, minimized to 2 ops |
| `fuzz_sabotage.txt` | S0 | fuzz v1 | the registered sabotage: I1/I2 found, 1 op |
| *(log only)* | S1 | fuzz v1, campaign v2 | sabotage: I1/I2 found; campaign: 6 of 6 |
| `fuzz_postfix1_I5.txt` | S1 | fuzz v1 | prints "I6/I7" for sequence 10 beside a minimized sequence that fails as I5 (deviation 2: minimization accepted any violation) |
| *(log only)* | S2 | fuzz v1, campaign v2 | sabotage: violation found; campaign: 6 of 6 |
| `fuzz_postfix.txt` | S2 | fuzz v1 | "legal transition EFFECT_UNCONFIRMED -> EFFECT_ATTESTED was refused": a false alarm, the instrument's legality model omitted I5 (deviation 2) |
| `fuzz_postfix2.txt` | S2 | fuzz v2 | the fuzzer crashed (KeyError in its own check() on a DISPATCHED with no context; no verdict line). Deviation 2b |
| `fuzz_sabotage_postfix2.txt` | S2 | fuzz v2 | I1/I2 found, 1 op |
| `fuzz_postfix2b.txt` | S2 | fuzz v2b | 0 violations in 2000 sequences (13096 ops), **although a crash path existed** |
| `directed_prefix3.txt` | S2 | fuzz v2b | two sequences written from reading the code: unhandled KeyError('receipt') and KeyError('context') in recover() |
| `fuzz_explore_20000.txt` | S2 | fuzz v2b | exploratory (another seed, 20000 sequences): finds the KeyError('receipt') class at sequence 360, minimized to 3 ops |
| `poc_binding_prefix3.txt` | S2 | PoC | P1, P2, P3 all ACCEPTED (the script had no exit code then) |
| `postfix3_predictions.txt` | — | — | predictions P-a to P-g, written before any S3 run |
| `poc_binding_postfix3.txt` | S3a | PoC | all three refused. The first S3 run printed the same three refusals (log only); this file was rewritten when the script got its exit code |
| `fuzz_postfix3.txt` | S3 | fuzz v3 | P-a: 0 violations in 2000 |
| `fuzz_forge_postfix3.txt` | S3 | fuzz v3 | P-b: 0 violations in 2000, 1718 forged appends |
| `fuzz_sabotage_postfix3.txt` | S3 | fuzz v3 | P-c: 0 violations (the registered sabotage is now stopped by fix 3; deviation 3) |
| `fuzz_sabotage_deep_postfix3.txt` | S3 | fuzz v3 | P-d: I1/I2 found, 1 op |
| `fuzz_explore_20000_postfix3.txt` | S3 | fuzz v3 | P-e: 0 violations in 20000 |
| `campaign_registered_v3.txt`, `campaign_sabotage_v3.txt` | S3 | campaign v2 | P-f: 6 of 6, X8 4 of 22; P-g: 3 of 6 |
| `fuzz_forge_plant_*.txt` | S3 | fuzz v3 | each fix-3 rule removed in turn: found and minimized (2 to 3 ops) |
| `receipts_x5.txt`, `receipts_x5_sabotage.txt` | S4 | X5 v1 | X5 HELD; sabotage exit 1 |
| `test_execution_mutants_v1.txt` | S3a | mutants v1 | 19 of 23 killed: four test gaps |
| `test_execution_mutants_v2_RECONSTRUCTED.txt` | S4 | mutants v1 | 22 of 23; **its file was overwritten by the next run**, restored verbatim from the session log |
| `test_execution_mutants.txt` | S4 | mutants v2 | 23 of 24 killed, 1 declared equivalent with a killed witness |
| `final/` | S4 | final versions of every instrument | every instrument rerun on the committed code; `final/ENV.txt` has the platform and file digests |

S3, S3a and S4 differ only in the journal's lock (a sidecar file), append() refusing to create a journal, and the read
path's duplicate table check folded into `_admit`. The S4 reruns in `final/` agree with the S3 runs.

## Code states

- **S0**: `execution.py` as first built (reservation already published with `os.link`; the `O_CREAT|O_EXCL` design of the
  registration was replaced before any run, see deviations in `docs/EX1_RESULTS.md`).
- **S1**: S0 + fix 1 (the actor and basis rule for world claims moved into `ExecutionJournal.append`).
- **S2**: S1 + fix 2 (EFFECT_ATTESTED needs a receipt the journal's verifier accepts).
- **S3**: S2 + fix 3 (`_admit`: AUTHORIZED, DISPATCHED, EXECUTOR_ACKNOWLEDGED and FINALIZED need their evidence, on write
  and on read; schema and intent checked on read).
- **S3a**: S3 + the journal's lock on a sidecar file + append() never creates a journal.
- **S4**: S3a + the read path's duplicate table check folded into `_admit` (one definition), and three test functions (four cases) added
  (`tests/test_execution.py`), plus one limit test (a receipt signature is not checked on read). Committed.

## Instrument versions

- campaign v1: X4 asked whether any DISPATCHED event existed; the sabotage called the executor before DISPATCHED and again
  in the normal path. v2: X4 asks it per effect's attempt; the sabotage is a pure reordering (deviation 1).
- fuzz v1: legality model without I5's receipt condition; minimization accepted any violation. v2: both corrected
  (deviation 2). v2b: a DISPATCHED with no context binds nothing instead of crashing the checker, and an undeclared
  exception from the code under test is reported as a finding (deviation 2b). v3: legality model follows fix 3, `--forge`,
  `--sabotage-deep` (deviation 3), `--plant`.
- mutants v1: scratch runner; v2: `tools/ex1_test_mutants.py`, equivalence needs a killed witness.
