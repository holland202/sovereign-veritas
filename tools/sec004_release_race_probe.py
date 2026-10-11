#!/usr/bin/env python3
"""SEC-004: preregistered, local-only reservation race probe.

Registration: docs/SEC004_PREREG.md, committed before this probe.
No production code is changed or monkeypatched on disk.
Process exit 0 means the instrument finished, NOT security PASS.
"""
from __future__ import annotations

import hashlib
import json
import platform
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sovereign_veritas.idempotency import (  # noqa: E402
    COMPLETED,
    IN_FLIGHT,
    FileReservations,
    MemoryReservations,
)

EXPECTED_BLOBS = {
    "sovereign_veritas/idempotency.py": "071fc3fe64672c6cdbe7a3fe6e6406554c03a574",
    "tests/test_idempotency.py": "aa977253933cd6b0155cd923f5e06c4eb6586d63",
    "docs/RK3_RESULTS.md": "acddf169a76cdd07a1d52c5628eb626a6dfa5308",
    "docs/OBS1_RESULTS.md": "8a294a7dc5332b8c4777f6e9bc8d85df6381c7a3",
}


class Inconclusive(Exception):
    pass


def blob_id(path: Path) -> str:
    body = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(body)).encode() + b"\0" + body).hexdigest()


def snapshot(store: FileReservations, key: str) -> dict[str, Any]:
    path = store._path(key)
    if not path.exists():
        return {"present": False, "state": store.state(key)}
    body = path.read_bytes()
    record = json.loads(body)
    return {
        "present": True,
        "state": store.state(key),
        "entry_state": record.get("state"),
        "token": record.get("token"),
        "sha256": hashlib.sha256(body).hexdigest(),
        "history": record.get("history", []),
    }


def c0_memory() -> dict[str, Any]:
    s = MemoryReservations()
    old = s.reserve("K-C0", lease_s=0)
    s.release("K-C0", by="synthetic-operator", reason="test expired lease")
    new = s.reserve("K-C0", lease_s=60)
    s.complete("K-C0", token=old)
    events = s.late_events("K-C0")
    held = s.state("K-C0")
    s.complete("K-C0", token=new)
    passed = (
        old != new
        and held == IN_FLIGHT
        and s.state("K-C0") == COMPLETED
        and len(events) == 1
        and events[0].get("event") == "late_complete"
        and events[0].get("late_token") == old
        and events[0].get("current_token") == new
    )
    return {
        "pass": passed, "old_token": old, "new_token": new,
        "state_after_old_complete": held,
        "state_after_new_complete": s.state("K-C0"),
        "late_events": events,
    }


def c1_file(directory: Path) -> dict[str, Any]:
    s = FileReservations(directory / "c1")
    old = s.reserve("K-C1", lease_s=0)
    s.release("K-C1", by="synthetic-operator", reason="test expired lease")
    new = s.reserve("K-C1", lease_s=60)
    s.complete("K-C1", token=old)
    r = FileReservations(directory / "c1")
    events = r.late_events("K-C1")
    before = snapshot(r, "K-C1")
    s.complete("K-C1", token=new)
    after = snapshot(FileReservations(directory / "c1"), "K-C1")
    passed = (
        old != new
        and before.get("token") == new
        and before.get("state") == IN_FLIGHT
        and after.get("state") == COMPLETED
        and len(events) == 1
        and events[0].get("late_token") == old
        and events[0].get("current_token") == new
    )
    return {
        "pass": passed, "old_token": old, "new_token": new,
        "before": before, "after": after, "late_events": events,
    }


class PausedCompletion(FileReservations):
    """Instrument only this old holder; stop AFTER token check, BEFORE _write."""

    def __init__(self, directory: Path) -> None:
        super().__init__(directory)
        self.reached = threading.Event()
        self.resume = threading.Event()
        self.wait_s = 10.0
        self.pause_count = 0

    def _write(self, key: str, entry: dict[str, Any]) -> None:
        if threading.current_thread().name == "SEC004-old-holder" and entry.get("state") == COMPLETED:
            self.pause_count += 1
            self.reached.set()
            if not self.resume.wait(timeout=self.wait_s):
                raise TimeoutError("old holder did not receive resume")
        super()._write(key, entry)


