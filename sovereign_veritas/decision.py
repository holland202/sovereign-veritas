from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .capability import Capability
from .evidence import EvidenceRecord
from .runtime import RuntimeState


@dataclass(frozen=True)
class Decision:
    decision: str
    reasons: tuple[str, ...] = ()
    evidence_required: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {"decision": self.decision, "reasons": list(self.reasons), "evidence_required": list(self.evidence_required)}


class Gate:
    """Deterministic gate; authorization and action are separate concerns."""

    def evaluate(self, evidence: EvidenceRecord, capability: Capability | None, runtime: RuntimeState, policy: dict[str, Any] | None = None) -> Decision:
        policy = policy or {}
        reasons: list[str] = []
        required: list[str] = []
        if not evidence.input_digest:
            return Decision("REFUSE", ("evidence_invalid:missing_input_digest",))
        if evidence.verification is None or evidence.verification.get("status") != "PASS":
            return Decision("REFUSE", ("verification_not_passed",))
        if capability is None:
            return Decision("REFUSE", ("capability_missing",))
        if not capability.authorized:
            return Decision("REFUSE", ("capability_not_authorized",))
        if not runtime.is_available():
            return Decision("REFUSE", ("runtime_state_unavailable",))
        if not runtime.is_healthy():
            return Decision("DEFER", ("runtime_not_healthy",))
        for name in capability.required_evidence:
            if not evidence.metadata.get(name):
                reasons.append(f"missing_required_evidence:{name}")
                required.append(name)
        requested = (evidence.action or {}).get("requested")
        if requested and policy.get("allow_only") is not None and requested not in policy["allow_only"]:
            return Decision("REFUSE", ("action_not_permitted_by_policy",), tuple(required))
        if reasons:
            return Decision("DEFER", tuple(reasons), tuple(required))
        return Decision("ALLOW")
