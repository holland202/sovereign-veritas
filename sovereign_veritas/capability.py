from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Capability:
    name: str
    authorized: bool = False
    required_evidence: tuple[str, ...] = ()
    description: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "authorized": self.authorized, "required_evidence": list(self.required_evidence), "description": self.description}


class CapabilityRegistry:
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
            capability = Capability(capability.name, True, capability.required_evidence, capability.description)
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
