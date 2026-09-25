import pytest

from sovereign_veritas.evidence import EvidenceRecord


def make_record():
    return EvidenceRecord(
        record_id="r1",
        input_digest="abc",
        prediction={"value": 1, "nested": {"x": [1, 2]}},
        verification={"status": "PASS"},
        capability="read",
        action={"name": "read"},
        decision="ALLOW",
        reasons=(),
        metadata={"source": "test"},
        uncertainty={"confidence": 0.9},
        evidence_quality=1.0,
        timestamp="2026-01-01T00:00:00+00:00",
        previous_digest=None,
    )


def test_evidence_record_is_recursively_immutable():
    record = make_record()

    with pytest.raises(TypeError):
        record.metadata["source"] = "changed"

    with pytest.raises(TypeError):
        record.prediction["nested"]["x"][0] = 99


def test_non_json_serializable_evidence_fails_fast():
    with pytest.raises(TypeError, match="non-JSON-serializable"):
        make_record().with_updates(
            metadata={"bad": object()},
        )


def test_with_updates_returns_new_record():
    original = make_record()
    updated = original.with_updates(decision="DEFER")

    assert original.decision == "ALLOW"
    assert updated.decision == "DEFER"
    assert updated.record_id == original.record_id


def test_with_updates_rejects_unknown_fields():
    record = make_record()

    with pytest.raises(TypeError, match="unknown EvidenceRecord fields"):
        record.with_updates(not_a_real_field=True)


def test_with_updates_preserves_immutable_nested_values():
    original = make_record()
    updated = original.with_updates(
        metadata={"nested": {"values": [1, 2, 3]}}
    )

    with pytest.raises(TypeError):
        updated.metadata["nested"]["values"][0] = 99
