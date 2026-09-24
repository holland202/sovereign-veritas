import pytest
from sovereign_veritas.runtime import RuntimeState


def test_runtime_metadata_is_recursively_immutable():
    metadata = {
        "thermal_c": 35.0,
        "sensor": {"name": "original"},
        "tags": ["a", "b"],
    }

    runtime = RuntimeState(
        platform="test",
        python_version="3.14",
        metadata=metadata,
    )

    with pytest.raises(TypeError):
        runtime.metadata["thermal_c"] = 99.0

    with pytest.raises(TypeError):
        runtime.metadata["sensor"]["name"] = "tampered"

    with pytest.raises(AttributeError):
        runtime.metadata["tags"].__setitem__(0, "tampered")

    metadata["thermal_c"] = 99.0
    metadata["sensor"]["name"] = "caller-tampered"
    metadata["tags"][0] = "caller-tampered"

    assert runtime.metadata["thermal_c"] == 35.0
    assert runtime.metadata["sensor"]["name"] == "original"
    assert runtime.metadata["tags"][0] == "a"


def test_runtime_metadata_to_dict_returns_mutable_copy():
    runtime = RuntimeState(
        platform="test",
        python_version="3.14",
        metadata={
            "sensor": {"name": "original"},
            "tags": ["a", "b"],
        },
    )

    exported = runtime.to_dict()

    exported["metadata"]["sensor"]["name"] = "export-tampered"
    exported["metadata"]["tags"][0] = "export-tampered"

    assert runtime.metadata["sensor"]["name"] == "original"
    assert runtime.metadata["tags"][0] == "a"
