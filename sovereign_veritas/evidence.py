from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_json(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


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

    def digest(self) -> str:
        return sha256_json(self.to_dict())


class Ledger:
    """Simple append-only evidence ledger for local runtime use."""

    def __init__(self) -> None:
        self._records: list[EvidenceRecord] = []

    def append(self, record: EvidenceRecord) -> EvidenceRecord:
        self._records.append(record)
        return record

    def extend(self, records: list[EvidenceRecord]) -> list[EvidenceRecord]:
        self._records.extend(records)
        return records

    def all(self) -> list[EvidenceRecord]:
        return list(self._records)

    def as_dicts(self) -> list[dict[str, Any]]:
        return [record.to_dict() for record in self._records]
