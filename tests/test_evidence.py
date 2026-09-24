import pytest

from sovereign_veritas.evidence import EvidencePackage, EvidenceRecord


def test_evidence_package_provenance_is_immutable():
    record = EvidenceRecord(
        record_id="pkg-immutable-1",
        input_digest="input-1",
        prediction={"value": "test"},
        verification={"status": "PASS"},
    )
    provenance = {"source": "original"}

    package = EvidencePackage(
        schema_version="1",
        record=record,
        provenance=provenance,
    )

    original_digest = package.package_digest

    provenance["source"] = "tampered"

    assert package.provenance["source"] == "original"
    assert package.package_digest == original_digest

    with pytest.raises(TypeError):
        package.provenance["source"] = "tampered-again"


def test_evidence_package_provenance_is_recursively_immutable():
    record = EvidenceRecord(
        record_id="pkg-nested-immutable-1",
        input_digest="input-1",
        prediction={"value": "test"},
        verification={"status": "PASS"},
    )
    provenance = {
        "source": {
            "name": "original",
            "tags": ["a", "b"],
        }
    }

    package = EvidencePackage(
        schema_version="1",
        record=record,
        provenance=provenance,
    )

    with pytest.raises(TypeError):
        package.provenance["source"]["name"] = "tampered"

    with pytest.raises(AttributeError):
        package.provenance["source"]["tags"].__setitem__(0, "tampered")

    provenance["source"]["name"] = "caller-tampered"
    provenance["source"]["tags"][0] = "caller-tampered"

    assert package.provenance["source"]["name"] == "original"
    assert package.provenance["source"]["tags"][0] == "a"
