from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any


def _digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class EvidenceRecord:
    """Immutable observation of one prediction, verification, and gate decision."""

    record_id: str
    input_digest: str
    prediction: dict[str, Any] | None = None
    verification: dict[str, Any] | None = None
    capability: str | None = None
    action: dict[str, Any] | None = None
    decision: str | None = None
    reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    previous_digest: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "timestamp": self.timestamp,
            "input_digest": self.input_digest,
            "prediction": deepcopy(self.prediction),
            "verification": deepcopy(self.verification),
            "capability": self.capability,
            "action": deepcopy(self.action),
            "decision": self.decision,
            "reasons": list(self.reasons),
            "metadata": deepcopy(self.metadata),
            "previous_digest": self.previous_digest,
        }

    @property
    def record_digest(self) -> str:
        return _digest(self.to_dict())


class Ledger:
    """In-memory append-only hash chain with tamper detection."""

    def __init__(self) -> None:
        self._records: list[EvidenceRecord] = []
        self._digests: list[str] = []

    def append(self, record: EvidenceRecord) -> EvidenceRecord:
        if not record.record_id or not record.input_digest:
            raise ValueError("record_id and input_digest are required")
        self.verify()
        if any(existing.record_id == record.record_id for existing in self._records):
            raise ValueError(f"duplicate record_id: {record.record_id}")
        chained = replace(record, previous_digest=self._digests[-1] if self._digests else None)
        self._records.append(chained)
        self._digests.append(chained.record_digest)
        return chained

    def all(self) -> list[EvidenceRecord]:
        return list(self._records)

    def verify(self) -> bool:
        previous: str | None = None
        for index, record in enumerate(self._records):
            if record.previous_digest != previous:
                raise ValueError(f"ledger chain broken at index {index}")
            digest = record.record_digest
            if digest != self._digests[index]:
                raise ValueError(f"ledger record tampered at index {index}")
            previous = digest
        return True

    def as_dicts(self) -> list[dict[str, Any]]:
        self.verify()
        return [record.to_dict() | {"record_digest": record.record_digest} for record in self._records]
