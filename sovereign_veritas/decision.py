from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .capability import Capability
from .evidence import EvidenceRecord
from .runtime import RuntimeState


@dataclass(frozen=True)
class Decision:
    decision: str
    reasons: list[str] = field(default_factory=list)
    evidence_required: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "reasons": list(self.reasons),
            "evidence_required": list(self.evidence_required),
        }


class Gate:
    """Deterministic local action gate."""

    def evaluate(
        self,
        evidence: EvidenceRecord,
        capability: Capability,
        runtime: RuntimeState,
        policy: dict[str, Any] | None = None,
    ) -> Decision:
        policy = policy or {}
        reasons: list[str] = []
        evidence_required: list[str] = []

        if capability is None:
            return Decision("REFUSE", ["capability_missing"], [])

        if not capability.authorized:
            reasons.append("capability_not_authorized")

        if evidence.verification is None or evidence.verification.get("status") != "PASS":
            reasons.append("verification_not_passed")

        if not runtime.is_healthy():
            reasons.append("runtime_not_healthy")

        for field_name in capability.required_evidence:
            if not evidence.metadata.get(field_name):
                reasons.append(f"missing_required_evidence:{field_name}")
                evidence_required.append(field_name)

        if evidence.action and evidence.action.get("requested") and policy.get("allow_only"):
            if evidence.action["requested"] not in policy["allow_only"]:
                reasons.append("action_not_permitted_by_policy")

        if reasons:
            if "capability_not_authorized" in reasons:
                return Decision("REFUSE", reasons, evidence_required)
            if "verification_not_passed" in reasons or "runtime_not_healthy" in reasons or evidence_required:
                return Decision("DEFER", reasons, evidence_required)

        return Decision("ALLOW", reasons, evidence_required)
