from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class Prediction:
    value: Any
    uncertainty: Any | None = None
    model_id: str | None = None


@dataclass(frozen=True)
class ActionProposal:
    capability: str
    requested: str
    parameters: dict[str, Any]


class Sensor(Protocol):
    def observe(self) -> Any:
        ...


class Predictor(Protocol):
    def predict(self, observation: Any) -> Prediction:
        ...


class Adversary(Protocol):
    def attack(self, observation: Any, prediction: Prediction) -> dict[str, Any]:
        ...


class ActionExecutor(Protocol):
    def execute(self, action: ActionProposal) -> Any:
        ...


class Verifier(Protocol):
    def verify(self, observation: Any, prediction: Prediction) -> dict[str, Any]:
        ...


class AdversarialVerifier(Protocol):
    def verify_with_adversarial(
        self,
        observation: Any,
        prediction: Prediction,
        adversarial: dict[str, Any],
    ) -> dict[str, Any]:
        ...


class EvidenceSink(Protocol):
    def record(self, record: Any) -> Any:
        ...
