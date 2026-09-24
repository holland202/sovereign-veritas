from __future__ import annotations
import pytest

from dataclasses import dataclass, field

from sovereign_veritas.capability import Capability
from sovereign_veritas.interfaces.contracts import ActionProposal, Prediction
from sovereign_veritas.runtime import RuntimeState
from sovereign_veritas.workflow import EvidenceWorkflow


@dataclass
class FakeSensor:
    value: object = "observation"

    def observe(self):
        return self.value


@dataclass
class FakePredictor:
    prediction: Prediction = field(
        default_factory=lambda: Prediction(
            value="prediction",
            uncertainty=0.1,
            model_id="test-model",
        )
    )

    def predict(self, observation):
        return self.prediction


@dataclass
class FakeVerifier:
    status: str = "PASS"

    def verify(self, observation, prediction):
        return {"status": self.status}


@dataclass
class FakeExecutor:
    calls: list[ActionProposal] = field(default_factory=list)

    def execute(self, action):
        self.calls.append(action)
        return {"executed": action.requested}


@dataclass
class FakeSink:
    records: list = field(default_factory=list)

    def record(self, record):
        self.records.append(record)
        return record


def runtime(**kwargs):
    return RuntimeState(
        platform="android",
        python_version="3.14.6",
        **kwargs,
    )


def workflow(verifier_status="PASS"):
    executor = FakeExecutor()
    sink = FakeSink()
    instance = EvidenceWorkflow(
        sensor=FakeSensor(),
        predictor=FakePredictor(),
        verifier=FakeVerifier(verifier_status),
        executor=executor,
        evidence_sink=sink,
    )
    return instance, executor, sink


def action():
    return ActionProposal(
        capability="read_only",
        requested="read",
        parameters={"target": "test"},
    )


def capability():
    return Capability("read_only", True, ("fresh",))


def test_allow_executes_only_after_gate_allows():
    wf, executor, sink = workflow()
    result = wf.run(
        record_id="r1",
        input_digest="abc",
        capability=capability(),
        runtime=runtime(),
        action=action(),
        metadata={"fresh": True},
    )

    assert result.decision.decision == "ALLOW"
    assert result.executed
    assert len(executor.calls) == 1
    assert len(sink.records) == 1
    assert sink.records[0].decision == "ALLOW"


def test_refused_capability_never_executes():
    wf, executor, sink = workflow()
    result = wf.run(
        record_id="r2",
        input_digest="abc",
        capability=Capability("read_only", False),
        runtime=runtime(),
        action=action(),
    )

    assert result.decision.decision == "REFUSE"
    assert not result.executed
    assert executor.calls == []
    assert sink.records[0].decision == "REFUSE"


def test_failed_verification_never_executes():
    wf, executor, sink = workflow(verifier_status="FAIL")
    result = wf.run(
        record_id="r3",
        input_digest="abc",
        capability=Capability("read_only", True),
        runtime=runtime(),
        action=action(),
    )

    assert result.decision.decision == "REFUSE"
    assert not result.executed
    assert executor.calls == []
    assert sink.records[0].decision == "REFUSE"


def test_missing_required_evidence_defers():
    wf, executor, sink = workflow()
    result = wf.run(
        record_id="r4",
        input_digest="abc",
        capability=capability(),
        runtime=runtime(),
        action=action(),
    )

    assert result.decision.decision == "DEFER"
    assert "missing_required_evidence:fresh" in result.decision.reasons
    assert not result.executed
    assert executor.calls == []


def test_unavailable_runtime_refuses():
    wf, executor, sink = workflow()
    result = wf.run(
        record_id="r5",
        input_digest="abc",
        capability=Capability("read_only", True),
        runtime=runtime(thermal_status="unavailable"),
        action=action(),
    )

    assert result.decision.decision == "REFUSE"
    assert not result.executed
    assert executor.calls == []


def test_unhealthy_runtime_defers():
    wf, executor, sink = workflow()
    result = wf.run(
        record_id="r6",
        input_digest="abc",
        capability=Capability("read_only", True),
        runtime=runtime(thermal_status="hot"),
        action=action(),
    )

    assert result.decision.decision == "DEFER"
    assert not result.executed
    assert executor.calls == []


