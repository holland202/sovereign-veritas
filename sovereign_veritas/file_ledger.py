from __future__ import annotations

import json
import os
from pathlib import Path
from dataclasses import replace

from .evidence import EvidenceRecord, Ledger, canonical_json


class FileLedger(Ledger):
    """Append-only JSONL ledger with fail-closed verification on load.

    Support boundary
    ----------------
    *Single-writer* use (one process owns the path) is the tested and
    supported mode.

    *Concurrent multi-writer* use is **UNSUPPORTED**. A Stage-1 Termux
    measurement (4 processes × 50 records) produced a broken hash chain;
    reload failed closed. See docs/CONCURRENCY_MEASUREMENT.md.

    Integrity checks detect corruption; they do not serialize writers.
    Do not treat a green unit suite as a concurrency-safety claim.
    """

    def __init__(self, path: str | Path) -> None:
        super().__init__()
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

        if self._path.exists():
            self._load()

    def _load(self) -> None:
        """Rebuild the chain from disk and verify every persisted record."""
        previous: str | None = None
        seen: set[str] = set()

        with self._path.open("r", encoding="utf-8") as handle:
            for index, line in enumerate(handle):
                line = line.strip()
                if not line:
                    continue

                try:
                    entry = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        f"invalid JSON at ledger index {index}"
                    ) from exc

                try:
                    record = EvidenceRecord(**entry["record"])
                    stored_digest = entry["record_digest"]
                except (KeyError, TypeError) as exc:
                    raise ValueError(
                        f"invalid ledger entry at index {index}"
                    ) from exc

                recomputed = record.record_digest

                if recomputed != stored_digest:
                    raise ValueError(
                        f"ledger content tampered at index {index}"
                    )

                if record.previous_digest != previous:
                    raise ValueError(
                        f"ledger chain broken at index {index}"
                    )

                if record.record_id in seen:
                    raise ValueError(
                        f"duplicate record_id across reload: {record.record_id}"
                    )

                seen.add(record.record_id)
                self._records.append(record)
                self._digests.append(recomputed)
                previous = recomputed

        self.verify()

    def append(self, record: EvidenceRecord) -> EvidenceRecord:
        """Durably append one record before advancing in-memory state.

        Supported under single-writer use only. Concurrent callers of
        append on the same path are unsupported (see class docstring).
        """
        if not record.record_id or not record.input_digest:
            raise ValueError("record_id and input_digest are required")

        self.verify()

        if any(
            existing.record_id == record.record_id
            for existing in self._records
        ):
            raise ValueError(f"duplicate record_id: {record.record_id}")

        chained = replace(
            record,
            previous_digest=self._digests[-1] if self._digests else None,
        )

        payload = canonical_json(
            {
                "record": chained.to_dict(),
                "record_digest": chained.record_digest,
            }
        ) + "\n"

        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())

        self._records.append(chained)
        self._digests.append(chained.record_digest)

        return chained
