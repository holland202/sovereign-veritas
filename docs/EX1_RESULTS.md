# EX-1 results: write-ahead dispatch kept every crash case at one effect or fewer; the registered fuzz run REFUTED X7, and the fuzzer and proofs of concept found three journal defects of one kind (7 of 8 as registered)

Registration: `docs/EX1_PREREG.md`, commit `9f92326`, made before `sovereign_veritas/execution.py`,
`sovereign_veritas/receipts.py` and the EX-1 tools existed. Baseline `1fbdced`. That commit was local when the runs were
made and is pushed together with these results; a local commit orders events more weakly than a pushed one. Linux container
(x86_64, Python 3.13.16, OpenSSH 9.6p1; `results/ex1/final/ENV.txt`). **NOT VALIDATED on the S25.** Claude-assisted (Claude
Opus 5.5): the same model registered, built, ran and judged this, so it is **self-tested**. No independent reviewer has seen
EX-1. Chad Holland directed the work. He has not reviewed this text or the code line by line.

Every run, in order, with the code state it ran against: `results/ex1/README.md`.

## Failures, limits and corrections (first)

1. **X7 REFUTED in the registered run.** `results/ex1/fuzz_registered.txt`:
   `VIOLATION in sequence 10: I8: effect happened, journal ends in RECONCILED_NO_EFFECT`, minimized to
   `[{"kind": "submit", "decision": "ALLOW", "executor": "foreign", "observe": false}, {"kind": "raw", "to": "RECONCILED_NO_EFFECT"}]`.
   The rule that only a person or an observer may record RECONCILED_NO_EFFECT lived in
   `ExecutionCoordinator.reconcile_no_effect()`. `ExecutionJournal.append()` accepted it from any caller, after an effect.
   **Fix 1** moved the rule into the journal.
2. **The fuzzer then found the same defect class twice more, and a third member was found only by reading the code.**
   - After fix 1: a raw `append(EFFECT_ATTESTED)` with no receipt was accepted (I5). **Fix 2**: the journal takes the
     receipt verifier and refuses EFFECT_ATTESTED without a receipt that it accepts for the dispatched attempt.
   - After fix 2, the corrected fuzzer printed `0 violations in 2000 sequences` (`fuzz_postfix2b.txt`, 13096 operations)
     while a crash path existed. Two sequences written from reading `recover()` (`directed_prefix3.txt`) raised
     `unhandled KeyError in the code under test: KeyError('receipt')` and `KeyError('context')`. An exploratory run on
     another seed found the first one at sequence 360 (`fuzz_explore_20000.txt`). **A clean fuzz run is a statement about
     coverage, not proof of absence.**
   - Three proofs of concept with real ssh receipts (`tools/ex1_poc_binding.py`, output `poc_binding_prefix3.txt`):
     **P1** `ACCEPTED: reserved for sha256:265329e02d888cad..., final EFFECT_ATTESTED by a receipt for sha256:99f22b2ce36373a7...`
     (I6 at the journal level), **P2** `replayed old receipt -> EFFECT_ATTESTED (attempt ids used: ['a1', 'a1'])`, **P3**
     `ACCEPTED: AUTHORIZED by 'anyone' with detail {}`. **Fix 3** (`_admit`) makes the journal check each transition's
     evidence, on write and again on read.

   None of the five was reachable through `ExecutionCoordinator`, which always supplied the evidence. All five were
   reachable by any other caller of `append()`. **Lesson:** a durable state machine has to check the evidence for each of
   its own transitions. It cannot rely on its usual caller to do so.
3. **`EvidenceWorkflow` is unchanged.** The baseline still shows the gap: `baseline EvidenceWorkflow crash after_execute
   effects=1 ledger_records=0` and the same `after_complete` (X3). `ExecutionCoordinator` is a prototype beside the workflow
   that `README.md` describes. It does not replace it. Until the two are joined, the execution path that exists for users
   keeps XB-1 X5's effect-without-record case.
4. **Liveness cost (X8).** Of 22 faulted intents, 4 end `EFFECT_UNCONFIRMED` with no effect (a crash after DISPATCHED was
   written, before the executor ran), and 4 end `EFFECT_UNCONFIRMED` with the effect in the world (a crash after the
   executor ran, before its receipt was written). Either way, a person or a re-delivered receipt has to resolve it. The
   design never guesses. How often this would happen in service is unmeasured.
5. **A receipt proves who claimed the effect, not that it happened (X6, a limit, as registered).** A lying executor with a
   valid key gets `EFFECT_ATTESTED` without an observer. Only an independent observer moves it to `EFFECT_DISPUTED`.
