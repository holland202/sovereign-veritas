from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class EvidenceRecord:
    record_id: str
    input_digest: str
    capability: str | None = None
    prediction: dict[str, Any] | None = None
    verification: dict[str, Any] | None = None
    action: dict[str, Any] | None = None
    decision: str | None = None
    reasons: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "timestamp": self.timestamp,
            "input_digest": self.input_digest,
            "capability": self.capability,
            "prediction": self.prediction,
            "verification": self.verification,
            "action": self.action,
            "decision": self.decision,
            "reasons": list(self.reasons),
            "metadata": dict(self.metadata),
        }


class Ledger:
    def __init__(self) -> None:
        self._records: list[EvidenceRecord] = []

    def append(self, record: EvidenceRecord) -> EvidenceRecord:
        self._records.append(record)
        return record

    def all(self) -> list[EvidenceRecord]:
        return list(self._records)
