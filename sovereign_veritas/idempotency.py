"""Reserved idempotency keys (RK-2, docs/RK2_PREREG.md).

A key is reserved before an external effect and is never reused without an explicit release:

    reserve(key)   -> IN_FLIGHT (with a lease expiry), or ReservationRefused if the key exists at all
    complete(key)  -> COMPLETED   (the effect happened and its response came back)
    unknown(key)   -> UNKNOWN     (the executor raised: the effect may or may not have happened)
    release(key)   -> the key may run again; allowed only from UNKNOWN, meant for a human after investigating

An IN_FLIGHT key whose lease has expired becomes UNKNOWN and is still refused: an expired lease is never treated
as permission to run again (fail closed). The price is liveness: UNKNOWN keys wait for a person.

RK-3 (docs/RK3_PREREG.md): reserve() never writes to an existing key (expiry is derived, not stored), so it cannot
overwrite a late complete(). reserve() returns a holder token; complete()/unknown() given a token that no longer
matches the entry (the key was released, and maybe reserved again) leave the entry alone and append a late event
instead (late_events()). This makes a late holder visible; it cannot stop the late holder's effect. That needs a
fence checked by the action's target (OBS-1).

The caller must choose the key when the intent is created, before the first attempt. A fresh key per attempt
defeats this (RK-2 case A3).
"""
from __future__ import annotations

import hashlib
import json
import secrets
import os
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

try:  # SEC-005: an exclusive OS lock per key file
    import fcntl
except ImportError:  # Windows
    fcntl = None  # type: ignore[assignment]
    import msvcrt

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


def _late_event(to: str, why: str | None, token: str, entry: dict[str, Any] | None) -> dict[str, Any]:
    """RK-3: a complete()/unknown() from a holder that no longer holds the key."""
    return {"at": time.time(), "event": "late_complete" if to == COMPLETED else "late_unknown",
            "late_token": token, "current_token": None if entry is None else entry.get("token"),
            **({"why": why} if why else {})}


def _with_expiry(entry: dict[str, Any]) -> list[dict[str, Any]]:
    """History as released: expiry is derived (RK-3), so write it down at release time."""
    hist = list(entry.get("history", []))
    if entry.get("state") == IN_FLIGHT:
        hist.append({"at": float(entry.get("lease_expires", 0)), "to": UNKNOWN, "why": "lease_expired"})
    return hist


