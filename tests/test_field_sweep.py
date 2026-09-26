"""The set of package fields a consistent rewrite can change undetected is pinned.

A CONSISTENT package claims consistency, not authenticity: fields no check recomputes, and inputs
the Gate's decision does not depend on, can be rewritten with every digest recomputed. This test
pins that set for the fixture package so it cannot grow or shrink silently. Binding a field
(signature, new check) must remove it here on purpose; losing a check adds a field and fails.
"""
import importlib.util
import pathlib
import tempfile

from test_package import make, thermal_fixture, vp

ROOT = pathlib.Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("field_sweep", ROOT / "tools" / "field_sweep.py")
fs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fs)

UNBOUND = {
    "artifact/name",
    "gate_inputs/capability/description",
    "gate_inputs/capability/max_steps",
    "gate_inputs/capability_registry/root-off/authorized",
    "gate_inputs/capability_registry/root-off/description",
    "gate_inputs/capability_registry/root-off/max_steps",
    "gate_inputs/capability_registry/root-off/min_evidence_quality",
    "gate_inputs/capability_registry/root-off/name",
    "gate_inputs/capability_registry/root-off/parent",
    "gate_inputs/capability_registry/root-on/authorized",
    "gate_inputs/capability_registry/root-on/description",
    "gate_inputs/capability_registry/root-on/max_steps",
    "gate_inputs/capability_registry/root-on/min_evidence_quality",
    "gate_inputs/capability_registry/root-on/name",
    "gate_inputs/capability_registry/root-on/parent",
    "measurement/elapsed_ms",
    "provenance/chain/0/record/action",
    "provenance/chain/0/record/capability",
    "provenance/chain/0/record/decision",
    "provenance/chain/0/record/evidence_quality",
    "provenance/chain/0/record/input_digest",
    "provenance/chain/0/record/prediction",
    "provenance/chain/0/record/record_id",
    "provenance/chain/0/record/timestamp",
    "provenance/chain/0/record/uncertainty",
    "provenance/chain/0/record/verification",
    "provenance/chain/1/record/metadata/step_count",
    "provenance/chain/1/record/record_id",
    "provenance/chain/1/record/timestamp",
    "provenance/chain/1/record/uncertainty",
    "resource_state/runtime/platform",
    "resource_state/runtime/python_version",
    "resource_state/thermal/zones/*/raw",
    "resource_state/thermal/zones/*/type",
    "resource_state/thermal/zones/*/zone",
    "verifier/validation/total_probes",
}


def _survivors():
    pkg = make(thermal=thermal_fixture(pathlib.Path(tempfile.mkdtemp())))
    return fs.sweep(vp, pkg)


def test_unbound_fields_are_exactly_the_pinned_set():
    total, survivors = _survivors()
    assert total > 100
    assert set(survivors) == UNBOUND


def test_load_bearing_fields_are_bound():
    _, survivors = _survivors()
    for field in ("artifact/bytes_b64", "artifact/sha256", "measurement/output_sha256",
                  "decision/decision", "gate_inputs/capability/authorized",
                  "resource_state/runtime/thermal_status", "freshness/status"):
        assert field not in survivors


def test_pin_can_fail_when_a_check_is_disabled(monkeypatch):
    """Anti-vacuity: with gate replay switched off, decision inputs become forgeable."""
    real = vp.verify
    monkeypatch.setattr(vp, "verify", lambda p, allow_recorded_only=False: [
        (n, ok or n == "gate_replay", d) for n, ok, d in real(p, allow_recorded_only)])
    _, survivors = _survivors()
    assert "gate_inputs/capability/authorized" in survivors
    assert set(survivors) != UNBOUND
