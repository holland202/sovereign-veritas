"""Reserved idempotency keys (RK-2, docs/RK2_PREREG.md).

A key is reserved before an external effect and is never reused without an explicit release:

    reserve(key)   -> IN_FLIGHT (with a lease expiry), or ReservationRefused if the key exists at all
    complete(key)  -> COMPLETED   (the effect happened and its response came back)
    unknown(key)   -> UNKNOWN     (the executor raised: the effect may or may not have happened)
    release(key)   -> the key may run again; allowed only from UNKNOWN, meant for a human after investigating

An IN_FLIGHT key whose lease has expired becomes UNKNOWN and is still refused: an expired lease is never treated
as permission to run again (fail closed). The price is liveness: UNKNOWN keys wait for a person.

The caller must choose the key when the intent is created, before the first attempt. A fresh key per attempt
defeats this (RK-2 case A3).
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from pathlib import Path
from typing import Any

IN_FLIGHT, COMPLETED, UNKNOWN = "IN_FLIGHT", "COMPLETED", "UNKNOWN"
DEFAULT_LEASE_S = 30.0


class ReservationRefused(ValueError):
    """The key already exists in some state; nothing may run under it."""


def _effective(entry: dict[str, Any], now: float) -> str:
    if entry.get("state") == IN_FLIGHT and now >= float(entry.get("lease_expires", 0)):
        return UNKNOWN
    return entry.get("state", IN_FLIGHT)


def _refusal(key: str, state: str) -> ReservationRefused:
    return ReservationRefused(f"idempotency key {key!r} is {state}: refused before execution")


class MemoryReservations:
    """In-process store; reserve() is atomic under one lock."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._entries: dict[str, dict[str, Any]] = {}
        self._released: dict[str, list[list[dict[str, Any]]]] = {}

    def reserve(self, key: str, lease_s: float = DEFAULT_LEASE_S) -> None:
        now = time.time()
        with self._lock:
            entry = self._entries.get(key)
            if entry is not None:
                state = _effective(entry, now)
                if state != entry["state"]:
                    entry.update(state=state, history=entry["history"] + [{"at": now, "to": state, "why": "lease_expired"}])
                raise _refusal(key, state)
            self._entries[key] = {"state": IN_FLIGHT, "lease_expires": now + lease_s,
                                  "history": [{"at": now, "to": IN_FLIGHT}]}

    def _move(self, key: str, to: str, why: str | None = None) -> None:
        with self._lock:
            entry = self._entries[key]
            entry["state"] = to
            entry["history"] = entry["history"] + [{"at": time.time(), "to": to, **({"why": why} if why else {})}]

    def complete(self, key: str) -> None:
        self._move(key, COMPLETED)

    def unknown(self, key: str, why: str) -> None:
        self._move(key, UNKNOWN, why)

    def state(self, key: str) -> str | None:
        with self._lock:
            entry = self._entries.get(key)
            return None if entry is None else _effective(entry, time.time())

    def history(self, key: str) -> list[dict[str, Any]]:
        with self._lock:
            return list((self._entries.get(key) or {}).get("history", []))

    def release(self, key: str, by: str, reason: str) -> None:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None or _effective(entry, time.time()) != UNKNOWN:
                raise ValueError(f"release is allowed only from UNKNOWN: {key!r}")
            released = entry["history"] + [{"at": time.time(), "to": "RELEASED", "by": by, "why": reason}]
            self._released.setdefault(key, []).append(released)
            del self._entries[key]

    def released_history(self, key: str) -> list[list[dict[str, Any]]]:
        with self._lock:
            return list(self._released.get(key, []))


class FileReservations:
    """One file per key hash in a directory. The claim is os.open(O_CREAT|O_EXCL), atomic across threads and
    processes on one local filesystem. A file that exists but cannot be read counts as IN_FLIGHT (fail closed)."""

    def __init__(self, directory: str | os.PathLike[str]) -> None:
        self._dir = Path(directory)
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self._dir / (hashlib.sha256(key.encode("utf-8")).hexdigest() + ".json")

    def _read(self, key: str) -> dict[str, Any]:
        try:
            with open(self._path(key), encoding="utf-8") as fh:
                entry = json.load(fh)
            return entry if isinstance(entry, dict) and "state" in entry else {"state": IN_FLIGHT, "lease_expires": float("inf")}
        except (OSError, ValueError):
            return {"state": IN_FLIGHT, "lease_expires": float("inf")}

    def _write(self, key: str, entry: dict[str, Any]) -> None:
        path = self._path(key)
        tmp = path.with_suffix(f".tmp-{os.getpid()}-{threading.get_ident()}")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(entry, fh, sort_keys=True)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)

    def reserve(self, key: str, lease_s: float = DEFAULT_LEASE_S) -> None:
        now = time.time()
        entry = {"key": key, "state": IN_FLIGHT, "lease_expires": now + lease_s, "history": [{"at": now, "to": IN_FLIGHT}]}
        try:
            fd = os.open(self._path(key), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            current = self._read(key)
            state = _effective(current, now)
            if state != current.get("state") and "history" in current:
                current.update(state=state, history=current["history"] + [{"at": now, "to": state, "why": "lease_expired"}])
                self._write(key, current)
            raise _refusal(key, state) from None
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(entry, fh, sort_keys=True)
            fh.flush()
            os.fsync(fh.fileno())

    def _move(self, key: str, to: str, why: str | None = None) -> None:
        entry = self._read(key)
        entry["state"] = to
        entry["history"] = entry.get("history", []) + [{"at": time.time(), "to": to, **({"why": why} if why else {})}]
        self._write(key, entry)

    def complete(self, key: str) -> None:
        self._move(key, COMPLETED)

    def unknown(self, key: str, why: str) -> None:
        self._move(key, UNKNOWN, why)

    def state(self, key: str) -> str | None:
        if not self._path(key).exists():
            return None
        return _effective(self._read(key), time.time())

    def history(self, key: str) -> list[dict[str, Any]]:
        return list(self._read(key).get("history", [])) if self._path(key).exists() else []

    def release(self, key: str, by: str, reason: str) -> None:
        if self.state(key) != UNKNOWN:
            raise ValueError(f"release is allowed only from UNKNOWN: {key!r}")
        entry = self._read(key)
        entry["history"] = entry.get("history", []) + [{"at": time.time(), "to": "RELEASED", "by": by, "why": reason}]
        self._write(key, entry)
        path = self._path(key)
        os.replace(path, path.with_suffix(f".released-{time.time_ns()}.json"))

    def released_history(self, key: str) -> list[list[dict[str, Any]]]:
        stem = self._path(key).stem
        out = []
        for p in sorted(self._dir.glob(stem + ".released-*.json")):
            with open(p, encoding="utf-8") as fh:
                out.append(json.load(fh).get("history", []))
        return out
