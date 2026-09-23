from __future__ import annotations

from sovereign_veritas.capability import Capability, CapabilityRegistry
from sovereign_veritas.decision import Gate
from sovereign_veritas.evidence import EvidenceRecord, Ledger
from sovereign_veritas.runtime import RuntimeState


def test_gate_allows_valid_evidence():
    capability = Capability(
        name="read_only",
        authorized=True,
        required_evidence=["fresh_sensor_window", "verified_prediction"],
    )
    runtime = RuntimeState(
        platform="android",
        python_version="3.14.6",
        thermal_status="normal",
        compute_budget="available",
    )

    evidence = EvidenceRecord(
        record_id="r-1",
        input_digest="abc123",
        capability="read_only",
        prediction={"value": "ANOMALY"},
        verification={"status": "PASS"},
        metadata={"fresh_sensor_window": True, "verified_prediction": True},
    )

    decision = Gate().evaluate(evidence, capability, runtime)
    assert decision.decision == "ALLOW"


def test_gate_defers_when_evidence_is_missing():
    capability = Capability(
        name="read_only",
        authorized=True,
        required_evidence=["fresh_sensor_window", "verified_prediction"],
    )
    runtime = RuntimeState(
        platform="android",
        python_version="3.14.6",
        thermal_status="normal",
        compute_budget="available",
    )

    evidence = EvidenceRecord(
        record_id="r-2",
        input_digest="def456",
        capability="read_only",
        prediction={"value": "ANOMALY"},
        verification={"status": "PASS"},
        metadata={"fresh_sensor_window": True},
    )

    decision = Gate().evaluate(evidence, capability, runtime)
    assert decision.decision == "DEFER"


def test_gate_refuses_unauthorized_capability():
    capability = Capability(
        name="industrial_control.write",
        authorized=False,
        required_evidence=["fresh_sensor_window"],
    )
    runtime = RuntimeState(
        platform="android",
        python_version="3.14.6",
        thermal_status="normal",
        compute_budget="available",
    )

    evidence = EvidenceRecord(
        record_id="r-3",
        input_digest="ghi789",
        capability="industrial_control.write",
        prediction={"value": "NORMAL"},
        verification={"status": "PASS"},
        metadata={"fresh_sensor_window": True},
    )

    decision = Gate().evaluate(evidence, capability, runtime)
    assert decision.decision == "REFUSE"


def test_ledger_records_append_only_history():
    ledger = Ledger()
    ledger.append(EvidenceRecord(record_id="a", input_digest="x"))
    ledger.append(EvidenceRecord(record_id="b", input_digest="y"))
    assert [item.record_id for item in ledger.all()] == ["a", "b"]
