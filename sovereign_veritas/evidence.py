from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Mapping


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType(
            {key: _freeze(item) for key, item in value.items()}
        )
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, set):
        return frozenset(_freeze(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze(item) for item in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    if isinstance(value, frozenset):
        return {_thaw(item) for item in value}
    return value


def canonical_json(value: Any) -> str:
    """Return deterministic JSON suitable for hashing and evidence export."""
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


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

    def __post_init__(self) -> None:
        object.__setattr__(self, "prediction", _freeze(self.prediction))
        object.__setattr__(self, "verification", _freeze(self.verification))
        object.__setattr__(self, "action", _freeze(self.action))
        object.__setattr__(self, "metadata", _freeze(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "timestamp": self.timestamp,
            "input_digest": self.input_digest,
            "prediction": _thaw(self.prediction),
            "verification": _thaw(self.verification),
            "capability": self.capability,
            "action": _thaw(self.action),
            "decision": self.decision,
            "reasons": list(self.reasons),
            "metadata": _thaw(self.metadata),
            "previous_digest": self.previous_digest,
        }

    @property
    def record_digest(self) -> str:
        return _digest(self.to_dict())


@dataclass(frozen=True)
class EvidencePackage:
    """Independently inspectable evidence bundle around one EvidenceRecord."""

    schema_version: str
    record: EvidenceRecord
    provenance: dict[str, Any] = field(default_factory=dict)
    known_limitations: tuple[str, ...] = ()
    artifact_digests: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "provenance", _freeze(self.provenance))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "record": self.record.to_dict(),
            "record_digest": self.record.record_digest,
            "provenance": _thaw(self.provenance),
            "known_limitations": list(self.known_limitations),
            "artifact_digests": list(self.artifact_digests),
        }

    def serialize(self) -> str:
        return canonical_json(self.to_dict())

    @property
    def package_digest(self) -> str:
        return _digest(self.to_dict())

    @property
    def verification_status(self) -> str:
        verification = self.record.verification
        if verification is None:
            return "NOT_VERIFIED"

        status = verification.get("status")
        if status is None:
            return "UNKNOWN"

        return str(status)


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


class LedgerSink:
    """EvidenceSink that makes the hash chain the default custody path.

    Structurally satisfies interfaces.contracts.EvidenceSink.
    Duplicate record_ids and broken chains propagate loudly by design:
    evidence integrity failures must never be silently absorbed.
    """

    def __init__(self, ledger: Ledger) -> None:
        self.ledger = ledger

    def record(self, record: EvidenceRecord) -> EvidenceRecord:
        return self.ledger.append(record)
