from dataclasses import dataclass, field

from sovereign_veritas.capability import Capability
from sovereign_veritas.interfaces.contracts import ActionProposal, Prediction
from sovereign_veritas.runtime import RuntimeState
from sovereign_veritas.verifier_registry import (
    VerifierRegistry,
    VerifierValidationStatus,
)
from sovereign_veritas.workflow import EvidenceWorkflow


@dataclass
class Sensor:
    def observe(self):
        return "obs"


@dataclass
class Predictor:
    def predict(self, observation):
        return Prediction(
            value="prediction",
            uncertainty=0.1,
            model_id="test",
        )


@dataclass
class Verifier:
    calls: int = 0
    status: str = "PASS"

    def verify(self, observation, prediction):
        self.calls += 1
        return {"status": self.status}


@dataclass
class Executor:
    calls: list = field(default_factory=list)

    def execute(self, action):
        self.calls.append(action)
        return {"ok": True}


@dataclass
class Sink:
    records: list = field(default_factory=list)

    def record(self, record):
        self.records.append(record)
        return record


def runtime():
    return RuntimeState(platform="android", python_version="3.14.6")


def action():
    return ActionProposal("read_only", "read", {})


def capability():
    return Capability("read_only", True, ("fresh",))


def build(status="PASS", registry=None):
    verifier = Verifier(status=status)
    executor = Executor()
    sink = Sink()

    wf = EvidenceWorkflow(
        sensor=Sensor(),
        predictor=Predictor(),
        verifier=verifier,
        executor=executor,
        evidence_sink=sink,
        verifier_registry=registry,
    )
    return wf, verifier, executor, sink


def test_validated_registry_allows_actual_verifier():
    registry = VerifierRegistry(min_coverage=0.5)
    registry.register("v1", object())
    registry.record_probe("v1", passed=True, meaningful=True)

    wf, verifier, executor, sink = build(registry=registry)

    result = wf.run(
        record_id="r1",
        input_digest="abc",
        capability=capability(),
        runtime=runtime(),
        action=action(),
        verifier_id="v1",
        metadata={"fresh": True},
    )

    assert result.decision.decision == "ALLOW"
    assert verifier.calls == 1
    assert len(executor.calls) == 1


def test_unvalidated_registry_defers_and_does_not_run_verifier():
    registry = VerifierRegistry()
    registry.register("v1", object())

    wf, verifier, executor, sink = build(registry=registry)

    result = wf.run(
        record_id="r2",
        input_digest="abc",
        capability=capability(),
        runtime=runtime(),
        action=action(),
        verifier_id="v1",
        metadata={"fresh": True},
    )

    assert result.decision.decision == "DEFER"
    assert "verification_insufficient_evidence" in result.decision.reasons
    assert verifier.calls == 0
    assert executor.calls == []


def test_failed_registry_refuses_and_does_not_run_verifier():
    registry = VerifierRegistry()
    registry.register("v1", object())
    registry.record_probe("v1", passed=False, meaningful=True)

    wf, verifier, executor, sink = build(registry=registry)

    result = wf.run(
        record_id="r3",
        input_digest="abc",
        capability=capability(),
        runtime=runtime(),
        action=action(),
        verifier_id="v1",
    )

    assert result.decision.decision == "REFUSE"
    assert "verification_not_passed" in result.decision.reasons
    assert verifier.calls == 0
    assert executor.calls == []


def test_unknown_registry_verifier_defers():
    registry = VerifierRegistry()
    wf, verifier, executor, sink = build(registry=registry)

    result = wf.run(
        record_id="r4",
        input_digest="abc",
        capability=capability(),
        runtime=runtime(),
        action=action(),
        verifier_id="missing",
    )

    assert result.decision.decision == "DEFER"
    assert verifier.calls == 0
    assert executor.calls == []


def test_requested_registry_without_registry_defers():
    wf, verifier, executor, sink = build()

    result = wf.run(
        record_id="r5",
        input_digest="abc",
        capability=capability(),
        runtime=runtime(),
        action=action(),
        verifier_id="v1",
    )

    assert result.decision.decision == "DEFER"
    assert verifier.calls == 0
    assert executor.calls == []


def test_registry_does_not_override_actual_verifier_result():
    registry = VerifierRegistry()
    registry.register("v1", object())
    registry.record_probe("v1", passed=True, meaningful=True)

    wf, verifier, executor, sink = build(status="FAIL", registry=registry)

    result = wf.run(
        record_id="r6",
        input_digest="abc",
        capability=capability(),
        runtime=runtime(),
        action=action(),
        verifier_id="v1",
    )

    assert result.decision.decision == "REFUSE"
    assert result.evidence.verification["status"] == "FAIL"
    assert verifier.calls == 1
    assert executor.calls == []
