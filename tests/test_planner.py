from __future__ import annotations

import pytest

from sovereign_veritas.capability import Capability, CapabilityRegistry
from sovereign_veritas.evidence import Ledger, LedgerSink
from sovereign_veritas.interfaces.contracts import ActionProposal, Prediction
from sovereign_veritas.planner import (
    BoundedMultiStepPlanner,
    BoundedPlan,
    PlanStep,
)
from sovereign_veritas.runtime import RuntimeState
from sovereign_veritas.workflow import EvidenceWorkflow


class _Sensor:
    def observe(self) -> dict:
        return {"obs": 1}


class _Predictor:
    def predict(self, observation: object) -> Prediction:
        return Prediction(value=observation, uncertainty=None, model_id="test")


class _Verifier:
    def verify(self, observation: object, prediction: Prediction) -> dict:
        return {"status": "PASS"}


class _Executor:
    def __init__(self) -> None:
        self.calls: list[ActionProposal] = []

    def execute(self, action: ActionProposal) -> str:
        self.calls.append(action)
        return f"ok:{action.requested}"


class _FailingExecutor:
    def __init__(self, fail_on: int) -> None:
        self.fail_on = fail_on
        self.calls = 0

    def execute(self, action: ActionProposal) -> str:
        self.calls += 1
        if self.calls >= self.fail_on:
            raise RuntimeError("executor_boom")
        return "ok"


def _runtime() -> RuntimeState:
    return RuntimeState(platform="android", python_version="3.14.6")


def _step(
    record_id: str,
    capability: str = "read",
    requested: str = "read",
) -> PlanStep:
    return PlanStep(
        record_id=record_id,
        input_digest=f"digest-{record_id}",
        capability_name=capability,
        action=ActionProposal(
            capability=capability,
            requested=requested,
            parameters={},
        ),
    )


def _planner(
    *,
    registry: CapabilityRegistry | None = None,
    executor: object | None = None,
) -> tuple[BoundedMultiStepPlanner, Ledger, _Executor | _FailingExecutor]:
    if registry is None:
        registry = CapabilityRegistry()
        registry.register(Capability("read", True, required_evidence=()))
    if executor is None:
        executor = _Executor()
    ledger = Ledger()
    workflow = EvidenceWorkflow(
        sensor=_Sensor(),
        predictor=_Predictor(),
        verifier=_Verifier(),
        executor=executor,  # type: ignore[arg-type]
        evidence_sink=LedgerSink(ledger),
    )
    planner = BoundedMultiStepPlanner(
        workflow=workflow,
        registry=registry,
        runtime=_runtime(),
    )
    return planner, ledger, executor  # type: ignore[return-value]


def test_empty_plan_rejected_before_execution():
    planner, ledger, executor = _planner()
    with pytest.raises(ValueError, match="plan_empty"):
        planner.run(BoundedPlan(steps=()))
    assert len(ledger.all()) == 0
    assert executor.calls == []


def test_duplicate_record_ids_rejected_before_execution():
    planner, ledger, executor = _planner()
    plan = BoundedPlan(steps=(_step("a"), _step("a")))
    with pytest.raises(ValueError, match="duplicate_record_id"):
        planner.run(plan)
    assert len(ledger.all()) == 0
    assert executor.calls == []


def test_unauthorized_capability_stops_without_execution():
    registry = CapabilityRegistry()
    registry.register(Capability("write", False))
    planner, ledger, executor = _planner(registry=registry)
    plan = BoundedPlan(steps=(_step("s1", capability="write", requested="write"),))
    result = planner.run(plan)
    assert result.completed is False
    assert result.steps_executed == 0
    assert result.stopped_reason is not None
    assert "REFUSE" in result.stopped_reason or "refuse" in result.stopped_reason.lower()
    assert executor.calls == []


def test_successful_two_step_plan():
    planner, ledger, executor = _planner()
    plan = BoundedPlan(steps=(_step("s1"), _step("s2")))
    result = planner.run(plan)
    assert result.completed is True
    assert result.steps_executed == 2
    assert result.stopped_reason is None
    assert len(executor.calls) == 2
    assert ledger.all()[0].metadata["step_count"] == 1
    assert ledger.all()[1].metadata["step_count"] == 2


def test_refuse_at_step_2_prevents_step_3():
    registry = CapabilityRegistry()
    registry.register(Capability("read", True))
    registry.register(Capability("write", False))
    planner, ledger, executor = _planner(registry=registry)
    plan = BoundedPlan(
        steps=(
            _step("s1", "read", "read"),
            _step("s2", "write", "write"),
            _step("s3", "read", "read"),
        )
    )
    result = planner.run(plan)
    assert result.completed is False
    assert result.steps_executed == 1
    assert result.steps_attempted == 2  # step 2 evaluated, refused
    assert len(executor.calls) == 1
    assert len(ledger.all()) == 2
    assert ledger.all()[1].decision == "REFUSE"


def test_plan_exceeding_max_steps_rejected_in_preflight():
    registry = CapabilityRegistry()
    registry.register(Capability("read", True, max_steps=1))
    planner, ledger, executor = _planner(registry=registry)
    plan = BoundedPlan(steps=(_step("s1"), _step("s2")))
    with pytest.raises(ValueError, match="plan_exceeds_capability_max_steps"):
        planner.run(plan)
    assert len(ledger.all()) == 0
    assert executor.calls == []


def test_executor_failure_stops_plan():
    executor = _FailingExecutor(fail_on=2)
    planner, ledger, _ = _planner(executor=executor)
    plan = BoundedPlan(steps=(_step("s1"), _step("s2"), _step("s3")))
    result = planner.run(plan)
    assert result.completed is False
    assert "executor_exception" in (result.stopped_reason or "")
    # step 1 succeeded and was recorded; step 2 failed and was recorded by workflow
    assert len(ledger.all()) >= 1
    assert executor.calls == 2


def test_planner_cannot_use_one_capability_to_authorize_another():
    registry = CapabilityRegistry()
    registry.register(Capability("read", True))
    registry.register(Capability("write", False))
    planner, ledger, executor = _planner(registry=registry)
    # Step claims write capability but tries to ride on read — preflight mismatch
    bad = PlanStep(
        record_id="bad",
        input_digest="d",
        capability_name="read",
        action=ActionProposal(capability="write", requested="write", parameters={}),
    )
    with pytest.raises(ValueError, match="action_capability_mismatch"):
        planner.run(BoundedPlan(steps=(bad,)))
    assert executor.calls == []


def test_missing_capability_rejected_in_preflight():
    planner, ledger, executor = _planner()
    plan = BoundedPlan(steps=(_step("s1", capability="nope", requested="nope")))
    with pytest.raises(ValueError, match="capability_missing"):
        planner.run(plan)
    assert len(ledger.all()) == 0


def test_plan_is_immutable():
    plan = BoundedPlan(steps=(_step("s1"),))
    with pytest.raises(Exception):
        plan.steps = ()  # type: ignore[misc]
