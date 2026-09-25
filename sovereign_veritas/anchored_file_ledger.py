from __future__ import annotations

import json
import os
from pathlib import Path
from time import time

from .evidence import EvidenceRecord
from .file_ledger import FileLedger

try:
    import fcntl
except ImportError:  # pragma: no cover - platform guard
    fcntl = None


class AnchoredFileLedger(FileLedger):
    """FileLedger with an external consistency anchor and process locking.

    The anchor records the accepted ledger prefix. On startup, the ledger must
    contain that prefix exactly; additional valid records are accepted as a
    post-anchor suffix, which permits recovery from a crash between ledger
    fsync and anchor update.

    This is not cryptographic authentication of the anchor. A host attacker
    able to rewrite both the ledger and anchor can defeat the mechanism.
    """

    ANCHOR_SCHEMA = 1

    def __init__(
        self,
        path: str | Path,
        *,
        anchor_path: str | Path | None = None,
        lock_path: str | Path | None = None,
    ) -> None:
        self._path = Path(path)
        self._anchor_path = (
            Path(anchor_path)
            if anchor_path is not None
            else self._path.with_name(self._path.name + ".anchor")
        )
        self._lock_path = (
            Path(lock_path)
            if lock_path is not None
            else self._path.with_name(self._path.name + ".lock")
        )

        self._anchor_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)

        self._load_anchor()
        super().__init__(self._path)
        self._verify_anchor_against_ledger()

    def _load_anchor(self) -> None:
        self._anchor: dict[str, object] | None = None

        if not self._anchor_path.exists():
            return

        try:
            anchor = json.loads(
                self._anchor_path.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("invalid ledger anchor") from exc

        if not isinstance(anchor, dict):
            raise ValueError("invalid ledger anchor")

        if anchor.get("schema") != self.ANCHOR_SCHEMA:
            raise ValueError("unsupported ledger anchor schema")

        required = {"count", "head_digest", "history", "updated_at"}
        if not required.issubset(anchor):
            raise ValueError("incomplete ledger anchor")

        self._anchor = anchor

    def _verify_anchor_against_ledger(self) -> None:
        if self._anchor is None:
            return

        count = self._anchor["count"]
        head_digest = self._anchor["head_digest"]
        history = self._anchor["history"]

        if not isinstance(count, int) or count < 0:
            raise ValueError("invalid ledger anchor count")

        if not isinstance(history, list):
            raise ValueError("invalid ledger anchor history")

        if count != len(history):
            raise ValueError("ledger anchor history/count mismatch")

        if count > len(self._records):
            raise ValueError("ledger truncated relative to anchor")

        actual_history = self._digests[:count]
        if actual_history != history:
            raise ValueError("ledger history mismatch against anchor")

        actual_head = actual_history[-1] if actual_history else None
        if head_digest != actual_head:
            raise ValueError("ledger head mismatch against anchor")

    def _write_anchor(self) -> None:
        history = list(self._digests)
        anchor = {
            "schema": self.ANCHOR_SCHEMA,
            "count": len(history),
            "head_digest": history[-1] if history else None,
            "history": history,
            "updated_at": time(),
        }

        temporary = self._anchor_path.with_name(
            self._anchor_path.name + ".tmp"
        )

        payload = json.dumps(
            anchor,
            sort_keys=True,
            separators=(",", ":"),
        )

        with temporary.open("w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())

        os.replace(temporary, self._anchor_path)

        try:
            directory_fd = os.open(
                self._anchor_path.parent,
                os.O_RDONLY,
            )
        except OSError:
            return

        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)

    def _locked(self):
        if fcntl is None:
            raise RuntimeError(
                "AnchoredFileLedger requires fcntl.flock on this platform"
            )

        handle = self._lock_path.open("a+", encoding="utf-8")
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        return handle

    def append(self, record: EvidenceRecord) -> EvidenceRecord:
        lock = self._locked()
        try:
            # Re-read the on-disk state while holding the lock. This prevents
            # two cooperating writers from advancing from stale in-memory
            # chain state.
            self._reload_locked()
            chained = super().append(record)
            self._write_anchor()
            return chained
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
            lock.close()

    def _reload_locked(self) -> None:
        if not self._path.exists():
            self._records = []
            self._digests = []
            self._verify_anchor_against_ledger()
            return

        self._records = []
        self._digests = []
        self._load()
        self._verify_anchor_against_ledger()
