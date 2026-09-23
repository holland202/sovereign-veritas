# Sovereign Veritas

Sovereign Veritas is the runtime and governance layer for evidence-first autonomous systems.

It is intentionally small and tool-oriented. The goal is not to replace domain models or scientific verification packages, but to provide a deterministic contract for:

- local evidence capture
- claim/prediction provenance
- capability enforcement
- resource-aware runtime gating
- decision records that separate observation from action
- auditable operation on edge devices

## Architecture

The project is organized around a few core ideas:

1. Models produce observations, not proof.
2. Verification is a separate state from prediction.
3. Actions require a declared capability and evidence sufficiency.
4. The runtime may defer or refuse when the evidence is incomplete or the environment is unsafe.
5. Decisions are append-only evidence, not informal status messages.

## Core modules

- `sovereign_veritas.evidence` — evidence records and append-only ledger
- `sovereign_veritas.runtime` — local device/runtime state model
- `sovereign_veritas.capability` — capability registry and access checks
- `sovereign_veritas.decision` — deterministic gate for allow / defer / refuse
- `sovereign_veritas.adapters.veritas_science` — adapter for scientific verification

## Example policy

```python
from sovereign_veritas.capability import Capability, CapabilityRegistry
from sovereign_veritas.decision import Gate
from sovereign_veritas.evidence import EvidenceRecord
from sovereign_veritas.runtime import RuntimeState

capability = Capability(
    name="industrial_control.write",
    authorized=False,
    required_evidence=["fresh_sensor_window", "verified_prediction", "runtime_status"],
)
registry = CapabilityRegistry()
registry.register(capability)

runtime = RuntimeState(platform="android", thermal_status="normal", compute_budget="available")

record = EvidenceRecord(
    record_id="r-1",
    input_digest="abc",
    capability="industrial_control.write",
    prediction={"value": "ANOMALY"},
    verification={"status": "PASS"},
    metadata={"fresh_sensor_window": True, "verified_prediction": True, "runtime_status": "stable"},
)

decision = Gate().evaluate(record, capability, runtime)
print(decision.decision)
```

## Status

This repository is the v0.1 kernel for Sovereign Veritas. It establishes the first hard contract:

- evidence must be recorded;
- verification must be explicit;
- action requires declared capability and required evidence;
- the runtime controls whether the system is currently permitted to act;
- decisions are deterministic and auditable.

This package intentionally stays small and conservative. It is an integration layer, not a replacement for domain-specific scientific packages.