def c2_race(directory: Path) -> dict[str, Any]:
    d = directory / "c2"
    old_store = PausedCompletion(d)
    admin = FileReservations(d)
    old = old_store.reserve("K-C2", lease_s=0)
    errors: list[str] = []

    def old_completion() -> None:
        try:
            old_store.complete("K-C2", token=old)
        except Exception as exc:
            errors.append(type(exc).__name__ + ": " + str(exc))

    t = threading.Thread(target=old_completion, name="SEC004-old-holder", daemon=True)
    t.start()
    result: dict[str, Any] = {}
    try:
        if not old_store.reached.wait(timeout=10):
            raise Inconclusive("old holder never reached post-token-check _write")
        paused = snapshot(FileReservations(d), "K-C2")
        if paused.get("token") != old:
            raise Inconclusive("old token changed before release")
        admin.release("K-C2", by="synthetic-operator", reason="test expired lease")
        new = admin.reserve("K-C2", lease_s=60)
        fresh = FileReservations(d)
        before = snapshot(fresh, "K-C2")
        if new == old or before.get("token") != new or before.get("state") != IN_FLIGHT:
            raise Inconclusive("new reservation was not observed before old resume")
        result = {
            "old_token": old, "new_token": new,
            "paused": paused, "before_resume": before,
            "pause_count": old_store.pause_count,
            "released_history_count_before_resume": len(admin.released_history("K-C2")),
            "ordered": True,
        }
    finally:
        old_store.resume.set()
        t.join(timeout=10)
    if t.is_alive():
        raise Inconclusive("old completion thread remained alive")
    if errors:
        raise Inconclusive("old completion failed: " + repr(errors))
    fresh = FileReservations(d)
    after = snapshot(fresh, "K-C2")
    events = fresh.late_events("K-C2")
    result.update({
        "after_resume": after, "late_events": events,
        "released_history_count_after_resume": len(fresh.released_history("K-C2")),
        "p2_old_token_replaced_new": after.get("token") == old and after.get("state") == COMPLETED,
        "p3_no_stale_late_event": not any(
            e.get("event") == "late_complete" and e.get("late_token") == old for e in events
        ),
        "new_token_survives": after.get("token") == new and after.get("state") == IN_FLIGHT,
    })
    return result


def c3_completed_refusal(directory: Path) -> dict[str, Any]:
    s = FileReservations(directory / "c3")
    token = s.reserve("K-C3", lease_s=60)
    s.complete("K-C3", token=token)
    before = snapshot(s, "K-C3")
    refused = False
    try:
        s.release("K-C3", by="synthetic-operator", reason="should be refused")
    except ValueError:
        refused = True
    after = snapshot(FileReservations(directory / "c3"), "K-C3")
    return {"pass": refused and before["sha256"] == after["sha256"], "refused": refused, "before": before, "after": after}


def run() -> int:
    print("EXPERIMENT=SEC-004")
    print("PHASE=REGISTERED_PROBE")
    print("REGISTRATION=docs/SEC004_PREREG.md")
    print("PYTHON=" + platform.python_version())
    print("PLATFORM=" + platform.platform())
    actual = {}
    for name, expected in EXPECTED_BLOBS.items():
        path = ROOT / name
        if not path.is_file():
            print("GATE=INCONCLUSIVE_MISSING_SOURCE " + name)
            return 2
        actual[name] = blob_id(path)
        if actual[name] != expected:
            print("GATE=INCONCLUSIVE_SOURCE_CHANGED " + name)
            print("EXPECTED_BLOB=" + expected)
            print("OBSERVED_BLOB=" + actual[name])
            return 2

    started = time.monotonic()
    try:
        with tempfile.TemporaryDirectory(prefix="sec004-local-") as t:
            d = Path(t)
            cases = {
                "C0": c0_memory(),
                "C1": c1_file(d),
                "C2": c2_race(d),
                "C3": c3_completed_refusal(d),
            }
    except Exception as exc:
        print("GATE=INCONCLUSIVE_PROBE_EXCEPTION")
        print("ERROR=" + type(exc).__name__ + ": " + str(exc))
        return 2

    controls = cases["C0"]["pass"] and cases["C1"]["pass"] and cases["C3"]["pass"]
    c2 = cases["C2"]
    instrument = c2.get("pause_count") == 1 and c2.get("ordered") is True
    if not controls or not instrument:
        verdict = "INCONCLUSIVE"
    elif c2["p2_old_token_replaced_new"]:
        verdict = "SECURITY_FAIL"
    elif c2["new_token_survives"] and not c2["p3_no_stale_late_event"]:
        verdict = "BOUNDED_SECURITY_PASS"
    else:
        verdict = "UNEXPECTED"

    summary = {
        "experiment": "SEC-004", "source_git_blobs": actual,
        "duration_s": round(time.monotonic() - started, 4),
        "cases": cases,
        "predictions": {
            "P0": cases["C0"]["pass"],
            "P1": cases["C1"]["pass"],
            "P2": c2["p2_old_token_replaced_new"],
            "P3": c2["p3_no_stale_late_event"],
            "P4": cases["C3"]["pass"],
            "P5": instrument,
        },
        "verdict": verdict,
        "cross_substrate_verified": False,
        "independent_validation": False,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    print("GATE=" + verdict)
    return 0 if verdict != "INCONCLUSIVE" else 2


if __name__ == "__main__":
    raise SystemExit(run())