def test_model_prediction_does_not_authorize_capability():
    wf, executor, sink = workflow()
    result = wf.run(
        record_id="r7",
        input_digest="abc",
        capability=Capability("write", False),
        runtime=runtime(),
        action=ActionProposal("write", "write", {}),
        metadata={"authorized": True},
    )

    assert result.decision.decision == "REFUSE"
    assert executor.calls == []


def test_workflow_records_prediction_and_action():
    wf, executor, sink = workflow()
    result = wf.run(
        record_id="r8",
        input_digest="abc",
        capability=Capability("read_only", True),
        runtime=runtime(),
        action=action(),
    )

    record = sink.records[0]

    assert record.prediction["value"] == "prediction"
    assert record.prediction["model_id"] == "test-model"
    assert record.action["requested"] == "read"
    assert record.capability == "read_only"


def test_workflow_preserves_verification():
    wf, executor, sink = workflow()
    result = wf.run(
        record_id="r9",
        input_digest="abc",
        capability=Capability("read_only", True),
        runtime=runtime(),
        action=action(),
    )

    assert result.evidence.verification == {"status": "PASS"}


def test_workflow_requires_action_for_allow():
    wf, executor, sink = workflow()

    try:
        wf.run(
            record_id="r10",
            input_digest="abc",
            capability=Capability("read_only", True),
            runtime=runtime(),
            action=None,
        )
    except ValueError as exc:
        assert str(exc) == "ALLOW requires an action proposal"
    else:
        raise AssertionError("expected ValueError")

def test_execution_failure_is_not_silently_lost():
    @dataclass
    class FailingExecutor:
        calls: list[ActionProposal] = field(default_factory=list)

        def execute(self, action):
            self.calls.append(action)
            raise RuntimeError("execution failed")

    sink = FakeSink()
    wf = EvidenceWorkflow(
        sensor=FakeSensor(),
        predictor=FakePredictor(),
        verifier=FakeVerifier(),
        executor=FailingExecutor(),
        evidence_sink=sink,
    )

    try:
        wf.run(
            record_id="r11",
            input_digest="abc",
            capability=Capability("read_only", True),
            runtime=runtime(),
            action=action(),
        )
    except RuntimeError as exc:
        assert str(exc) == "execution failed"
    else:
        raise AssertionError("expected RuntimeError")

    assert len(sink.records) == 1
    assert sink.records[0].decision == "ALLOW"

def test_gate_refuse_or_defer_never_reaches_executor():
    @dataclass
    class RecordingExecutor:
        calls: list[ActionProposal] = field(default_factory=list)

        def execute(self, action):
            self.calls.append(action)
            return {"executed": True}

    for capability, runtime_state, expected in (
        (
            Capability("read_only", False),
            runtime(),
            "REFUSE",
        ),
        (
            Capability("read_only", True),
            runtime(thermal_status="hot"),
            "DEFER",
        ),
    ):
        executor = RecordingExecutor()
        sink = FakeSink()

        wf = EvidenceWorkflow(
            sensor=FakeSensor(),
            predictor=FakePredictor(),
            verifier=FakeVerifier(),
            executor=executor,
            evidence_sink=sink,
        )

        result = wf.run(
            record_id=f"gate-{expected.lower()}",
            input_digest="abc",
            capability=capability,
            runtime=runtime_state,
            action=action(),
        )

        assert result.decision.decision == expected
        assert executor.calls == []
        assert len(sink.records) == 1
        assert sink.records[0].decision == expected


@dataclass
class FakeAdversary:
    result: dict = field(
        default_factory=lambda: {
            "candidate_id": "r-adversarial",
            "attack_id": "a1",
            "attack_type": "counterexample",
            "target": "prediction",
            "result": "NO_COUNTEREXAMPLE_FOUND",
            "epistemic_status": "OBSERVATION",
            "truth_status": "UNDETERMINED",
        }
    )
    calls: list = field(default_factory=list)

    def attack(self, observation, prediction):
        self.calls.append((observation, prediction))
        return self.result


def workflow_with_adversary(verifier_status="PASS"):
    executor = FakeExecutor()
    sink = FakeSink()
    adversary = FakeAdversary()
    instance = EvidenceWorkflow(
        sensor=FakeSensor(),
        predictor=FakePredictor(),
        verifier=FakeVerifier(verifier_status),
        adversary=adversary,
        executor=executor,
        evidence_sink=sink,
    )
    return instance, executor, sink, adversary


