# Real-World Validation

## Claim discipline

| Level | Claim allowed |
|-------|----------------|
| Unit/integration tests | Specified tests pass |
| Stage 0 fault injection | Synthetic fault model rejected/contained |
| Stage 1 concurrency | Measured multi-process outcomes (not safety) |
| Stage 2 durability | Measured interrupt/restart recovery (not physical power-loss) |
| Soak / shift / red-team / task | Only after measured evidence |

## Stage 0 — implemented + device-tested

`ValidationSuite` — restart, torn truncation, duplicate identity, hostile persistence.

## Stage 1 — measured; option A in force

`ConcurrencyProbe` — 4×50 baseline **and** control: chain broken, reload fail-closed.
Concurrent writers **UNSUPPORTED**. See `CONCURRENCY_MEASUREMENT.md`.

## Stage 2 — harness implemented

`DurabilityProbe` — single-writer `clean` / `torn_last_line` modes.
See `DURABILITY_MEASUREMENT.md`. Physical power interrupt remains operator-run.

## Stages 3–6 — not implemented

Soak, distribution shift, motivated adversary, real-task integration.
