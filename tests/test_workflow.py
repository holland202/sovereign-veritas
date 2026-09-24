from __future__ import annotations

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