6. **What fix 3 does not stop.** The actor of a world claim (`human:`, `observer:`) is declared, not authenticated. The
   chain is unkeyed. Anyone who can call `append()` can also write the file, and can write a history that obeys every
   rule. The rules stop an orchestrator's mistakes, not a liar. `tests/test_execution.py::test_limit_the_actor_is_declared_not_authenticated`
   pins this as a limit. AUTHORIZED carries a declared ALLOW. The journal cannot tell whether the Gate produced it.
7. **Four instrument defects, each kept with its output** (deviations 1, 2, 2b and 3 below). Two output files were
   overwritten by later runs: one is restored verbatim from the session log and labelled RECONSTRUCTED; the other was
   rewritten with the same refusals. Four reruns were printed but never saved; they are listed as *log only*. The code under
   test was not committed between runs (`results/ex1/README.md` names each state).
8. **Windows: not run.** The journal's lock moved from the journal file to a sidecar `.lock` file. Windows `LockFile` is
   mandatory, so locking the journal would stop this process's own second handle from reading it. That conclusion comes
   from the documentation. The code was changed before any Windows run, so the failure itself was never observed. CI on
   `windows-latest` will be the first Windows run of this code.
9. **The registered anti-vacuity control for X7 no longer works.** It added the illegal edge REFUSED→DISPATCHED to the
   table and made the coordinator dispatch on REFUSE. Fix 3 makes a dispatch bind the authorization immediately before it,
   so after fix 3 the edge alone produces nothing (P-c, predicted). Deviation 3 adds `--sabotage-deep`, which removes both
   rules. `tools/ex1_test_mutants.py` shows the equivalence: the edge alone SURVIVES and the edge with the binding rule
   removed is KILLED.

## Outcome (X1–X8)

| ID | Prediction | Result | Evidence |
|---|---|---|---|
| X1 | crash campaign, honest executor: effects ≤ 1 in every case | **HELD**: 22 of 22 cases ≤ 1 (14 with 1 effect ending EFFECT_ATTESTED, 4 with 1 ending EFFECT_UNCONFIRMED, 4 with 0 ending EFFECT_UNCONFIRMED) | `final/campaign_registered.txt` |
| X2 | an effect in the world never ends in a state that denies it | **HELD** | same |
| X3 | baseline `EvidenceWorkflow`: ≥ 1 case with an effect and no record | **HELD**: 2 of 2 (`effects=1 ledger_records=0`) | same |
| X4 | 0 effects without a DISPATCHED event for that attempt before it | **HELD**, with the v2 check (deviation 1). The v1 check could not fail | same; `campaign_sabotage_v2.txt` |
| X5 | missing, another command's, another authorization's, another attempt's receipt, wrong namespace, unknown key: never EFFECT_ATTESTED | **HELD**: `none of 6 registered cases attests`; the valid control attests through both paths | `final/receipts_x5.txt` |
| X6 | lying executor: EFFECT_ATTESTED alone (a limit), EFFECT_DISPUTED with an observer | **HELD**: `without observer -> EFFECT_ATTESTED; with observer -> EFFECT_DISPUTED` | `final/campaign_registered.txt` |
| X7 | ≥ 2000 fuzz sequences: 0 violations of I1–I10; sabotage found and minimized to ≤ 4 events | **REFUTED** (I8 in the registered run). The sabotage half held: I1/I2, 1 op | `fuzz_registered.txt`, `fuzz_sabotage.txt` |
| X8 | ≥ 1 faulted intent EFFECT_UNCONFIRMED with no effect | **HELD**: `4 of 22` | `final/campaign_registered.txt` |

After fixes 1–3, all runs were made against the committed code:
- `fuzz_registered.txt`: 0 violations in 2000 sequences (13096 operations).
- `--forge`: 0 violations in 2000 sequences (13202 operations, 1718 of them forged direct appends).
- Seed 20261008: 0 violations in 20000 sequences (129776 operations).

These are confirmations after fixes, exploratory under C-EXPLORE. They do not undo X7's refutation, which stays.

## Fixes

