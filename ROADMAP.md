# Sovereign Veritas Implementation Roadmap

## Phase 1 — Evidence Backbone

Integrate:

- evidence ledger
- provenance schema
- vacuity/meaningful-test checks
- verification/evaluation records
- protected evidence artifacts
- structured uncertainty and evidence quality fields

Acceptance:

- deterministic serialization
- tamper detection
- explicit verification state
- retained failures/refutations
- independently inspectable evidence packages
- graded quality decisions by the Gate

**Status:** largely implemented in-kernel; Stage-0 fault injection measured.

### FileLedger writer boundary (measured 2026-09-24)

- Single writer: supported.
- Concurrent multi-writer: **UNSUPPORTED** (Stage-1: 4×50 → chain broken;
  reload failed closed). See `docs/CONCURRENCY_MEASUREMENT.md`.
- Options A (policy) / B (flock) / C (per-process + merge) are open.
  Choose deliberately; re-measure against the frozen baseline.

## Phase 2 — Safety and Governance

Integrate:

- capability registry
- hierarchical capabilities
- quality-bounded and step-bounded capabilities
- containment
- runtime/resource state
- Veritas Gate
- CapabilityGovernor (custody before registry mutation)
- BoundedMultiStepPlanner (Gate-only sequential steps)

Acceptance:

- unauthorized actions cannot execute
- unavailable prerequisites cannot become ALLOW
- incomplete evidence can DEFER
- evidence quality below threshold can DEFER
- policy violations REFUSE
- models cannot self-authorize
- parent capabilities must be authorized for children
- planner cannot manufacture ALLOW or bypass Gate

**Status:** implemented and device-tested (107 passed Termux).

## Phase 3 — Edge Intelligence

Integrate:

- local inference
- uncertainty
- conformal prediction
- controlled synthesis
- thermal/energy-aware compute selection

Acceptance:

- resource adaptation is measured
- uncertainty remains attached to predictions
- cloud is not silently required
- execution decisions are reproducible

## Phase 4 — Validation Domains

Integrate:

- sentinel-hai-validation
- sentinel-batadal-validation

Acceptance:

- datasets/splits are explicit
- ordinary changes and tested attacks are distinguishable
- failures remain visible
- claims are evidence-backed

## Phase 5 — Research Plugins

Integrate as isolated modules:

- principia-artificialis
- quasar / quasar-v2
- qsleuth / qolas-synthesis
- polytope-explorer

Acceptance:

- plugins cannot weaken governance
- speculative results are labeled
- inputs/outputs are explicit
- provenance is retained

## Phase 6 — Sovereign Suite

Build the integration layer around stable contracts:

sense → model → predict → uncertainty → propose action
→ Veritas Gate → bounded execution → verify → record evidence → adapt safely

## Non-goals

- monolithic repository architecture
- mandatory cloud dependency
- hidden telemetry
- silent fallback behavior
- unsupported autonomy claims
- experimental code masquerading as production capability
- treating green unit tests as concurrency-safety evidence

## Promotion Rule

Target → implemented only after code + verification evidence support the claim.
