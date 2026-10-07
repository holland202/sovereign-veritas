from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from .capability import Capability, CapabilityRegistry
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
from .verifier_registry import VerifierRegistry, VerifierValidationStatus


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
        verifier_registry: VerifierRegistry | None = None,
        reservations: Any | None = None,
        capability_registry: CapabilityRegistry | None = None,
    ) -> None:
        self.sensor = sensor
        self.predictor = predictor
        self.verifier = verifier
        self.adversary = adversary
        self.executor = executor
        self.evidence_sink = evidence_sink
        self.gate = gate or Gate()
        self.verifier_registry = verifier_registry
        # RK-2 (docs/RK2_PREREG.md): optional idempotency-key store (sovereign_veritas/idempotency.py).
        self.reservations = reservations
        # Custody (docs/CUSTODY_RESULTS.md): with a registry, the registry's current entry decides, not the object the
        # caller holds, so a revocation reaches the decision; and the Gate gets the registry, so parents are checked.
        # Without one, the caller-supplied Capability decides (issue #4, B2) and the record says so.
        self.capability_registry = capability_registry

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
        verifier_id: str | None = None,
        idempotency_key: str | None = None,
        lease_s: float = 30.0,
    ) -> WorkflowResult:
        # XB-1 (docs/EXECUTION_BOUNDARY_RESULTS.md): the sink's duplicate check runs inside record(),
        # i.e. after execute(), so a repeated record_id produced a second external effect before the
        # ledger refused it. Refuse it here, before anything runs. Covers sequential repeats only: a
        # concurrent race (X4) and an effect whose record fails to write (X5) are NOT closed by this.
        has_record = getattr(self.evidence_sink, "has_record", None)
        if has_record is not None and has_record(record_id):
            raise ValueError(f"duplicate record_id refused before execution: {record_id}")
        # RK-2: a key without a store would silently protect nothing. Refuse before anything runs.
        if idempotency_key is not None and self.reservations is None:
            raise ValueError("idempotency_key given but no reservation store: refused before execution")

        observation = self.sensor.observe()
        prediction = self.predictor.predict(observation)

        # FI-FIX F3 (docs/FI_FIX_PREREG.md; finding U9 in docs/FI_RESULTS.md): a NaN or infinite uncertainty
        # was allowed through and the action executed. Refuse before the gate and before any effect.
        uncertainty = prediction.uncertainty
        if (
            isinstance(uncertainty, (int, float))
            and not isinstance(uncertainty, bool)
            and not math.isfinite(uncertainty)
        ):
            raise ValueError(f"non-finite prediction uncertainty refused before execution: {uncertainty!r}")

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

        registry_verification: dict[str, Any] | None = None
        if verifier_id is None and self.verifier_registry is not None:
            # A configured registry cannot be bypassed by omitting the id.
            registry_verification = {
                "status": "INSUFFICIENT_EVIDENCE",
                "verifier_id": None,
                "registry_reason": "verifier_id_missing",
            }
        elif verifier_id is not None:
            if self.verifier_registry is None:
                registry_verification = {
                    "status": "INSUFFICIENT_EVIDENCE",
                    "verifier_id": verifier_id,
                    "registry_reason": "verifier_registry_missing",
                }
            else:
                validation = self.verifier_registry.validation(verifier_id)
                if validation is None:
                    registry_verification = {
                        "status": "INSUFFICIENT_EVIDENCE",
                        "verifier_id": verifier_id,
                        "registry_reason": "verifier_not_registered",
                    }
                elif validation.status is VerifierValidationStatus.FAILED:
                    registry_verification = {
                        "status": "FAIL",
                        "verifier_id": verifier_id,
                        "registry_reason": "verifier_validation_failed",
                    }
                elif validation.status is not VerifierValidationStatus.VALIDATED:
                    registry_verification = {
                        "status": "INSUFFICIENT_EVIDENCE",
                        "verifier_id": verifier_id,
                        "registry_reason": "verifier_not_validated",
                    }

        if registry_verification is not None:
            verification = registry_verification
        elif (
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

        custody = {"capability_source": "caller"}
        if self.capability_registry is not None:
            name = capability.name if capability is not None else (action.capability if action is not None else None)
            current = self.capability_registry.get(name) if name else None
            custody = {"capability_source": "registry",
                       "caller_capability_differs_from_registry": capability != current}
            capability = current
            evidence = evidence.with_updates(capability=capability.name if capability else None)
        evidence = evidence.with_updates(metadata={**dict(evidence.metadata), **custody})

        decision = self.gate.evaluate(
            evidence,
            capability,
            runtime,
            policy=policy,
            registry=self.capability_registry,
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

            if idempotency_key is not None:
                # RK-2: reserved before the effect. Raises ReservationRefused if the key exists in any state.
                # RK-3: the lease is the caller's to set; the token lets a late holder be recorded, not obeyed.
                holder_token = self.reservations.reserve(idempotency_key, lease_s)
            try:
                execution_result = self.executor.execute(action)
            except Exception as exc:
                failed_metadata = dict(evidence.metadata)
                if idempotency_key is None:
                    failed_metadata["execution_status"] = "FAILED"
                else:
                    # RK-1 found FAILED recorded where the effect had happened. With a key the honest label is
                    # UNKNOWN; the key is held until a person releases it.
                    failed_metadata["execution_status"] = "UNKNOWN"
                    failed_metadata["idempotency_key"] = idempotency_key
                    try:
                        self.reservations.unknown(idempotency_key, str(exc), token=holder_token)
                    except Exception:
                        pass  # the reservation stays IN_FLIGHT, then UNKNOWN when its lease ends: still refused
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

            if idempotency_key is not None:
                self.reservations.complete(idempotency_key, token=holder_token)  # before the record: a failed record write cannot free the key
            success_metadata = dict(evidence.metadata)
            success_metadata["execution_status"] = "SUCCEEDED"
            if idempotency_key is not None:
                success_metadata["idempotency_key"] = idempotency_key

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
