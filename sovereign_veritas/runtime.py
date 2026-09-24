from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .evidence import _freeze, _thaw


@dataclass(frozen=True)
class RuntimeState:
    platform: str
    python_version: str
    thermal_status: str = "normal"
    compute_budget: str = "available"
    power_status: str = "stable"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", _freeze(self.metadata))

    def is_healthy(self) -> bool:
        return (
            self.thermal_status in {"normal", "cool"}
            and self.compute_budget not in {"exhausted", "unavailable"}
            and self.power_status not in {"unsafe", "unavailable"}
        )

    def is_available(self) -> bool:
        return all(value not in {"", "unknown", "unavailable"} for value in (self.thermal_status, self.compute_budget, self.power_status))

    def to_dict(self) -> dict[str, Any]:
        return {"platform": self.platform, "python_version": self.python_version, "thermal_status": self.thermal_status, "compute_budget": self.compute_budget, "power_status": self.power_status, "metadata": _thaw(self.metadata)}
