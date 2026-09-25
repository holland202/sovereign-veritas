from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from .capability import Capability, CapabilityRegistry
from .evidence import EvidenceRecord
from .runtime import RuntimeState
from .verification import REFUSAL_REASONS, VerificationStatus


@dataclass(frozen=True)
class Decision:
    decision: str
    reasons: tuple[str, ...] = ()
    evidence_required: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "reasons": list(self.reasons),
            "evidence_required": list(self.evidence_required),
        }


class Gate:
    """Deterministic gate; authorization and action are separate concerns.

    REFUSE dominates hard prerequisite failures.
    DEFER is used for incomplete evidence, unhealthy runtime, or insufficient
    evidence quality relative to the capability's declared threshold.
    Models cannot authorize their own capabilities.
    """

    def evaluate(
        self,
        evidence: EvidenceRecord,
        capability: Capability | None,
        runtime: RuntimeState,
        policy: dict[str, Any] | None = None,
        registry: CapabilityRegistry | None = None,
    ) -> Decision:
        policy = policy or {}
        reasons: list[str] = []
        required: list[str] = []

        if not evidence.input_digest:
            return Decision("REFUSE", ("evidence_invalid:missing_input_digest",))

        verification_status = VerificationStatus.coerce(
            None if evidence.verification is None
            else evidence.verification.get("status")
        )

        if verification_status in REFUSAL_REASONS:
            return Decision(
                "REFUSE",
                (REFUSAL_REASONS[verification_status],),
            )

        # DEFER conditions accumulate and never short-circuit: an early DEFER
        # would mask a later REFUSE and drop the other DEFER reasons.
        if verification_status is VerificationStatus.INSUFFICIENT_EVIDENCE:
            reasons.append("verification_insufficient_evidence")
        elif verification_status is not VerificationStatus.PASS:
            return Decision(
                "REFUSE",
                ("verification_not_passed",),
            )

        if capability is None:
            return Decision("REFUSE", ("capability_missing",))

        # Identity, not truthiness: "false", "0" and 1 are not authorization.
        if capability.authorized is not True:
            return Decision("REFUSE", ("capability_not_authorized",))

        # Hierarchical check: parent must be authorized if declared.
        if capability.parent:
            if registry is None:
                return Decision("REFUSE", ("capability_parent_requires_registry",))
            parent = registry.get(capability.parent)
            if parent is None:
                return Decision("REFUSE", (f"capability_parent_missing:{capability.parent}",))
            if parent.authorized is not True:
                return Decision("REFUSE", (f"capability_parent_not_authorized:{capability.parent}",))

        requested_capability = (evidence.action or {}).get("capability")
        if requested_capability and requested_capability != capability.name:
            return Decision("REFUSE", ("action_capability_mismatch",))

        if not runtime.is_available():
            return Decision("REFUSE", ("runtime_state_unavailable",))

        if not runtime.is_healthy():
            reasons.append("runtime_not_healthy")

        for name in capability.required_evidence:
            # Attestation is the boolean True. "FAILED", {"ok": False} and
            # "false" are truthy, and are not evidence.
            if evidence.metadata.get(name) is not True:
                reasons.append(f"missing_required_evidence:{name}")
                required.append(name)

        # Evidence quality threshold (graded decision).
        if capability.min_evidence_quality is not None:
            quality = evidence.quality_or_default(default=0.0)
            if not (math.isfinite(quality) and 0.0 <= quality <= 1.0):
                reasons.append(f"evidence_quality_invalid:{quality!r}")
            elif quality < capability.min_evidence_quality:
                reasons.append(
                    f"evidence_quality_below_threshold:{quality:.4f}<{capability.min_evidence_quality:.4f}"
                )

        # Advisory step bound (callers that track steps put 'step_count' in metadata).
        if capability.max_steps is not None:
            step_count = evidence.metadata.get("step_count")
            if step_count is not None:
                # Steps count from 1 (planner contract); bools and negatives are not counts.
                if isinstance(step_count, bool) or not isinstance(step_count, int) or step_count < 1:
                    reasons.append("invalid_step_count_metadata")
                elif step_count > capability.max_steps:
                    return Decision("REFUSE", (f"capability_max_steps_exceeded:{step_count}>{capability.max_steps}",))

        requested = (evidence.action or {}).get("requested")
        allow_only = policy.get("allow_only")
        # A str allow_only would do substring matching ("read" in "read_raw").
        if allow_only is not None and not isinstance(allow_only, (list, tuple, set, frozenset)):
            return Decision("REFUSE", ("policy_invalid:allow_only_must_be_a_collection",), tuple(required))
        if requested and allow_only is not None and requested not in allow_only:
            return Decision("REFUSE", ("action_not_permitted_by_policy",), tuple(required))

        if reasons:
            return Decision("DEFER", tuple(reasons), tuple(required))

        return Decision("ALLOW")
