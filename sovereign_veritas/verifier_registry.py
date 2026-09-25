from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable


class VerifierValidationStatus(str, Enum):
    VALIDATED = "VALIDATED"
    UNTESTED = "UNTESTED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class VerifierValidation:
    verifier_id: str
    status: VerifierValidationStatus = VerifierValidationStatus.UNTESTED
    total_probes: int = 0
    meaningful_probes: int = 0
    meaningful_passes: int = 0
    failed_probes: int = 0
    min_coverage: float = 0.5

    @property
    def coverage(self) -> float:
        if self.total_probes == 0:
            return 0.0
        return self.meaningful_probes / self.total_probes

    def record(
        self,
        *,
        passed: bool,
        meaningful: bool = True,
    ) -> "VerifierValidation":
        total = self.total_probes + 1
        meaningful_probes = self.meaningful_probes + (1 if meaningful else 0)
        meaningful_passes = self.meaningful_passes + (
            1 if meaningful and passed else 0
        )
        failed_probes = self.failed_probes + (0 if passed else 1)

        if failed_probes:
            status = VerifierValidationStatus.FAILED
        elif (
            meaningful_probes > 0
            and meaningful_passes == meaningful_probes
            and meaningful_probes / total >= self.min_coverage
        ):
            status = VerifierValidationStatus.VALIDATED
        else:
            status = VerifierValidationStatus.UNTESTED

        return VerifierValidation(
            verifier_id=self.verifier_id,
            status=status,
            total_probes=total,
            meaningful_probes=meaningful_probes,
            meaningful_passes=meaningful_passes,
            failed_probes=failed_probes,
            min_coverage=self.min_coverage,
        )


@dataclass(frozen=True)
class _VerifierEntry:
    verifier: Any
    validation: VerifierValidation


class VerifierRegistry:
    """Registry for verifiers and their independently recorded validation state."""

    def __init__(self, *, min_coverage: float = 0.5) -> None:
        if not 0.0 <= min_coverage <= 1.0:
            raise ValueError("min_coverage must be in [0.0, 1.0]")
        self.min_coverage = min_coverage
        self._entries: dict[str, _VerifierEntry] = {}

    def register(
        self,
        verifier_id: str,
        verifier: Any,
    ) -> Any:
        validation = VerifierValidation(
            verifier_id=verifier_id,
            min_coverage=self.min_coverage,
        )
        self._entries[verifier_id] = _VerifierEntry(verifier, validation)
        return verifier

    def get(self, verifier_id: str) -> Any | None:
        entry = self._entries.get(verifier_id)
        return None if entry is None else entry.verifier

    def validation(
        self,
        verifier_id: str,
    ) -> VerifierValidation | None:
        entry = self._entries.get(verifier_id)
        return None if entry is None else entry.validation

    def record_probe(
        self,
        verifier_id: str,
        *,
        passed: bool,
        meaningful: bool = True,
    ) -> VerifierValidation:
        entry = self._entries.get(verifier_id)
        if entry is None:
            raise KeyError(f"unknown verifier: {verifier_id}")

        validation = entry.validation.record(
            passed=passed,
            meaningful=meaningful,
        )
        self._entries[verifier_id] = _VerifierEntry(
            entry.verifier,
            validation,
        )
        return validation

    def is_validated(self, verifier_id: str) -> bool:
        validation = self.validation(verifier_id)
        return (
            validation is not None
            and validation.status == VerifierValidationStatus.VALIDATED
        )

    def is_failed(self, verifier_id: str) -> bool:
        validation = self.validation(verifier_id)
        return (
            validation is not None
            and validation.status == VerifierValidationStatus.FAILED
        )

    def items(self) -> list[tuple[str, Any, VerifierValidation]]:
        return [
            (verifier_id, entry.verifier, entry.validation)
            for verifier_id, entry in self._entries.items()
        ]
