from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .capability import CapabilityRegistry
from .interfaces.contracts import ActionProposal
from .runtime import RuntimeState
from .workflow import EvidenceWorkflow, WorkflowResult


@dataclass(frozen=True)
class PlanStep:
    """One predeclared atomic action. Immutable after construction."""

    record_id: str
    input_digest: str
    capability_name: str
    action: ActionProposal
    policy: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BoundedPlan:
    """Immutable ordered sequence of PlanSteps. No authority of its own."""

    steps: tuple[PlanStep, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "steps", tuple(self.steps))


@dataclass(frozen=True)
class PlanResult:
    """Outcome of running a BoundedPlan."""

    plan: BoundedPlan
    step_results: tuple[WorkflowResult, ...]
    stopped_reason: str | None
    completed: bool

    @property
    def steps_executed(self) -> int:
        return sum(1 for r in self.step_results if r.executed)

    @property
    def steps_attempted(self) -> int:
        return len(self.step_results)


class BoundedMultiStepPlanner:
    """Run a predeclared sequence of actions through the existing Gate.

    This planner does not create capabilities, authorize anything, or bypass
    EvidenceWorkflow. It only sequences atomic Gate-authorized steps.

    Preflight (zero executions on failure):
      - plan non-empty
      - unique record_ids
      - each step has matching action.capability == capability_name
      - each capability exists in the registry
      - if any capability.max_steps is set, plan length must not exceed it

    Runtime:
      - step_count metadata starts at 1 and increases by 1 each step
      - DEFER or REFUSE stops immediately (no further steps)
      - executor exception stops after the existing workflow records failure
      - already-executed external actions are not rolled back
    """

    def __init__(
        self,
        *,
        workflow: EvidenceWorkflow,
        registry: CapabilityRegistry,
        runtime: RuntimeState,
    ) -> None:
        self.workflow = workflow
        self.registry = registry
        self.runtime = runtime

    def preflight(self, plan: BoundedPlan) -> None:
        if not plan.steps:
            raise ValueError("plan_empty")

        seen: set[str] = set()
        for index, step in enumerate(plan.steps):
            if not step.record_id:
                raise ValueError(f"missing_record_id_at_step:{index + 1}")
            if step.record_id in seen:
                raise ValueError(f"duplicate_record_id:{step.record_id}")
            seen.add(step.record_id)

            if not step.input_digest:
                raise ValueError(f"missing_input_digest_at_step:{index + 1}")

            if step.action.capability != step.capability_name:
                raise ValueError(
                    "action_capability_mismatch_at_step:"
                    f"{index + 1}:{step.action.capability}!={step.capability_name}"
                )

            capability = self.registry.get(step.capability_name)
            if capability is None:
                raise ValueError(f"capability_missing:{step.capability_name}")

            # If this capability declares max_steps, plan length must not
            # exceed it (step_count will be 1..N). Gate still enforces at runtime.
            if capability.max_steps is not None:
                if len(plan.steps) > capability.max_steps:
                    raise ValueError(
                        "plan_exceeds_capability_max_steps:"
                        f"{step.capability_name}:{len(plan.steps)}"
                        f">{capability.max_steps}"
                    )

    def run(self, plan: BoundedPlan) -> PlanResult:
        self.preflight(plan)

        results: list[WorkflowResult] = []
        stopped_reason: str | None = None

        for index, step in enumerate(plan.steps):
            step_number = index + 1
            capability = self.registry.get(step.capability_name)
            assert capability is not None  # preflight guarantee

            metadata = dict(step.metadata)
            metadata["step_count"] = step_number
            metadata["plan_length"] = len(plan.steps)
            metadata["plan_step_index"] = index

            try:
                result = self.workflow.run(
                    record_id=step.record_id,
                    input_digest=step.input_digest,
                    capability=capability,
                    runtime=self.runtime,
                    action=step.action,
                    policy=step.policy,
                    metadata=metadata,
                )
            except Exception as exc:
                # Workflow records failure evidence when executor fails.
                stopped_reason = f"executor_exception:{type(exc).__name__}:{exc}"
                break

            results.append(result)

            if result.decision.decision != "ALLOW":
                stopped_reason = (
                    f"gate_{result.decision.decision.lower()}:"
                    + ",".join(result.decision.reasons)
                )
                break

            if not result.executed:
                stopped_reason = "allow_without_execution"
                break

        completed = stopped_reason is None and len(results) == len(plan.steps)
        return PlanResult(
            plan=plan,
            step_results=tuple(results),
            stopped_reason=stopped_reason,
            completed=completed,
        )