class MemoryReservations:
    """In-process store; reserve() is atomic under one lock."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._entries: dict[str, dict[str, Any]] = {}
        self._released: dict[str, list[list[dict[str, Any]]]] = {}
        self._late: dict[str, list[dict[str, Any]]] = {}

    def reserve(self, key: str, lease_s: float = DEFAULT_LEASE_S) -> str:
        now = time.time()
        with self._lock:
            entry = self._entries.get(key)
            if entry is not None:
                raise _refusal(key, _effective(entry, now))  # RK-3: never written here
            token = secrets.token_hex(8)
            self._entries[key] = {"state": IN_FLIGHT, "lease_expires": now + lease_s, "token": token,
                                  "history": [{"at": now, "to": IN_FLIGHT}]}
            return token

    def _move(self, key: str, to: str, why: str | None = None, token: str | None = None) -> None:
        with self._lock:
            entry = self._entries.get(key)
            if token is not None and (entry is None or entry.get("token") != token):
                self._late.setdefault(key, []).append(_late_event(to, why, token, entry))
                return
            entry["state"] = to
            entry["history"] = entry["history"] + [{"at": time.time(), "to": to, **({"why": why} if why else {})}]

    def complete(self, key: str, token: str | None = None) -> None:
        self._move(key, COMPLETED, token=token)

    def unknown(self, key: str, why: str, token: str | None = None) -> None:
        self._move(key, UNKNOWN, why, token=token)

    def late_events(self, key: str) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._late.get(key, []))

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
            released = _with_expiry(entry) + [{"at": time.time(), "to": "RELEASED", "by": by, "why": reason}]
            self._released.setdefault(key, []).append(released)
            del self._entries[key]

    def released_history(self, key: str) -> list[list[dict[str, Any]]]:
        with self._lock:
            return list(self._released.get(key, []))


def _lock_fd(fd: int) -> None:
    if fcntl is not None:
        fcntl.flock(fd, fcntl.LOCK_EX)
        return
    os.lseek(fd, 0, os.SEEK_SET)
    while True:  # msvcrt.LK_LOCK gives up after about 10 s; keep waiting, as flock does
        try:
            msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
            return
        except OSError:
            continue


def _unlock_fd(fd: int) -> None:
    if fcntl is not None:
        fcntl.flock(fd, fcntl.LOCK_UN)
        return
    os.lseek(fd, 0, os.SEEK_SET)
    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)


class FileReservations:
    """One file per key hash in a directory. The claim is os.open(O_CREAT|O_EXCL), atomic across threads and
    processes on one local filesystem. A file that exists but cannot be read counts as IN_FLIGHT (fail closed).

    SEC-005 (docs/SEC005_PREREG.md): reserve(), _move() and release() each hold an exclusive OS lock on the key's
    lock file for their whole read-check-write(-rename), so a holder that passed its token check cannot write
    after a release and a fresh reserve (SEC-004). The lock file is never deleted. Local filesystems only."""

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

    @contextmanager
    def _key_lock(self, key: str) -> Iterator[None]:
        fd = os.open(self._path(key).with_suffix(".lock"), os.O_CREAT | os.O_RDWR, 0o600)
        try:
            _lock_fd(fd)
            try:
                yield
            finally:
                _unlock_fd(fd)
        finally:
            os.close(fd)

    def _write(self, key: str, entry: dict[str, Any]) -> None:
        path = self._path(key)
        tmp = path.with_suffix(f".tmp-{os.getpid()}-{threading.get_ident()}")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(entry, fh, sort_keys=True)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)

    def reserve(self, key: str, lease_s: float = DEFAULT_LEASE_S) -> str:
        now = time.time()
        token = secrets.token_hex(8)
        entry = {"key": key, "state": IN_FLIGHT, "lease_expires": now + lease_s, "token": token,
                 "history": [{"at": now, "to": IN_FLIGHT}]}
        with self._key_lock(key):
            try:
                fd = os.open(self._path(key), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError:  # RK-3: never written here
                raise _refusal(key, _effective(self._read(key), now)) from None
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(entry, fh, sort_keys=True)
                fh.flush()
                os.fsync(fh.fileno())
        return token

    def _late_path(self, key: str) -> Path:
        return self._path(key).with_suffix(".late.jsonl")  # no new hash site (JG-2 P1)

    def _move(self, key: str, to: str, why: str | None = None, token: str | None = None) -> None:
        with self._key_lock(key):  # SEC-005: token check and write in one critical section
            self._move_locked(key, to, why, token)

    def _move_locked(self, key: str, to: str, why: str | None, token: str | None) -> None:
        if token is not None:
            exists = self._path(key).exists()
            entry = self._read(key) if exists else None
            if entry is None or entry.get("token") != token:
                with open(self._late_path(key), "a", encoding="utf-8") as fh:  # append-only; never rewritten
                    fh.write(json.dumps(_late_event(to, why, token, entry), sort_keys=True) + "\n")
                    fh.flush()
                    os.fsync(fh.fileno())
                return
        entry = self._read(key)
        entry["state"] = to
        entry["history"] = entry.get("history", []) + [{"at": time.time(), "to": to, **({"why": why} if why else {})}]
        self._write(key, entry)

    def complete(self, key: str, token: str | None = None) -> None:
        self._move(key, COMPLETED, token=token)

    def unknown(self, key: str, why: str, token: str | None = None) -> None:
        self._move(key, UNKNOWN, why, token=token)

    def late_events(self, key: str) -> list[dict[str, Any]]:
        p = self._late_path(key)
        if not p.exists():
            return []
        with open(p, encoding="utf-8") as fh:
            return [json.loads(line) for line in fh if line.strip()]

    def state(self, key: str) -> str | None:
        if not self._path(key).exists():
            return None
        return _effective(self._read(key), time.time())

    def history(self, key: str) -> list[dict[str, Any]]:
        return list(self._read(key).get("history", [])) if self._path(key).exists() else []

    def release(self, key: str, by: str, reason: str) -> None:
        with self._key_lock(key):  # SEC-005: check, write and rename in one critical section
            if self.state(key) != UNKNOWN:
                raise ValueError(f"release is allowed only from UNKNOWN: {key!r}")
            entry = self._read(key)
            entry["history"] = _with_expiry(entry) + [{"at": time.time(), "to": "RELEASED", "by": by, "why": reason}]
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
