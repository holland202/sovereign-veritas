"""Transition ledger for the Sovereign Veritas covering (StegVerse Build Lane).

A hash-chained, append-only ledger of TRANSITIONS, written around the unmodified
Sovereign Veritas workflow:

    INTENT      written durably BEFORE any external effect; one per record_id, ever.
                A second INTENT for the same record_id is refused before execution,
                atomically, under an OS file lock - for every caller, with no
                idempotency key and no sink cooperation required.
    COMPLETION  written after the effect, carrying the effected side's attestation:
                the before/after observation of the target's state and the EO-2
                verdict recomputed from it.
    UNKNOWN     written when the executor raised: the effect may or may not have
                happened. The transition stays open and the record_id stays refused.

An INTENT with no COMPLETION and no UNKNOWN is an OPEN transition: a first-class,
enumerable state, never silence. This is the StegVerse form of the execution
boundary: the record of an action is not written after the action as its account;
the intent is the action's admission, and the completion is its matched pair.

Format: one canonical-JSON entry per line; each entry carries the previous entry's
hash (prev) and its own hash over the entry without the hash field. Reload verifies
the chain and refuses a broken one.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from sovereign_veritas.evidence import canonical_json

try:
    import fcntl
except ImportError:  # Windows
    fcntl = None  # type: ignore[assignment]
    import msvcrt


def _entry_hash(entry: dict[str, Any]) -> str:
    body = {k: v for k, v in entry.items() if k != "hash"}
    return "sha256:" + hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()


class TransitionLedger:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._entries: list[dict[str, Any]] = []
        if self.path.exists():
            self._load_verified()

    # -- chain ---------------------------------------------------------------
    def _load_verified(self) -> None:
        entries: list[dict[str, Any]] = []
        prev = "GENESIS"
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            entry = json.loads(line)
            if entry.get("prev") != prev:
                raise ValueError(f"transition ledger chain broken at seq {entry.get('seq')}")
            if _entry_hash(entry) != entry.get("hash"):
                raise ValueError(f"transition ledger entry hash mismatch at seq {entry.get('seq')}")
            prev = entry["hash"]
            entries.append(entry)
        self._entries = entries

    def _append_locked(self, entry: dict[str, Any]) -> dict[str, Any]:
        """Append under an exclusive OS lock, re-reading the tail first so two
        processes (or threads) cannot fork the chain or both claim a record_id."""
        with open(self.path, "a+", encoding="utf-8") as fh:
            if fcntl is not None:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            try:
                fh.seek(0)
                lines = [ln for ln in fh.read().splitlines() if ln.strip()]
                entries = [json.loads(ln) for ln in lines]
                prev = entries[-1]["hash"] if entries else "GENESIS"
                entry = {"seq": len(entries), **entry, "prev": prev}
                entry["hash"] = _entry_hash(entry)
                fh.seek(0, os.SEEK_END)
                fh.write(canonical_json(entry) + "\n")
                fh.flush()
                os.fsync(fh.fileno())
                self._entries = entries + [entry]
                return entry
            finally:
                if fcntl is not None:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_UN)

    # -- transitions -----------------------------------------------------------
    def begin(self, record_id: str, action_digest: str) -> str:
        """Write the INTENT before any effect. Refuses a record_id that already
        has an INTENT in any state - atomically, under the append lock."""
        # Fast path check, then the authoritative check inside the lock.
        if any(e["kind"] == "INTENT" and e["record_id"] == record_id for e in self._entries):
            raise ValueError(f"duplicate record_id refused before execution: {record_id}")

        def _guarded() -> dict[str, Any]:
            return {"kind": "INTENT", "record_id": record_id, "action_digest": action_digest}

        # The check must hold against the on-disk tail, not only memory: do it
        # inside _append_locked's critical section by re-reading there.
        with open(self.path, "a+", encoding="utf-8") as fh:
            if fcntl is not None:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            try:
                fh.seek(0)
                entries = [json.loads(ln) for ln in fh.read().splitlines() if ln.strip()]
                if any(e["kind"] == "INTENT" and e["record_id"] == record_id for e in entries):
                    raise ValueError(f"duplicate record_id refused before execution: {record_id}")
                prev = entries[-1]["hash"] if entries else "GENESIS"
                entry = {"seq": len(entries), **_guarded(), "prev": prev}
                entry["hash"] = _entry_hash(entry)
                fh.seek(0, os.SEEK_END)
                fh.write(canonical_json(entry) + "\n")
                fh.flush()
                os.fsync(fh.fileno())
                self._entries = entries + [entry]
                return entry
            finally:
                if fcntl is not None:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_UN)

    def complete(self, record_id: str, observation: dict[str, Any],
                 expected: dict[str, Any] | None, effect_verdict: str) -> dict[str, Any]:
        intent = self._intent(record_id)
        if intent is None:
            raise ValueError(f"completion without intent: {record_id}")
        return self._append_locked({
            "kind": "COMPLETION", "record_id": record_id,
            "intent_hash": intent["hash"], "observation": observation,
            "expected": expected, "effect_verdict": effect_verdict,
        })

    def mark_unknown(self, record_id: str, why: str) -> dict[str, Any]:
        intent = self._intent(record_id)
        if intent is None:
            raise ValueError(f"unknown without intent: {record_id}")
        return self._append_locked({
            "kind": "UNKNOWN", "record_id": record_id,
            "intent_hash": intent["hash"], "why": why,
        })

    # -- reads -----------------------------------------------------------------
    def _intent(self, record_id: str) -> dict[str, Any] | None:
        for e in self._entries:
            if e["kind"] == "INTENT" and e["record_id"] == record_id:
                return e
        return None

    def entries(self) -> list[dict[str, Any]]:
        return list(self._entries)

    def open_transitions(self) -> list[str]:
        done = {e["record_id"] for e in self._entries if e["kind"] in ("COMPLETION", "UNKNOWN")}
        return [e["record_id"] for e in self._entries
                if e["kind"] == "INTENT" and e["record_id"] not in done]
