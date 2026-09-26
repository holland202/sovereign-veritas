from __future__ import annotations

import math

import hashlib
import json
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


def _validate_jsonable(value: Any, path: str = "value") -> None:
    try:
        json.dumps(_thaw(value), sort_keys=True, ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"non-JSON-serializable value at {path}") from exc


def _as_quality(value: Any) -> float | None:
    """A JSON number as a float; None for anything else. Too large for a float: signed infinity."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        return float(value)
    except OverflowError:
        return math.inf if value > 0 else -math.inf


@dataclass(frozen=True)
class EvidenceRecord:
    """Immutable observation of one prediction, verification, and gate decision.

    uncertainty and evidence_quality are optional structured fields that let the
    Gate make graded decisions without changing the core hash-chain contract.
    evidence_quality is expected in [0.0, 1.0] when present.
    """

    record_id: str
    input_digest: str
    prediction: dict[str, Any] | None = None
    verification: dict[str, Any] | None = None
    capability: str | None = None
    action: dict[str, Any] | None = None
    decision: str | None = None
    reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    uncertainty: dict[str, Any] | None = None
    evidence_quality: float | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    previous_digest: str | None = None

    def __post_init__(self) -> None:
        prediction = _freeze(self.prediction)
        verification = _freeze(self.verification)
        action = _freeze(self.action)
        metadata = _freeze(self.metadata)
        uncertainty = _freeze(self.uncertainty)

        _validate_jsonable(prediction, "prediction")
        _validate_jsonable(verification, "verification")
        _validate_jsonable(action, "action")
        _validate_jsonable(metadata, "metadata")
        _validate_jsonable(uncertainty, "uncertainty")

        object.__setattr__(self, "prediction", prediction)
        object.__setattr__(self, "verification", verification)
        object.__setattr__(self, "action", action)
        object.__setattr__(self, "metadata", metadata)
        object.__setattr__(self, "uncertainty", uncertainty)

    def with_updates(self, **changes: Any) -> "EvidenceRecord":
        allowed = {
            "record_id",
            "input_digest",
            "prediction",
            "verification",
            "capability",
            "action",
            "decision",
            "reasons",
            "metadata",
            "uncertainty",
            "evidence_quality",
            "timestamp",
            "previous_digest",
        }

        unknown = set(changes) - allowed
        if unknown:
            raise TypeError(
                f"unknown EvidenceRecord fields: {sorted(unknown)}"
            )

        values = {
            field_name: getattr(self, field_name)
            for field_name in allowed
        }
        values.update(changes)
        return replace(self, **values)

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
            "uncertainty": _thaw(self.uncertainty),
            "evidence_quality": self.evidence_quality,
            "previous_digest": self.previous_digest,
        }

    @property
    def record_digest(self) -> str:
        return _digest(self.to_dict())

    def quality_or_default(self, default: float = 0.0) -> float:
        """The record's evidence_quality if present, else metadata's, else default.

        Only a number counts, never a boolean or a string: True is not 1.0 and "0.9" is not 0.9
        (docs/GATE_CONTRACT.md, Q1). A present top-level value that is not a number counts as not
        supplied; it does not fall through to metadata. NaN, infinities and values outside [0, 1]
        are returned as they are, for the Gate to report as invalid.
        """
        if self.evidence_quality is not None:
            q = _as_quality(self.evidence_quality)
            return default if q is None else q
        meta_q = _as_quality(self.metadata.get("evidence_quality")) if self.metadata else None
        return default if meta_q is None else meta_q


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