| Fix | Defect (found by) | Change | Pinned by |
|---|---|---|---|
| 1 | RECONCILED_NO_EFFECT from any caller (registered fuzz run) | actor and basis rule in `ExecutionJournal.append` | `test_world_claims_need_a_basis_and_a_person_or_observer` |
| 2 | EFFECT_ATTESTED without a receipt (fuzz, after fix 1) | `ExecutionJournal(verify=...)`, `_check_attestation`; no verifier means no attestation | `test_attestation_needs_a_bound_verified_receipt`, `test_no_verifier_no_attestation` |
| 3 | receipt-less EXECUTOR_ACKNOWLEDGED crashed `recover()` (reading, then exploratory fuzz); DISPATCHED bound to another command (P1); reused attempt id (P2); AUTHORIZED with no decision (P3) | `_admit`, on write and on read. AUTHORIZED needs ALLOW, an authorization digest and an attempt id new to the intent. DISPATCHED needs a context equal to {this intent, the attempt just authorized, the reserved command, its authorization}. EXECUTOR_ACKNOWLEDGED needs a receipt. EFFECT_ATTESTED's receipt must bind the dispatch. FINALIZED needs a basis and a person or observer, because once written it cannot be disputed. On read, schema and intent must match: a journal copied from another intent is refused | `test_dispatch_must_bind_*`, `test_an_attempt_id_cannot_be_authorized_twice`, `test_authorized_needs_*`, `test_acknowledged_needs_a_receipt_so_recovery_cannot_crash`, `test_a_rechained_*`, `test_a_journal_copied_from_another_intent_is_detected` |

## Deviations from the registration

- **Design, before any run.**
  - The registration said the journal file would be created with `O_CREAT|O_EXCL`. Reading the first draft showed that an
    empty reservation file could be taken by a second caller for another command. The first event is now written to a
    temporary file and published with `os.link`, which fails if the path exists. This happened before any test ran.
  - EFFECT_DISPUTED was built in before X6 ran. The registration made it conditional on X6 showing the distinction; X6
    then showed it.
- **Design, after runs.**
  - The sidecar lock (item 8 above).
  - append() never creates a journal: only reserve() does.
  - FINALIZED needs a basis (fix 3; not in the registration).
- **Deviation 1 (campaign).** v1's X4 asked whether any DISPATCHED event existed, so `campaign_sabotage.txt` printed
  `X4  HELD` under sabotage. The v1 sabotage also called the executor twice, which made effects 2 to 3 in every row. v2
  checks X4 per effect's attempt and makes the sabotage a pure reordering. The registered run's outcome did not change
  (v1 and v2 are identical); the sabotage became able to refute X4.
- **Deviation 2 (fuzzer).**
  - The raw-append legality model omitted I5's receipt condition, so `fuzz_postfix.txt` reported the journal's correct
    refusal as a violation.
  - Minimization accepted any violation, so `fuzz_postfix1_I5.txt` prints sequence 10's violation (I6/I7) beside a
    minimized sequence that fails as I5.
  - Corrected: ATTESTED is not legal for a receipt-less raw caller, and minimization keeps the violation's class. With the
    receipt check or the actor rule re-planted in memory, the corrected fuzzer still reports `illegal transition ... was
    accepted`.
- **Deviation 2b (fuzzer).** `check()` assumed every DISPATCHED had a context and crashed (`fuzz_postfix2.txt`, no
  verdict line, so no false pass). Corrected. An undeclared exception from the code under test is now a finding.
- **Deviation 3 (fuzzer).** `--sabotage-deep` (item 9 above). `--forge` (well-formed adversarial direct appends) and
  `--plant RULE` (each fix-3 rule removed, which must be found) were added after fix 3. They are not in the registration.

The raw-append legality model reads the implementation's own tables. It is a **derived oracle**: it checks that append()
enforces them, not that they are right. I1–I10 are computed from the journal's events and the world file. The world file
is ground truth that the coordinator's decisions never read: **partially independent**. The same author wrote both.

## Can the instruments fail?

| Instrument | Pass condition | Shown able to fail |
|---|---|---|
| campaign | 6 of 6 | `--sabotage`: `3 of 6`, X1, X4 and X8 REFUTED (`final/campaign_sabotage.txt`) |
| X5 | none of 6 attests, and the control attests | `--sabotage` (a verifier that accepts anything): exit 1. The journal's own binding check still refused the three binding cases |
| fuzz | 0 violations | `--sabotage-deep`: I1/I2 at sequence 6, 1 op. `--plant dispatch-binding`: sequence 176, 3 ops. `--plant attempt-reuse`: sequence 800, 3 ops. `--plant attest-binding`: sequence 26, 2 ops |
| `tests/test_execution.py` (105 cases) | all pass | `tools/ex1_test_mutants.py`: `23 of 24 killed; 1 declared equivalent with a killed witness`. The first run killed 19 of 23 and exposed four gaps. One was a redundant check, now removed; the other three got tests |
| PoC | all three refused | before fix 3, all three ACCEPTED |

CI runs every row of this table (`.github/workflows/tests.yml`, red-team job).

## What this establishes, and what it does not

