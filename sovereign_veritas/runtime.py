from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .evidence import _freeze, _thaw

# Runtime vocabulary. Anything outside it - None, "", "unknown", a typo, a case
# variant - means the state cannot be read: unavailable, so the Gate REFUSEs.
THERMAL_HEALTHY = frozenset({"normal", "cool"})
THERMAL_DEGRADED = frozenset({"warning", "high", "hot", "critical", "unsafe"})
COMPUTE_HEALTHY = frozenset({"available", "constrained", "low"})
COMPUTE_DEGRADED = frozenset({"exhausted"})
POWER_HEALTHY = frozenset({"stable"})
POWER_DEGRADED = frozenset({"unsafe"})


def _known(value: Any, *sets: frozenset) -> bool:
    return isinstance(value, str) and any(value in s for s in sets)


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
            _known(self.thermal_status, THERMAL_HEALTHY)
            and _known(self.compute_budget, COMPUTE_HEALTHY)
            and _known(self.power_status, POWER_HEALTHY)
        )

    def is_available(self) -> bool:
        return (
            _known(self.thermal_status, THERMAL_HEALTHY, THERMAL_DEGRADED)
            and _known(self.compute_budget, COMPUTE_HEALTHY, COMPUTE_DEGRADED)
            and _known(self.power_status, POWER_HEALTHY, POWER_DEGRADED)
        )

    def to_dict(self) -> dict[str, Any]:
        return {"platform": self.platform, "python_version": self.python_version, "thermal_status": self.thermal_status, "compute_budget": self.compute_budget, "power_status": self.power_status, "metadata": _thaw(self.metadata)}
