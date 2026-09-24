from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .capability import Capability, CapabilityRegistry
from .evidence import EvidenceRecord
from .interfaces.contracts import EvidenceSink


class CapabilityGovernor:
    """Authorize or revoke capabilities only after recording evidence.

    The model never calls this path directly for self-authorization.
    Callers (human, attested policy, or higher-level orchestration) supply
    the decision; this class makes the change custodial by default.
    """

    def __init__(self, registry: CapabilityRegistry, sink: EvidenceSink) -> None:
        self.registry = registry
        self.sink = sink

    def authorize(
        self,
        name: str,
        *,
        record_id: str,
        input_digest: str,
        reason: str,
        actor: str = "external",
        metadata: dict[str, Any] | None = None,
    ) -> tuple[Capability | None, EvidenceRecord]:
        """Record the authorization decision, then apply it to the registry."""
        before = self.registry.get(name)
        meta = dict(metadata or {})
        meta.update(
            {
                "governance_action": "authorize",
                "capability_name": name,
                "actor": actor,
                "reason": reason,
                "prior_authorized": before.authorized if before else None,
            }
        )

        evidence = EvidenceRecord(
            record_id=record_id,
            input_digest=input_digest,
            verification={"status": "PASS", "source": "capability_governor"},
            capability=name,
            decision="ALLOW",
            reasons=(f"authorize:{name}", reason),
            metadata=meta,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        self.sink.record(evidence)

        updated = self.registry.authorize(name)
        return updated, evidence

    def revoke(
        self,
        name: str,
        *,
        record_id: str,
        input_digest: str,
        reason: str,
        actor: str = "external",
        metadata: dict[str, Any] | None = None,
    ) -> tuple[Capability | None, EvidenceRecord]:
        """Record the revocation decision, then apply it to the registry."""
        before = self.registry.get(name)
        meta = dict(metadata or {})
        meta.update(
            {
                "governance_action": "revoke",
                "capability_name": name,
                "actor": actor,
                "reason": reason,
                "prior_authorized": before.authorized if before else None,
            }
        )

        evidence = EvidenceRecord(
            record_id=record_id,
            input_digest=input_digest,
            verification={"status": "PASS", "source": "capability_governor"},
            capability=name,
            decision="REFUSE",
            reasons=(f"revoke:{name}", reason),
            metadata=meta,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        self.sink.record(evidence)

        updated = self.registry.revoke(name)
        return updated, evidence
