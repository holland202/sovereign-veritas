# Real-World Validation

**Status:** Stage 0 implemented (synthetic fault injection). Higher stages are
design targets until measured.

## Claim discipline

| Evidence level | What you may claim |
|----------------|--------------------|
| Unit/integration tests | Implemented behavior passes specified tests |
| Fault injection (Stage 0) | Specified synthetic fault model rejected/contained |
| Device soak | Measured behavior under stated workload/window |
| Distribution shift | Measured performance on held-out shifts |
| Motivated red-team | Behavior under documented attack set |
| Real-task evaluation | Measured usefulness on stated task |

Passing one row does **not** upgrade the claim to the next row.

## Stage 0 — Deterministic fault injection (implemented)

Module: `sovereign_veritas.validation.ValidationSuite`

Checks:

1. **Ledger restart** — write N records, reload `FileLedger`, verify count + chain
2. **Torn persistence** — truncate JSONL at deterministic offsets; load must fail closed
3. **Duplicate writer identity** — second independent instance cannot append duplicate `record_id`
4. **Hostile persistence** — malformed JSON, field mutation without digest update, forged digest

Allowed claim when green:

> The specified synthetic fault model was rejected/contained.

**Not** claimed: physical power-cycle recovery, multi-process locking, concurrency safety, motivated adversary resistance.

## Stage 1 — Concurrency characterization (not implemented)

Multiple processes against one ledger. Measure interleaving, exceptions, final chain. Require verified chain **or** explicit fail-closed. No concurrency-safety claim until measured.

## Stage 2 — Physical durability on S25 (not implemented)

Termux interruption during writes, restart, recovery. Record device, FS, Python, interruption point, final verification.

## Stage 3 — Long-running soak (not implemented)

1h → 6h → 24h. Measure records, failures, memory, thermal where available. Missing measurements stay missing.

## Stage 4 — Distribution shift (not implemented)

Sealed streams, explicit digests, false accepts/rejects/DEFER/REFUSE under shift.

## Stage 5 — Motivated adversary (not implemented)

Attack evidence, ordering, identities, verifier output, authorization, cross-capability boundaries. Adversary stays outside authority boundary.

## Stage 6 — Real task integration (not implemented)

Real sensors, stronger local models, actual tasks — only after earlier stages leave evidence.
