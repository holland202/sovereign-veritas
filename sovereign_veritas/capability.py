from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Capability:
    name: str
    authorized: bool = False
    required_evidence: list[str] = field(default_factory=list)
    description: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "authorized": self.authorized,
            "required_evidence": list(self.required_evidence),
            "description": self.description,
        }


class CapabilityRegistry:
    """Simple registry for local action authorization and evidence requirements."""

    def __init__(self) -> None:
        self._capabilities: dict[str, Capability] = {}

    def register(self, capability: Capability) -> Capability:
        self._capabilities[capability.name] = capability
        return capability

    def get(self, name: str) -> Capability | None:
        return self._capabilities.get(name)

    def authorize(self, name: str) -> Capability | None:
        capability = self._capabilities.get(name)
        if capability is not None:
            self._capabilities[name] = Capability(
                name=capability.name,
                authorized=True,
                required_evidence=list(capability.required_evidence),
                description=capability.description,
            )
        return self._capabilities.get(name)

    def check(self, capability_name: str, evidence: dict[str, Any]) -> tuple[bool, list[str]]:
        capability = self._capabilities.get(capability_name)
        if capability is None:
            return False, [f"capability_missing:{capability_name}"]
        if not capability.authorized:
            return False, [f"capability_not_authorized:{capability_name}"]

        missing = [field for field in capability.required_evidence if not evidence.get(field)]
        return (not missing), missing
