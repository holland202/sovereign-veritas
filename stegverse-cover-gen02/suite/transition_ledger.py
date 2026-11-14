"""Transition ledger for the Sovereign Veritas covering (StegVerse Build Lane).

GEN 02 — the locking correction. GEN 01 imported msvcrt on Windows but never
called it: on that platform no lock was taken, while this docstring claimed
one "for every caller". GEN 02 implements the lock on both platforms through
a single helper (_lock_exclusive) and states the claim the code now makes
true. Found by the subject's author on static read of GEN 01; the GEN 01
suite is preserved unmodified as the baseline this generation cures.

A hash-chained, append-only ledger of TRANSITIONS, written around the unmodified
Sovereign Veritas workflow:

    INTENT      written durably BEFORE any external effect; one per record_id, ever.
                A second INTENT for the same record_id is refused before execution,
                atomically, under an OS file lock — fcntl.flock on POSIX,
                msvcrt.locking on Windows — for every caller, with no
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


def _lock_exclusive(fh) -> None:
    """Take the ledger's exclusive OS file lock, on this platform.

    POSIX: fcntl.flock on the ledger file. Windows: msvcrt.locking over
    byte 0 of the ledger file — every process appending to the same ledger
    contends on the same byte, so the guarantee is the same one POSIX gets
    from the flock. msvcrt.locking retries for roughly ten seconds and then
    raises OSError: a caller that cannot acquire the lock fails visibly
    instead of writing unlocked.
    """
    if fcntl is not None:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
    else:
        fh.seek(0)
        msvcrt.locking(fh.fileno(), msvcrt.LK_LOCK, 1)


def _unlock(fh) -> None:
    if fcntl is not None:
        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    else:
        fh.seek(0)
        msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)


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

    def _append_locked(self, entry: dict[str, Any], precheck=None) -> dict[str, Any]:
        """Append under the exclusive OS lock, re-reading the tail first so two
        processes (or threads) cannot fork the chain or both claim a record_id.
        `precheck`, when given, runs inside the critical section against the
        freshly read on-disk entries and may raise to refuse the append before
        anything is written."""
        with open(self.path, "a+", encoding="utf-8") as fh:
            _lock_exclusive(fh)
            try:
                fh.seek(0)
                lines = [ln for ln in fh.read().splitlines() if ln.strip()]
                entries = [json.loads(ln) for ln in lines]
                if precheck is not None:
                    precheck(entries)
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
                _unlock(fh)

    # -- transitions -----------------------------------------------------------
    def begin(self, record_id: str, action_digest: str) -> dict[str, Any]:
        """Write the INTENT before any effect. Refuses a record_id that already
        has an INTENT in any state — atomically, under the append lock, on
        every supported platform (see _lock_exclusive)."""
        # Fast path check, then the authoritative check inside the lock.
        if any(e["kind"] == "INTENT" and e["record_id"] == record_id for e in self._entries):
            raise ValueError(f"duplicate record_id refused before execution: {record_id}")

        def _no_duplicate(entries: list[dict[str, Any]]) -> None:
            # The authoritative check: it must hold against the on-disk tail,
            # not only memory, so it runs inside the lock's critical section.
            if any(e["kind"] == "INTENT" and e["record_id"] == record_id for e in entries):
                raise ValueError(f"duplicate record_id refused before execution: {record_id}")

        return self._append_locked(
            {"kind": "INTENT", "record_id": record_id, "action_digest": action_digest},
            precheck=_no_duplicate,
        )

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
