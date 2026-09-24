from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Capability:
    """Declared capability with optional hierarchy and evidence-quality bounds.

    Models cannot authorize themselves. Authorization is external.
    min_evidence_quality is a float in [0.0, 1.0]; None means no quality gate.
    parent, when set, must itself be authorized before this capability can ALLOW.
    max_steps is an advisory bound for temporary escalations (enforced by callers
    that track step counts via evidence metadata).
    """

    name: str
    authorized: bool = False
    required_evidence: tuple[str, ...] = ()
    description: str | None = None
    parent: str | None = None
    min_evidence_quality: float | None = None
    max_steps: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "authorized": self.authorized,
            "required_evidence": list(self.required_evidence),
            "description": self.description,
            "parent": self.parent,
            "min_evidence_quality": self.min_evidence_quality,
            "max_steps": self.max_steps,
        }


class CapabilityRegistry:
    def __init__(self) -> None:
        self._capabilities: dict[str, Capability] = {}

    def register(self, capability: Capability) -> Capability:
        self._capabilities[capability.name] = capability
        return capability

    def get(self, name: str) -> Capability | None:
        return self._capabilities.get(name)

    def authorize(self, name: str) -> Capability | None:
        """Authorize an already-registered capability. Does not create new ones."""
        capability = self._capabilities.get(name)
        if capability is not None:
            capability = Capability(
                name=capability.name,
                authorized=True,
                required_evidence=capability.required_evidence,
                description=capability.description,
                parent=capability.parent,
                min_evidence_quality=capability.min_evidence_quality,
                max_steps=capability.max_steps,
            )
            self._capabilities[name] = capability
        return capability

    def revoke(self, name: str) -> Capability | None:
        """Revoke authorization. Authorization changes must be ledgered by callers."""
        capability = self._capabilities.get(name)
        if capability is not None:
            capability = Capability(
                name=capability.name,
                authorized=False,
                required_evidence=capability.required_evidence,
                description=capability.description,
                parent=capability.parent,
                min_evidence_quality=capability.min_evidence_quality,
                max_steps=capability.max_steps,
            )
            self._capabilities[name] = capability
        return capability

    def check(self, name: str, evidence: dict[str, Any]) -> tuple[bool, list[str]]:
        capability = self.get(name)
        if capability is None:
            return False, [f"capability_missing:{name}"]
        if not capability.authorized:
            return False, [f"capability_not_authorized:{name}"]
        missing = [key for key in capability.required_evidence if not evidence.get(key)]
        return not missing, missing
