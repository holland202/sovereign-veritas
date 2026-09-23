from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RuntimeState:
    platform: str
    python_version: str
    thermal_status: str = "normal"
    compute_budget: str = "available"
    power_status: str = "stable"
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_healthy(self) -> bool:
        return self.thermal_status in {"normal", "cool"} and self.compute_budget != "exhausted"

    def to_dict(self) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "python_version": self.python_version,
            "thermal_status": self.thermal_status,
            "compute_budget": self.compute_budget,
            "power_status": self.power_status,
            "metadata": dict(self.metadata),
        }
