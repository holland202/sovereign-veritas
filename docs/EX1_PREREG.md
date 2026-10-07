# EX-1 — a durable execution journal, scoped effect receipts, and a crash campaign: registration

**Status:** REGISTERED, nothing built or run. Committed alone, before `sovereign_veritas/execution.py`,
`sovereign_veritas/receipts.py` and the campaign tools exist. Baseline: `1fbdced`.

**Provenance.** Designed by Claude (Opus 5.5) at Chad Holland's direction; the same model builds, runs and judges. **Self-tested.**
Container (Linux x86_64) only. **S25 NOT VALIDATED.**

## Why

Open limits recorded elsewhere: XB-1 X4/X5 (`docs/EXECUTION_BOUNDARY_RESULTS.md`: a race, and an effect whose record fails
to write); EO-1 (`docs/EO1_RESULTS.md`: the record reports the workflow's account, not the effect; `SUCCEEDED` means the
executor returned); the review's F2/F2b (two effects, or an effect with no record, through `EvidenceWorkflow`). In
`EvidenceWorkflow` the durable record is written **after** `execute()`, and with an idempotency key the reservation store
holds the only trace of an effect whose record failed. The question is whether writing intent **before** dispatch, in one
durable, hash-chained journal per intent, removes the silent cases, and what it costs.

## What will be built

- `sovereign_veritas/execution.py`: `ExecutionJournal` (one append-only, hash-chained JSONL file per intent, named by
  `sha256(domain, principal, idempotency_key)`, created with `O_CREAT|O_EXCL`: the creation *is* the reservation; appends under
  an OS lock with fsync) and `ExecutionCoordinator` (reserve → Gate decision → **durable DISPATCHED before the executor is
  called** → executor → receipt check → attested/unconfirmed → optional independent observation → finalized). An explicit
  transition table; an illegal transition raises (fail closed). Recovery never re-dispatches an intent that reached DISPATCHED:
  it moves it to EFFECT_UNCONFIRMED (reconciliation required).
- `sovereign_veritas/receipts.py`: `sv.effect-receipt/1`, bound to record id, attempt id, command digest and authorization
  digest; signed with `ssh-keygen -Y sign` under namespace `sv-effect-receipt` (a different namespace from packages' `sv-package`,
  so a signature for one purpose does not verify for the other). **An executor receipt is the executor's attributable claim,
  not proof of the external effect.**
- States: RESERVED, AUTHORIZED, DEFERRED, REFUSED, DISPATCHED, EXECUTOR_ACKNOWLEDGED, EFFECT_ATTESTED, EFFECT_UNCONFIRMED,
  INDEPENDENTLY_CONFIRMED, EFFECT_DISPUTED, RECONCILED_NO_EFFECT, FINALIZED. EFFECT_DISPUTED exists only if X6 shows the
  distinction is needed (a receipt that says yes, an observer that says no).

## Invariants (checked by the campaign and the fuzzer)

I1 REFUSED never dispatches. I2 DEFERRED never dispatches. I3 one reservation never yields two dispatched attempts without an
intervening RECONCILED_NO_EFFECT. I4 one (domain, principal, key) never causes two effects. I5 a missing receipt never becomes
EFFECT_ATTESTED. I6 a receipt for another command never attests this one. I7 a receipt for another authorization never
attests this one. I8 recovery never moves an intent whose effect may have happened into a state that says it did not. I9 a
replayed terminal event never changes the terminal state. I10 a tampered journal is detected (chain), never read as valid.

## Predictions

| ID | Prediction | Refuted if |
|---|---|---|
| X1 | Crash campaign, honest executor: for every fault point (reserve, decision, dispatch-record, before/after execute, receipt, attest, finalize) and fault (process kill via `os._exit`, storage failure on journal append), followed by recovery and a retry with the same key: **effects ≤ 1** in every case | any case with 2 effects |
| X2 | Same campaign: whenever the world shows the effect, the journal's final state is one that admits it (ATTESTED, UNCONFIRMED, CONFIRMED, DISPUTED, FINALIZED), never REFUSED/DEFERRED/RECONCILED_NO_EFFECT/RESERVED/AUTHORIZED (I8) | any such case |
| X3 | Same campaign, `EvidenceWorkflow` with an idempotency key and a ledger sink, fault between `execute()` and the ledger write: **≥ 1** case where the world has an effect and the ledger has no record (XB-1 X5, the baseline) | 0 such cases (the baseline would not show the gap) |
| X4 | Same faults through the coordinator: **0** cases where the world has an effect and the journal has no DISPATCHED event before it | ≥ 1 |
| X5 | Receipts: missing (I5), another command's (I6), another authorization's (I7), another attempt's, wrong namespace, unknown key → never EFFECT_ATTESTED | any of these attests |
| X6 | Lying executor (valid signed receipt, no effect): EFFECT_ATTESTED without an observer (**a limit, expected**); with an independent observer that sees no effect: EFFECT_DISPUTED | ATTESTED is not reached without an observer (then receipts check something they cannot), or DISPUTED is not reached with one |
| X7 | State-machine fuzz, ≥ 2000 random event sequences (valid, invalid, duplicate, reordered events, crashes, retries, foreign receipts): **0** violations of I1–I10. With `--sabotage` (an illegal edge REFUSED→DISPATCHED added) the fuzzer finds a violation and minimizes it to ≤ 4 events | a violation without sabotage, or none found with it |
| X8 | Liveness cost: some faulted intents end in EFFECT_UNCONFIRMED although no effect happened (a crash after DISPATCHED was recorded and before the executor ran). Count reported; prediction: ≥ 1 | 0 (then the design is not as conservative as claimed) |

## Left unrun

Power loss on real hardware (fsync is trusted, not tested), network filesystems, Android storage, multiple machines, a
compromised journal directory (an attacker who can write the journal can rewrite it; the hash chain detects edits, not
replacement of the whole file), a malicious *observer* (X6 only models a malicious executor).
