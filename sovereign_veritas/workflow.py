from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .capability import Capability
from .decision import Decision, Gate
from .evidence import EvidenceRecord
from .interfaces.contracts import (
    ActionExecutor,
    ActionProposal,
    Adversary,
    EvidenceSink,
    Predictor,
    Sensor,
    Verifier,
)
from .runtime import RuntimeState


@dataclass(frozen=True)
class WorkflowResult:
    observation: Any
    prediction: Any
    verification: dict[str, Any]
    evidence: EvidenceRecord
    decision: Decision
    execution_result: Any | None = None

    @property
    def executed(self) -> bool:
        return self.execution_result is not None


class EvidenceWorkflow:
    """Deterministic sense → predict → verify → gate → execute → record workflow."""

    def __init__(
        self,
        *,
        sensor: Sensor,
        predictor: Predictor,
        verifier: Verifier,
        adversary: Adversary | None = None,
        executor: ActionExecutor,
        evidence_sink: EvidenceSink,
        gate: Gate | None = None,
    ) -> None:
        self.sensor = sensor
        self.predictor = predictor
        self.verifier = verifier
        self.adversary = adversary
        self.executor = executor
        self.evidence_sink = evidence_sink
        self.gate = gate or Gate()

    def run(
        self,
        *,
        record_id: str,
        input_digest: str,
        capability: Capability | None,
        runtime: RuntimeState,
        action: ActionProposal | None = None,
        policy: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> WorkflowResult:
        observation = self.sensor.observe()
        prediction = self.predictor.predict(observation)

        adversarial = None
        if self.adversary is not None:
            adversarial = self.adversary.attack(observation, prediction)

        if adversarial is not None:
            verify_with_adversarial = getattr(
                self.verifier,
                "verify_with_adversarial",
                None,
            )
            requires_adversarial_verification = bool(
                adversarial.get(
                    "requires_adversarial_verification",
                    False,
                )
            )

            if (
                requires_adversarial_verification
                and verify_with_adversarial is None
            ):
                raise RuntimeError(
                    "adversarial verification required but verifier "
                    "does not implement verify_with_adversarial"
                )
        else:
            verify_with_adversarial = None

        if (
            verify_with_adversarial is not None
            and adversarial is not None
        ):
            verification = verify_with_adversarial(
                observation,
                prediction,
                adversarial,
            )
        else:
            verification = self.verifier.verify(
                observation,
                prediction,
            )

        action_dict = None
        if action is not None:
            action_dict = {
                "capability": action.capability,
                "requested": action.requested,
                "parameters": dict(action.parameters),
            }

        evidence = EvidenceRecord(
            record_id=record_id,
            input_digest=input_digest,
            prediction={
                "value": prediction.value,
                "uncertainty": prediction.uncertainty,
                "model_id": prediction.model_id,
            },
            verification=dict(verification),
            capability=capability.name if capability else None,
            action=action_dict,
            metadata=dict(metadata or {}),
        )

        if adversarial is not None:
            evidence_metadata = dict(evidence.metadata)
            evidence_metadata["adversarial"] = adversarial

            evidence = EvidenceRecord(
                record_id=evidence.record_id,
                input_digest=evidence.input_digest,
                prediction=evidence.prediction,
                verification=evidence.verification,
                capability=evidence.capability,
                action=evidence.action,
                decision=evidence.decision,
                reasons=evidence.reasons,
                metadata=evidence_metadata,
                timestamp=evidence.timestamp,
            )

        decision = self.gate.evaluate(
            evidence,
            capability,
            runtime,
            policy=policy,
        )

        evidence = EvidenceRecord(
            record_id=evidence.record_id,
            input_digest=evidence.input_digest,
            prediction=evidence.prediction,
            verification=evidence.verification,
            capability=evidence.capability,
            action=evidence.action,
            decision=decision.decision,
            reasons=decision.reasons,
            metadata=evidence.metadata,
            timestamp=evidence.timestamp,
        )

        execution_result = None

        if decision.decision == "ALLOW":
            if action is None:
                raise ValueError("ALLOW requires an action proposal")

            try:
                execution_result = self.executor.execute(action)
            except Exception as exc:
                failed_metadata = dict(evidence.metadata)
                failed_metadata["execution_status"] = "FAILED"
                failed_metadata["execution_error"] = str(exc)

                evidence = EvidenceRecord(
                    record_id=evidence.record_id,
                    input_digest=evidence.input_digest,
                    prediction=evidence.prediction,
                    verification=evidence.verification,
                    capability=evidence.capability,
                    action=evidence.action,
                    decision=evidence.decision,
                    reasons=evidence.reasons,
                    metadata=failed_metadata,
                    timestamp=evidence.timestamp,
                )

                self.evidence_sink.record(evidence)
                raise

            success_metadata = dict(evidence.metadata)
            success_metadata["execution_status"] = "SUCCEEDED"

            evidence = EvidenceRecord(
                record_id=evidence.record_id,
                input_digest=evidence.input_digest,
                prediction=evidence.prediction,
                verification=evidence.verification,
                capability=evidence.capability,
                action=evidence.action,
                decision=evidence.decision,
                reasons=evidence.reasons,
                metadata=success_metadata,
                timestamp=evidence.timestamp,
            )

        self.evidence_sink.record(evidence)

        return WorkflowResult(
            observation=observation,
            prediction=prediction,
            verification=verification,
            evidence=evidence,
            decision=decision,
            execution_result=execution_result,
        )
