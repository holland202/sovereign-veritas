"""BT-002: one test per BT-001 survivor that an input showed to be a real gap (docs/BT001_RESULTS.md, "15 GAPs
shown by an input"). Each test pins the behaviour of current main on that input, so the named mutant now fails it.

Each test name carries the BT-001 mutant ID it is meant to kill. The inputs follow tools/bt001_confirm.py. These
pin what the code does today; where CONTRACT.md states the rule (the step boundary, rule 11), the pin follows the
contract text. Self-tested: written by Claude (Anthropic, Opus 5.5).
"""
import math
from dataclasses import replace

import pytest

from sovereign_veritas.capability import Capability, CapabilityRegistry
from sovereign_veritas.decision import Gate
from sovereign_veritas.evidence import (EvidenceRecord, Ledger, LedgerSink, _validate_jsonable,
                                        canonical_json)
from sovereign_veritas.idempotency import (FileReservations, MemoryReservations, ReservationRefused,
                                           UNKNOWN)
from sovereign_veritas.interfaces.contracts import ActionProposal, Prediction
from sovereign_veritas.runtime import RuntimeState
from sovereign_veritas.workflow import EvidenceWorkflow

RT = RuntimeState(platform="t", python_version="3")


def _rec(**kw):
    return EvidenceRecord(record_id="r", input_digest="d", verification={"status": "PASS"}, **kw)


# --- capability.py ---------------------------------------------------------------------------------------------

def test_capability_0_unset_authorized_is_refused():
    assert Capability("x").authorized is False
    assert Gate().evaluate(_rec(), Capability("x"), RT).decision == "REFUSE"


def test_capability_16_missing_capability_check_is_false():
    ok, reasons = CapabilityRegistry().check("ghost", {})
    assert ok is False
    assert reasons == ["capability_missing:ghost"]


# --- decision.py (CONTRACT.md rule 11: REFUSE only when step_count is GREATER than max_steps) ------------------

def test_decision_72_step_count_equal_to_max_steps_is_not_refused():
    d = Gate().evaluate(_rec(metadata={"step_count": 3}), Capability("x", True, max_steps=3), RT)
    assert d.decision == "ALLOW"


def test_decision_72_control_one_over_is_refused():  # the same input one step over must still refuse
    d = Gate().evaluate(_rec(metadata={"step_count": 4}), Capability("x", True, max_steps=3), RT)
    assert d.decision == "REFUSE"
    assert "capability_max_steps_exceeded:4>3" in d.reasons


# --- evidence.py -----------------------------------------------------------------------------------------------

def test_evidence_59_append_requires_record_id():
    with pytest.raises(ValueError, match="record_id and input_digest are required"):
        Ledger().append(EvidenceRecord(record_id="", input_digest="d"))


def test_evidence_56_append_requires_input_digest():
    with pytest.raises(ValueError, match="record_id and input_digest are required"):
        Ledger().append(EvidenceRecord(record_id="r", input_digest=""))


def test_evidence_70_verify_detects_wrong_predecessor():
    led = Ledger()
    led.append(EvidenceRecord(record_id="a", input_digest="d"))
    led.append(EvidenceRecord(record_id="b", input_digest="d"))
    bad = replace(led._records[1], previous_digest="0" * 64)
    led._records[1] = bad
    led._digests[1] = bad.record_digest  # keep the record's own digest consistent: only the link is wrong
    with pytest.raises(ValueError, match="ledger chain broken at index 1"):
        led.verify()


def test_evidence_18_canonical_json_keeps_non_ascii_unescaped():
    out = canonical_json({"name": "café"})
    assert out == '{"name":"café"}'
    assert "\\u00e9" not in out


def test_evidence_20_validator_rejects_mixed_key_types():
    with pytest.raises(TypeError, match="non-JSON-serializable"):
        _validate_jsonable({1: "a", "b": 2})


def test_evidence_7_tuple_in_parameters_survives_freezing():
    r = _rec(action={"capability": "x", "requested": "r", "parameters": {"t": (1, 2)}})
    assert r.action["parameters"]["t"] == (1, 2)


# --- workflow.py (FI-FIX F3: a non-finite uncertainty is refused before the executor runs) --------------------

class _Sensor:
    def observe(self):
        return "o"


class _NaNPredictor:
    def predict(self, observation):
        return Prediction(value="v", uncertainty=math.nan, model_id="m")


class _Verifier:
    def verify(self, observation, prediction):
        return {"status": "PASS"}


class _Counting:
    def __init__(self):
        self.effects = 0

    def execute(self, action):
        self.effects += 1
        return {"n": self.effects}


def test_workflow_18_and_16_nan_uncertainty_refused_before_execution():
    ex = _Counting()
    wf = EvidenceWorkflow(sensor=_Sensor(), predictor=_NaNPredictor(), verifier=_Verifier(), executor=ex,
                          evidence_sink=LedgerSink(Ledger()))
    with pytest.raises(ValueError, match="non-finite prediction uncertainty refused before execution"):
        wf.run(record_id="r", input_digest="d", capability=Capability("x", True), runtime=RT,
               action=ActionProposal("x", "go", {}))
    assert ex.effects == 0


# --- idempotency.py --------------------------------------------------------------------------------------------

def test_idempotency_44_corrupt_reservation_file_is_refused(tmp_path):
    s = FileReservations(tmp_path)
    s._path("K").write_text("{", encoding="utf-8")
    with pytest.raises(ReservationRefused):
        s.reserve("K")


def test_idempotency_42_non_dict_reservation_file_is_refused(tmp_path):
    s = FileReservations(tmp_path)
    s._path("K").write_text('["state"]', encoding="utf-8")
    with pytest.raises(ReservationRefused):
        s.reserve("K")


def test_idempotency_38_store_directory_parents_are_created(tmp_path):
    target = tmp_path / "a" / "b"
    FileReservations(target)
    assert target.is_dir()


def test_idempotency_4_lease_expires_at_the_boundary(monkeypatch):
    import sovereign_veritas.idempotency as idem
    monkeypatch.setattr(idem.time, "time", lambda: 1000.0)
    s = MemoryReservations()
    s.reserve("K", lease_s=0)
    assert s.state("K") == UNKNOWN