It establishes, in this container, with fsync trusted, for this prototype:
- every tested crash point in the coordinator ends with at most one effect and a state that admits it;
- an effect never happens without a durable DISPATCHED for its attempt;
- the journal refuses histories that lack the evidence for a transition, whether that history is written through
  `append()` or found on disk. On disk it checks a receipt's binding but not its signature: the reader has no verifier,
  so a hand-written history with a bound but forged receipt reads as valid. That is item 6 again.

It does not establish:
- power loss on real hardware;
- Android storage or network filesystems;
- several machines;
- an honest observer, or authenticated people;
- that the Gate made the decision recorded as ALLOW;
- anything for `EvidenceWorkflow`, the path users run today.

## Decisions

| Item | Class | Why |
|---|---|---|
| Fixes 1–3 | IMPLEMENT (done) | each closed a reproduced failure, and each has a test that a mutant shows can fail |
| Join `ExecutionCoordinator` to `EvidenceWorkflow`, making the journal the record | EXPERIMENT FIRST | X3 should flip from ≥ 1 to 0. Needs its own registration: it changes the record format packages carry |
| Authenticated observations (signed by an observer key, like receipts) | EXPERIMENT FIRST | would turn the actor rule from a declaration into a check. A malicious observer is still unmodelled |
| Keyed or witnessed journal (signed checkpoints anchored in the witness log) | EXPERIMENT FIRST | the chain detects edits, not a rewritten history |
| Bind AUTHORIZED to the Gate's evaluation record (its digest) | DOCUMENT ONLY for now | cheap, but a declared digest is still declared. Pairs with the keyed journal |
| Treat "0 violations" from the fuzzer as evidence of safety | REJECT | `fuzz_postfix2b.txt` shows why |

## Left unrun (doors)

- Power loss on hardware (fsync is trusted, not tested).
- Android storage on the S25.
- Network filesystems and several machines.
- A malicious observer.
- A compromised journal directory.
- Windows (first run in CI).
- A second fuzzer written by someone else.
- An independent review of `execution.py` and `receipts.py`.
- **X9, registered here before any integration code exists, and not run:** with `ExecutionCoordinator` joined to `EvidenceWorkflow`, X3's two crash cases give
  0 effect-without-record cases. Refuted if either case ends with an effect and no journal event naming its attempt.

## Reproduce

```
python tools/ex1_campaign.py                 # exit 0: 6 of 6;   --sabotage: exit 1
python tools/ex1_receipts.py                 # exit 0: X5 HELD;  --sabotage: exit 1
python tools/ex1_fuzz.py                     # exit 0;  --forge: exit 0;  --sabotage-deep / --forge --plant RULE: exit 1
python tools/ex1_poc_binding.py              # exit 0: all three refused
python tools/ex1_test_mutants.py             # exit 0: every mutant killed or equivalent with a killed witness
python -m pytest -q tests/test_execution.py
```

## Addendum 1 (2026-10-07, after the results; the text above is unchanged)

1. **Windows: first run, in CI at `b7d072b`.** On `windows-latest` with Python 3.10, 3.12 and 3.14, every job printed
   `1 failed, 601 passed, 10 skipped`. The one failure was `tests/test_review_findings.py::test_f2_...` (item 3), so all
   105 cases of `tests/test_execution.py` passed on Windows. The sidecar lock (item 8 above) works there. This is CI's
   observation; there is still no desktop Windows run and no S25 run.
2. **JG-2 P1 was REFUTED at `b7d072b` by this code** (`docs/JG2_PREREG.md`, Record 2). Three hash sites used a local copy of
   canonical JSON instead of `canonical_json(...)`. The code now hashes `canonical_json(...)` and still refuses
   NaN/Infinity. On 20000 random finite values the bytes are identical, so no digest changes. The red-team job stopped at
   JG-2, so none of the EX-1 CI steps ran at `b7d072b`. Rerun after the change (`results/ex1/addendum1/`): campaign `6 of 6`;
   X5 `HELD`; fuzz `0 violations in 2000 sequences` (registered and `--forge`); `--sabotage-deep` `violation found`; PoC
   `all three refused`; `tests/test_execution.py` `105 passed`.
3. **The Windows failure came from a test, not from EX-1.** The review fix in `c7a9ee8` made `AnchoredFileLedger.contains()`
   read under the lock, and that lock needs `fcntl`. The F2 regression test ignored the repository's convention that the
   anchored ledger is POSIX-only. A run at `48ab26a` with `fcntl` removed, which is how Windows behaves, gave
   `effects = ['effect']` with no ledger file: the effect happened, and the ledger refused afterwards. After `c7a9ee8` the
   refusal comes before the effect. The F2 test now skips without `fcntl`, like the other anchored-ledger tests.
   `test_f2_without_flock_the_refusal_comes_before_the_effect` pins the new order on every platform.
