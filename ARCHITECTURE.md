# Sovereign Veritas Platform Architecture

Status: Target architecture / implementation contract

Sovereign Veritas is an evidence-first, sovereign edge-AI research platform.

Core loop:

sense → model → predict → act → verify → record evidence → adapt safely

## Layers

1. Evidence and Trust Foundation
   - evidence ledger
   - provenance
   - meaningful-test/vacuity detection
   - evaluation results
   - protected evidence artifacts
   - structured uncertainty and evidence quality

2. Governance and Containment
   - capability authorization
   - hierarchical capabilities
   - quality-bounded and step-bounded capabilities
   - containment
   - runtime/resource gating
   - Veritas Gate
   - ALLOW / DEFER / REFUSE

3. Edge Intelligence
   - local inference
   - uncertainty
   - conformal prediction
   - controlled synthesis
   - thermal/energy/latency adaptation

4. Industrial and Environmental Validation
   - HAI
   - BATADAL
   - anomaly detection
   - distribution shift
   - adversarial/evasive validation

5. Advanced Research Plugins
   - Principia
   - QUASAR
   - QSleuth
   - QOLAS
   - other experimental modules

6. Geometry and Visualization
   - latent-state inspection
   - uncertainty visualization
   - state transitions
   - verified geometric representations

7. Sovereign Suite
   - integration/control layer
   - orchestration
   - evidence inspection
   - bounded execution

## Veritas Gate

proposed action
    ↓
capability check (including parent hierarchy)
    ↓
containment check
    ↓
evidence sufficiency + quality threshold
    ↓
runtime / uncertainty / risk checks
    ↓
ALLOW / DEFER / REFUSE
    ↓
record decision + evidence

A model cannot authorize its own capability.

Evidence quality (when declared by a capability via min_evidence_quality)
must meet or exceed the threshold or the Gate returns DEFER with an
explicit reason. Step bounds (max_steps) are enforced when callers place
step_count in evidence metadata.

## Evidence Package

An important result should record, as applicable:

- input digest
- device identity
- model/code version
- training-data reference
- prediction
- uncertainty (structured)
- evidence quality (0.0–1.0)
- operating regime
- verification results
- capability/containment decision
- action and result
- reason
- known limitations
- provenance
- timestamps

## Integration Rule

Repositories remain independent modules with explicit interfaces.

Sovereign Veritas integrates them without erasing their provenance or turning the system into one monolithic codebase.

## Status Discipline

Interfaces do not constitute implementation.

A component becomes implemented only when supported by:

- code revision
- tests
- measured behavior
- known failures
- reproducibility information
- explicit integration boundary
