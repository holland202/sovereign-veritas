from __future__ import annotations

from dataclasses import replace

import pytest

from sovereign_veritas.capability import Capability
from sovereign_veritas.decision import Gate
from sovereign_veritas.evidence import EvidenceRecord, Ledger
from sovereign_veritas.runtime import RuntimeState


def runtime(**kwargs):
    return RuntimeState(platform="android", python_version="3.14.6", **kwargs)


def evidence(**kwargs):
    values = {"record_id": "r", "input_digest": "abc", "verification": {"status": "PASS"}, "metadata": {"fresh": True}}
    values.update(kwargs)
    return EvidenceRecord(**values)


def test_allow_when_all_requirements_pass():
    capability = Capability("read_only", True, ("fresh",))
    assert Gate().evaluate(evidence(), capability, runtime()).decision == "ALLOW"


def test_defer_when_evidence_is_incomplete():
    capability = Capability("read_only", True, ("fresh", "verified"))
    result = Gate().evaluate(evidence(), capability, runtime())
    assert result.decision == "DEFER"
    assert "missing_required_evidence:verified" in result.reasons


def test_refuse_when_capability_is_unauthorized():
    assert Gate().evaluate(evidence(), Capability("write", False), runtime()).decision == "REFUSE"


def test_refuse_when_verification_fails():
    assert Gate().evaluate(evidence(verification={"status": "FAIL"}), Capability("read", True), runtime()).decision == "REFUSE"


def test_model_cannot_authorize_capability():
    capability = Capability("write", False)
    record = evidence(prediction={"authorized": True})
    assert Gate().evaluate(record, capability, runtime()).decision == "REFUSE"


def test_runtime_unavailable_does_not_become_safe():
    result = Gate().evaluate(evidence(), Capability("read", True), runtime(thermal_status="unavailable"))
    assert result.decision == "REFUSE"


def test_ledger_is_append_only_and_chained():
    ledger = Ledger()
    first = ledger.append(evidence(record_id="a"))
    second = ledger.append(evidence(record_id="b"))
    assert first.previous_digest is None
    assert second.previous_digest == first.record_digest
    assert ledger.verify()


def test_ledger_tampering_is_detected():
    ledger = Ledger()
    ledger.append(evidence(record_id="a"))
    ledger._records[0] = replace(ledger._records[0], input_digest="tampered")
    with pytest.raises(ValueError, match="tampered"):
        ledger.verify()


def test_ledger_rejects_duplicate_ids():
    ledger = Ledger()
    ledger.append(evidence(record_id="a"))
    with pytest.raises(ValueError, match="duplicate"):
        ledger.append(evidence(record_id="a"))