def test_adversary_runs_after_prediction_and_before_verification():
    events = []

    @dataclass
    class OrderedPredictor:
        def predict(self, observation):
            events.append("predict")
            return Prediction("prediction", 0.1, "test-model")

    @dataclass
    class OrderedAdversary:
        def attack(self, observation, prediction):
            events.append("adversary")
            assert prediction.value == "prediction"
            return {"truth_status": "UNDETERMINED", "result": "OBSERVED"}

    @dataclass
    class OrderedVerifier:
        def verify(self, observation, prediction):
            events.append("verify")
            return {"status": "PASS"}

    wf = EvidenceWorkflow(
        sensor=FakeSensor(),
        predictor=OrderedPredictor(),
        verifier=OrderedVerifier(),
        adversary=OrderedAdversary(),
        executor=FakeExecutor(),
        evidence_sink=FakeSink(),
    )

    result = wf.run(
        record_id="order-1",
        input_digest="abc",
        capability=Capability("read_only", True),
        runtime=runtime(),
        action=action(),
    )

    assert events == ["predict", "adversary", "verify"]
    assert result.decision.decision == "ALLOW"


def test_adversarial_observation_enters_evidence_record():
    wf, executor, sink, adversary = workflow_with_adversary()

    result = wf.run(
        record_id="adv-1",
        input_digest="abc",
        capability=Capability("read_only", True),
        runtime=runtime(),
        action=action(),
    )

    assert result.evidence.metadata["adversarial"] == adversary.result
    assert sink.records[0].metadata["adversarial"] == adversary.result


def test_adversary_cannot_manufacture_gate_decision():
    wf, executor, sink, adversary = workflow_with_adversary()

    adversary.result = {
        "candidate_id": "r-adversarial",
        "attack_id": "a2",
        "attack_type": "counterexample",
        "target": "prediction",
        "result": "REFUTED",
        "epistemic_status": "OBSERVATION",
        "truth_status": "FALSE",
        "decision": "ALLOW",
    }

    result = wf.run(
        record_id="adv-2",
        input_digest="abc",
        capability=Capability("read_only", True),
        runtime=runtime(),
        action=action(),
    )

    assert result.decision.decision == "ALLOW"
    assert result.evidence.decision == "ALLOW"
    assert result.evidence.metadata["adversarial"]["decision"] == "ALLOW"
    assert len(executor.calls) == 1


def test_surviving_candidate_remains_undetermined():
    wf, executor, sink, adversary = workflow_with_adversary()

    result = wf.run(
        record_id="adv-3",
        input_digest="abc",
        capability=Capability("read_only", True),
        runtime=runtime(),
        action=action(),
    )

    assert result.evidence.metadata["adversarial"]["truth_status"] == "UNDETERMINED"
    assert result.decision.decision == "ALLOW"


def test_adversary_does_not_override_failed_verification():
    wf, executor, sink, adversary = workflow_with_adversary(verifier_status="FAIL")

    adversary.result["result"] = "NO_COUNTEREXAMPLE_FOUND"

    result = wf.run(
        record_id="adv-4",
        input_digest="abc",
        capability=Capability("read_only", True),
        runtime=runtime(),
        action=action(),
    )

    assert result.decision.decision == "REFUSE"
    assert not result.executed
    assert executor.calls == []


def test_no_adversary_preserves_existing_workflow_behavior():
    wf, executor, sink = workflow()

    result = wf.run(
        record_id="adv-5",
        input_digest="abc",
        capability=Capability("read_only", True),
        runtime=runtime(),
        action=action(),
    )

    assert result.decision.decision == "ALLOW"
    assert "adversarial" not in result.evidence.metadata
    assert len(executor.calls) == 1


def test_adversary_runs_even_when_gate_later_refuses_capability():
    wf, executor, sink, adversary = workflow_with_adversary()

    result = wf.run(
        record_id="adv-6",
        input_digest="abc",
        capability=Capability("read_only", False),
        runtime=runtime(),
        action=action(),
    )

    assert adversary.calls
    assert result.decision.decision == "REFUSE"
    assert executor.calls == []
    assert sink.records[0].metadata["adversarial"] == adversary.result


