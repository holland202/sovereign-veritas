# EO-2 — Can an independent observer close the EO-1 gap, and where does it stop? Results

**Status:** Draft, self-tested. **Registered run: 5 of 7 held; P3 and P4 REFUTED.** Amendment 1: 3 of 3 held
(one of them not fresh). Both sabotage arms exit 1. P9: 6 property tests pass, and all 7 mutants are killed.
P10 is the door.
**Registration:** [docs/EO2_PREREG.md](EO2_PREREG.md) (`6981e7f`); Amendment 1 registered at `58a24d9`, after the
registered run (`679b4ce`) and before any amended code.
**Digests:** registered run `3f7a451075292af5d194e2677250f37c9614ca2b51d1489136d591de5505ff32`; Amendment 1
`0f5badf94843f6b79a5077b1d62d828dc19382281447755376f2ac1b74afc89f`. Container only, **NOT VALIDATED on the S25**.

## What went wrong, first

1. **P3 and P4 were REFUTED by my own registration error.** In A4 the valve started `open` and the wrong-action
   executor closed it. R2 and R2u both said `UNOBSERVABLE`: the attack got through. The registered rule checks
   "the expected state was already there" before "something changed". The design note in the same
   registration said A4 would not be `UNOBSERVABLE`. Rule and note contradict each other, and I did not check
   one against the other before registering. The result is kept as run, and CI reproduces it.
2. **The fix came after the result.** Amendment 1 adds a stricter rule (R2s): with the expected state already
   there, any change is `WRONG_EFFECT`. Its catch on A4 is not confirmation, because A4 is the case that
   prompted it. The fresh evidence is A8 (below) and the absence of new false alarms.
3. **The first draft of the property tests could not reach `OK`.** Its random generator never produced "the
   expected change and nothing else". Every rule assertion passed, but the coverage assertion failed. The
   generator was fixed to produce that case, and the coverage assertion now passes. No module code changed.
4. **CI's red-team job caught a rule I broke.** JG-2 P1 refuses any hash in `sovereign_veritas/` that is not
   taken over the repository's `canonical_json`. My `action_digest` built the same canonical form by hand with
   `json.dumps`, so P1 refused it. It now calls `canonical_json`, which produces the same bytes; no EO-2 verdict or
   digest changed. Mutant M7 was updated to match.

## Raw output (`results/eo2/run.txt`)

```
            C1  C2  C3  C4            A1                   A2                   A3            A4            A5         A6                A7
R0          OK  OK  OK  OK            OK                   OK                   OK            OK            OK         OK                OK
R1          OK  OK  OK  OK            OK                   OK                   RECEIPT_FAIL  RECEIPT_FAIL  OK         OK                OK
R2          OK  OK  OK  UNOBSERVABLE  UNAUTHORIZED_EFFECT  UNAUTHORIZED_EFFECT  NO_EFFECT     UNOBSERVABLE  NO_EFFECT  BINDING_MISMATCH  OK
R2u         OK  OK  OK  UNOBSERVABLE  UNAUTHORIZED_EFFECT  UNAUTHORIZED_EFFECT  NO_EFFECT     UNOBSERVABLE  NO_EFFECT  OK                OK
PARANOID    FLAG on every case
```

What happened to the valve (outside SV): A1 and A2 closed → open under REFUSE and DEFER (the M1 mutant). A3 and
A5 closed → closed under ALLOW/SUCCEEDED. A4 open → closed under ALLOW/SUCCEEDED for `open_valve`.

## Predictions

| | prediction | result |
|---|---|---|
| P1 | R0 (the record) detects 0 of 7 | HELD |
| P2 | R1 (executor receipt) detects only A3, A4 | HELD |
| P3 | R2 detects A1–A6 with the named verdicts, 0 false alarms | **REFUTED**: A4 returned `UNOBSERVABLE` |
| P4 | R2u misses only A6 and A7 | **REFUTED**: it also misses A4 (same cause) |
| P5 | R2 misses A7 (compromised observer) | HELD |
| P6 | C4 is `UNOBSERVABLE` | HELD |
| P7 | the paranoid checker false-alarms on C1–C3 | HELD |
| P8 | sabotage: R2 misses A1, A2, A4, false-alarms on C1, P3 refuted, exit 1 | HELD (A4 was already a miss) |
| P9 | property tests pass; ≥ 5 mutants all killed; existing suite still passes | HELD after the generator fix above: 6 passed, 7/7 killed, suite `519 passed, 49 skipped` |
| P10 | door: package format, real hardware, concurrent writers | not run |

**Amendment 1** (`results/eo2/amendment1_run.txt`):

| | prediction | result |
|---|---|---|
| Q1 (fresh) | A8, an unrelated valve opened while V1 stayed `open`: R2 `UNOBSERVABLE`, R2s `WRONG_EFFECT` | HELD |
| Q2 (fresh) | R2s: C1–C3 `OK`, C4 `UNOBSERVABLE`; no new false alarm | HELD |
| Q3 (not fresh) | R2s detects A1–A6 (A4 `WRONG_EFFECT`), misses A7 | HELD |
| Q4 | sabotage: R2s false-alarms `NO_EFFECT` on C1, exit 1 | HELD |

## What this shows and does not show

- **Labels and executor receipts leave the gap open where it matters.** The record (R0) catches nothing. A
  receipt (R1) catches an executor that does nothing or the wrong thing and says so. It misses a broken guard,
  because the workflow discards what the executor returns there, and it misses an executor that lies.
- **A bound, independent read-back catches all six of those** (R2s): the broken guard on REFUSE and DEFER, a
  no-op, a wrong action, a forged receipt and a replayed observation. This holds on a file-backed stand-in,
  checked by code I wrote.
- **Binding earns its place.** Without it (R2u), C1's honest observation attached to A5's lying run passes.
- **It moves trust; it does not remove it.** An observer the executor can write to (A7) passes everything. What
  you now have to trust is the observer's wiring, not the executor's word.
- **Some things can't be seen.** If the target already has the expected state and nothing changes (C4), no
  observer can tell an honest repeat from no action. R2s says `UNOBSERVABLE` rather than OK.
- **Not shown:** a real actuator or sensor; anything on the S25; observers running while other writers are
  active; a signed observation (binding here is integrity, not authenticity); the package and verifier path.

## What changed in the code

- New and opt-in: `sovereign_veritas/effect_observation.py` (`check_observed_effect`, `make_observation`,
  `action_digest`). `strict=True` (the default) is Amendment 1's rule; `strict=False` is the rule as first
  registered, kept so that run reproduces.
- New: `tools/eo2_probe.py`, `tools/eo2_mutants.py`, `tests/test_effect_observation.py`,
  `.github/workflows/eo2.yml`, and `results/eo2/`.
- Unchanged: `workflow.py`, the record, the package format, `V0_LIMITATIONS` and `verify_package.py`.

## Open (P10, Chad's decision)

- Whether observations enter the evidence package and `verify_package.py` checks them. That is a format change.
- A real observer on hardware, for example the S25 reading a sensor that the executor's process can't write.
- Concurrent writers: an observation window that someone else also writes in.
- The vehicle, model and companion action paths, which EO-1 also left open.

## Credit and provenance

Follows EO-1, whose question was prompted by Terry Snyder's Elyria harness. That credits a question, not an
endorsement either way. AI participation: Claude (Opus 5.5, Anthropic) wrote the registration, amendment,
module, harness, tests, mutants and this file. Human validation: not performed. Chad Holland chose EO-2 over the
alternatives offered and directed the work; no line review. Chad Holland is responsible for the final artifact.
