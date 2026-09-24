from __future__ import annotations

import pytest

from sovereign_veritas.capability import Capability, CapabilityRegistry
from sovereign_veritas.decision import Gate
from sovereign_veritas.evidence import EvidenceRecord
from sovereign_veritas.runtime import RuntimeState


def runtime(**kwargs):
    return RuntimeState(platform="android", python_version="3.14.6", **kwargs)


def evidence(**kwargs):
    values = {
        "record_id": "r",
        "input_digest": "abc",
        "verification": {"status": "PASS"},
        "metadata": {"fresh": True},
    }
    values.update(kwargs)
    return EvidenceRecord(**values)


def test_allow_when_quality_meets_threshold():
    cap = Capability("analyze", True, ("fresh",), min_evidence_quality=0.7)
    rec = evidence(evidence_quality=0.85)
    assert Gate().evaluate(rec, cap, runtime()).decision == "ALLOW"


def test_defer_when_quality_below_threshold():
    cap = Capability("analyze", True, ("fresh",), min_evidence_quality=0.8)
    rec = evidence(evidence_quality=0.55)
    result = Gate().evaluate(rec, cap, runtime())
    assert result.decision == "DEFER"
    assert any("evidence_quality_below_threshold" in r for r in result.reasons)


def test_quality_from_metadata_is_accepted():
    cap = Capability("analyze", True, min_evidence_quality=0.6)
    rec = evidence(metadata={"fresh": True, "evidence_quality": 0.75})
    assert Gate().evaluate(rec, cap, runtime()).decision == "ALLOW"


def test_parent_must_be_authorized():
    registry = CapabilityRegistry()
    registry.register(Capability("read", False))
    registry.register(Capability("write", True, parent="read"))

    child = registry.get("write")
    result = Gate().evaluate(evidence(), child, runtime(), registry=registry)
    assert result.decision == "REFUSE"
    assert any("capability_parent_not_authorized" in r for r in result.reasons)


def test_parent_authorized_allows_child():
    registry = CapabilityRegistry()
    registry.register(Capability("read", True))
    registry.register(Capability("analyze", True, parent="read", min_evidence_quality=0.5))

    child = registry.get("analyze")
    rec = evidence(evidence_quality=0.9)
    assert Gate().evaluate(rec, child, runtime(), registry=registry).decision == "ALLOW"


def test_max_steps_exceeded_refuses():
    cap = Capability("explore", True, max_steps=3)
    rec = evidence(metadata={"fresh": True, "step_count": 5})
    result = Gate().evaluate(rec, cap, runtime())
    assert result.decision == "REFUSE"
    assert any("capability_max_steps_exceeded" in r for r in result.reasons)


def test_max_steps_within_bound_allows():
    cap = Capability("explore", True, max_steps=10)
    rec = evidence(metadata={"fresh": True, "step_count": 4})
    assert Gate().evaluate(rec, cap, runtime()).decision == "ALLOW"


def test_model_still_cannot_self_authorize():
    cap = Capability("write", False, min_evidence_quality=0.99)
    rec = evidence(prediction={"authorized": True}, evidence_quality=1.0)
    assert Gate().evaluate(rec, cap, runtime()).decision == "REFUSE"


def test_uncertainty_is_preserved_and_immutable():
    rec = evidence(
        uncertainty={"interval": [0.1, 0.9], "method": "conformal"},
        evidence_quality=0.8,
    )
    assert rec.uncertainty["method"] == "conformal"
    with pytest.raises(TypeError):
        rec.uncertainty["method"] = "changed"


def test_quality_or_default_fallback():
    rec = evidence()
    assert rec.quality_or_default(0.0) == 0.0
    rec2 = evidence(evidence_quality=0.42)
    assert rec2.quality_or_default() == 0.42