def test_adversarial_evidence_reaches_adversarial_aware_verifier():
    observed = {}

    @dataclass
    class AdversarialAwareVerifier:
        def verify(self, observation, prediction):
            raise AssertionError("legacy verifier path should not be used")

        def verify_with_adversarial(self, observation, prediction, adversarial):
            observed["observation"] = observation
            observed["prediction"] = prediction
            observed["adversarial"] = adversarial
            return {"status": "PASS", "source": "adversarial-aware"}

    adversary = FakeAdversary()
    wf = EvidenceWorkflow(
        sensor=FakeSensor(),
        predictor=FakePredictor(),
        verifier=AdversarialAwareVerifier(),
        adversary=adversary,
        executor=FakeExecutor(),
        evidence_sink=FakeSink(),
    )

    result = wf.run(
        record_id="adv-aware-1",
        input_digest="abc",
        capability=Capability("read_only", True),
        runtime=runtime(),
        action=action(),
    )

    assert observed["observation"] == result.observation
    assert observed["prediction"] == result.prediction
    assert observed["adversarial"] == adversary.result
    assert result.verification["source"] == "adversarial-aware"
    assert result.decision.decision == "ALLOW"


def test_verified_adversarial_refutation_reaches_gate():
    adversary = FakeAdversary(
        result={
            "candidate_id": "r-adversarial",
            "attack_id": "a-refute",
            "attack_type": "counterexample",
            "target": "prediction",
            "result": "REFUTED",
            "epistemic_status": "OBSERVATION",
            "truth_status": "UNDETERMINED",
            "decision": "ALLOW",
        }
    )

    @dataclass
    class AdversarialAwareVerifier:
        def verify(self, observation, prediction):
            raise AssertionError("legacy verifier path should not be used")

        def verify_with_adversarial(self, observation, prediction, adversarial):
            assert adversarial["result"] == "REFUTED"
            assert adversarial["truth_status"] == "UNDETERMINED"
            return {
                "status": "FAIL",
                "source": "independent-verification",
                "refutes_prediction": True,
            }

    executor = FakeExecutor()
    sink = FakeSink()

    wf = EvidenceWorkflow(
        sensor=FakeSensor(),
        predictor=FakePredictor(),
        verifier=AdversarialAwareVerifier(),
        adversary=adversary,
        executor=executor,
        evidence_sink=sink,
    )

    result = wf.run(
        record_id="adv-refute-1",
        input_digest="abc",
        capability=Capability("read_only", True),
        runtime=runtime(),
        action=action(),
    )

    assert result.verification["status"] == "FAIL"
    assert result.verification["refutes_prediction"] is True
    assert result.decision.decision == "REFUSE"
    assert not result.executed
    assert executor.calls == []

    # The adversary's own fabricated decision remains merely evidence.
    assert result.evidence.metadata["adversarial"]["decision"] == "ALLOW"
    assert sink.records[0].metadata["adversarial"]["result"] == "REFUTED"


def test_adversarial_verification_required_never_falls_back_to_legacy_verifier():
    """Required adversarial verification must fail closed.

    An adversary cannot force the workflow to accept its own result, and a
    verifier that lacks adversarial-aware verification must not silently fall
    back to the ordinary verifier when the adversary explicitly requires it.
    """
    class RequiringAdversary:
        def attack(self, observation, prediction):
            return {
                "requires_adversarial_verification": True,
                "decision": "ALLOW",
                "truth_status": "PASS",
            }

    class LegacyOnlyVerifier:
        def __init__(self):
            self.verify_called = False

        def verify(self, observation, prediction):
            self.verify_called = True
            return {
                "valid": True,
                "truth_status": "PASS",
            }

    verifier = LegacyOnlyVerifier()

    workflow = EvidenceWorkflow(
        sensor=FakeSensor(),
        predictor=FakePredictor(),
        verifier=verifier,
        adversary=RequiringAdversary(),
        executor=FakeExecutor(),
        evidence_sink=FakeSink(),
    )

    with pytest.raises(
        RuntimeError,
        match="adversarial verification required",
    ):
        workflow.run(
            record_id="adversarial-required",
            input_digest="digest",
            capability=None,
            runtime=runtime(),
        )

    assert verifier.verify_called is False
