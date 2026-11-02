#!/usr/bin/env python3
"""SEC-005: does the per-key lock close the SEC-004 race? Registration: docs/SEC005_PREREG.md (committed first).

Two arms in one run: LOCK (the code as it is) and NOLOCK (FileReservations._key_lock replaced by a no-op, in this
process and in its children). The NOLOCK arm is the anti-vacuity control (P6): it must reproduce SEC-004.
`--sabotage` also disables the lock in the LOCK arm, so the verdict must change (exit 1).
Exit 0 only on FIXED_IN_TESTED_SCHEDULES with the recorded digest. Exit 0 is not a proof of anything beyond the
schedules listed in the registration.
"""
from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import json
import platform
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sovereign_veritas.idempotency import COMPLETED, IN_FLIGHT, FileReservations  # noqa: E402

_spec = importlib.util.spec_from_file_location("sec004_probe", ROOT / "tools" / "sec004_release_race_probe.py")
sec004 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sec004)  # the SEC-004 case functions, imported, not copied

BLOCK_S = 3.0
DONE_S = 20.0
RECORDED: tuple[tuple[str, ...], str] | None = None  # pinned in a separate commit after the first run

_REAL_LOCK = FileReservations._key_lock


@contextlib.contextmanager
def _no_lock(self: FileReservations, key: str):  # noqa: ARG001
    yield


def set_lock(enabled: bool) -> None:
    FileReservations._key_lock = _REAL_LOCK if enabled else _no_lock  # type: ignore[method-assign]


class Inconclusive(Exception):
    pass


def l0(d: Path) -> dict[str, Any]:
    c0, c1, c3 = sec004.c0_memory(), sec004.c1_file(d), sec004.c3_completed_refusal(d)
    return {"C0": c0["pass"], "C1": c1["pass"], "C3": c3["pass"]}


def l1(d: Path) -> dict[str, Any]:
    """The SEC-004 schedule: A paused after its token check; B releases and reserves."""
    d = d / "l1"
    key = "K-L1"
    a_store = sec004.PausedCompletion(d)
    a_store.wait_s = DONE_S
    old = a_store.reserve(key, lease_s=0)
    a_err: list[str] = []

    def a() -> None:
        try:
            a_store.complete(key, token=old)
        except Exception as exc:  # kept as evidence
            a_err.append(type(exc).__name__)

    b_out: dict[str, Any] = {"released": False, "new": None, "err": None}

    def b() -> None:
        admin = FileReservations(d)
        try:
            admin.release(key, by="synthetic-operator", reason="test expired lease")
            b_out["released"] = True
            b_out["new"] = admin.reserve(key, lease_s=60)
        except Exception as exc:
            b_out["err"] = type(exc).__name__

    ta = threading.Thread(target=a, name="SEC004-old-holder", daemon=True)
    ta.start()
    if not a_store.reached.wait(timeout=DONE_S):
        raise Inconclusive("L1: A never reached its post-check write")
    tb = threading.Thread(target=b, name="SEC005-admin", daemon=True)
    tb.start()
    tb.join(BLOCK_S)
    b_blocked = tb.is_alive()
    a_store.resume.set()
    ta.join(DONE_S)
    tb.join(DONE_S)
    if ta.is_alive() or tb.is_alive():
        raise Inconclusive("L1: a thread did not finish within DONE_S")
    fresh = FileReservations(d)
    after = sec004.snapshot(fresh, key)
    new = b_out["new"]
    return {
        "a_errors": a_err, "pause_count": a_store.pause_count,
        "b_blocked_while_a_paused": b_blocked, "b_released": b_out["released"], "b_error": b_out["err"],
        "new_token_issued": new is not None,
        "final_is_old": after.get("token") == old, "final_state": after.get("state"),
        "overwrite": new is not None and after.get("token") == old,
        "released_history": len(fresh.released_history(key)),
    }


class PausedBeforeLock(FileReservations):
    def __init__(self, directory: Path) -> None:
        super().__init__(directory)
        self.reached = threading.Event()
        self.resume = threading.Event()

    def _move(self, *args: Any, **kwargs: Any) -> None:
        if threading.current_thread().name == "SEC005-late-holder":
            self.reached.set()
            if not self.resume.wait(timeout=DONE_S):
                raise TimeoutError("late holder did not receive resume")
        super()._move(*args, **kwargs)


def l2(d: Path) -> dict[str, Any]:
    d = d / "l2"
    key = "K-L2"
    a_store = PausedBeforeLock(d)
    old = a_store.reserve(key, lease_s=0)
    a_err: list[str] = []

    def a() -> None:
        try:
            a_store.complete(key, token=old)
        except Exception as exc:
            a_err.append(type(exc).__name__)

    ta = threading.Thread(target=a, name="SEC005-late-holder", daemon=True)
    ta.start()
    if not a_store.reached.wait(timeout=DONE_S):
        raise Inconclusive("L2: A never reached its pause")
    admin = FileReservations(d)
    admin.release(key, by="synthetic-operator", reason="test expired lease")
    new = admin.reserve(key, lease_s=60)
    a_store.resume.set()
    ta.join(DONE_S)
    if ta.is_alive():
        raise Inconclusive("L2: A did not finish within DONE_S")
    fresh = FileReservations(d)
    after = sec004.snapshot(fresh, key)
    late = [e for e in fresh.late_events(key) if e.get("event") == "late_complete" and e.get("late_token") == old]
    return {"a_errors": a_err, "final_is_new": after.get("token") == new, "final_state": after.get("state"),
            "late_complete_for_old": len(late)}


CHILD = r"""
import contextlib, os, sys, time
sys.path.insert(0, sys.argv[1])
from sovereign_veritas.idempotency import FileReservations
if sys.argv[2] == "nolock":
    @contextlib.contextmanager
    def _no_lock(self, key):
        yield
    FileReservations._key_lock = _no_lock
store, key, held, go, mode = FileReservations(sys.argv[3]), sys.argv[4], sys.argv[5], sys.argv[6], sys.argv[7]
with store._key_lock(key):
    open(held, "w").close()
    if mode == "crash":
        os._exit(0)
    end = time.monotonic() + float(sys.argv[8])
    while not os.path.exists(go) and time.monotonic() < end:
        time.sleep(0.01)
"""


def _child(d: Path, key: str, lock: bool, mode: str) -> tuple[subprocess.Popen, Path, Path]:
    held, go = d / f"{mode}.held", d / f"{mode}.go"
    p = subprocess.Popen([sys.executable, "-I", "-c", CHILD, str(ROOT), "lock" if lock else "nolock", str(d), key,
                          str(held), str(go), mode, str(DONE_S)])
    end = time.monotonic() + DONE_S
    while not held.exists():
        if time.monotonic() > end or p.poll() not in (None, 0):
            p.kill()
            raise Inconclusive(f"{mode}: child never took the lock")
        time.sleep(0.01)
    return p, held, go


def _release_thread(d: Path, key: str) -> tuple[threading.Thread, dict[str, Any]]:
    out: dict[str, Any] = {"done": False, "err": None}

    def r() -> None:
        try:
            FileReservations(d).release(key, by="synthetic-operator", reason="test expired lease")
            out["done"] = True
        except Exception as exc:
            out["err"] = type(exc).__name__

    t = threading.Thread(target=r, daemon=True)
    t.start()
    return t, out


def l3(d: Path, lock: bool) -> dict[str, Any]:
    d = d / "l3"
    key = "K-L3"
    FileReservations(d).reserve(key, lease_s=0)
    p, _, go = _child(d, key, lock, "hold")
    t, out = _release_thread(d, key)
    t.join(BLOCK_S)
    blocked = t.is_alive()
    go.touch()
    t.join(DONE_S)
    rc = p.wait(timeout=DONE_S)
    if t.is_alive():
        raise Inconclusive("L3: release did not finish within DONE_S after the child let go")
    return {"blocked_while_child_held": blocked, "release_done": out["done"], "release_error": out["err"],
            "child_rc": rc}


def l4(d: Path, lock: bool) -> dict[str, Any]:
    d = d / "l4"
    key = "K-L4"
    FileReservations(d).reserve(key, lease_s=0)
    p, _, _ = _child(d, key, lock, "crash")
    rc = p.wait(timeout=DONE_S)
    t, out = _release_thread(d, key)
    t.join(DONE_S)
    return {"child_rc": rc, "release_done_after_crash": (not t.is_alive()) and out["done"],
            "release_error": out["err"]}


def arm(lock: bool) -> dict[str, Any]:
    set_lock(lock)
    try:
        with tempfile.TemporaryDirectory(prefix="sec005-") as t:
            d = Path(t)
            return {"L0": l0(d), "L1": l1(d), "L2": l2(d), "L3": l3(d, lock), "L4": l4(d, lock)}
    finally:
        set_lock(True)


def score(lk: dict[str, Any], nl: dict[str, Any]) -> dict[str, bool]:
    a1, a2, a3, a4 = lk["L1"], lk["L2"], lk["L3"], lk["L4"]
    s1, s3 = nl["L1"], nl["L3"]
    return {
        "P1": all(lk["L0"].values()),
        "P2": (a1["b_blocked_while_a_paused"] and a1["final_is_old"] and a1["final_state"] == COMPLETED
               and a1["b_error"] == "ValueError" and not a1["new_token_issued"] and a1["released_history"] == 0
               and not a1["overwrite"] and a1["pause_count"] == 1 and not a1["a_errors"]),
        "P3": (a2["final_is_new"] and a2["final_state"] == IN_FLIGHT and a2["late_complete_for_old"] == 1
               and not a2["a_errors"]),
        "P4": a3["blocked_while_child_held"] and a3["release_done"],
        "P5": a4["release_done_after_crash"],
        "P6": (all(nl["L0"].values()) and not s1["b_blocked_while_a_paused"] and s1["new_token_issued"]
               and s1["overwrite"] and not s3["blocked_while_child_held"]),
    }


def main() -> int:
    sabotage = "--sabotage" in sys.argv[1:]
    print("EXPERIMENT=SEC-005")
    print("REGISTRATION=docs/SEC005_PREREG.md")
    print("PYTHON=" + platform.python_version())
    print("PLATFORM=" + platform.platform())
    body = (ROOT / "sovereign_veritas" / "idempotency.py").read_bytes()
    print("IDEMPOTENCY_BLOB=" + hashlib.sha1(b"blob " + str(len(body)).encode() + b"\0" + body).hexdigest())
    print("SABOTAGE=" + str(sabotage))
    started = time.monotonic()
    try:
        lk = arm(lock=not sabotage)
        nl = arm(lock=False)
    except Inconclusive as exc:
        print("VERDICT INCONCLUSIVE: " + str(exc))
        return 1
    preds = score(lk, nl)
    obs = {"LOCK_ARM": lk, "NOLOCK_ARM": nl}
    print(json.dumps(obs, indent=2, sort_keys=True))
    for k, v in preds.items():
        print(f"{k} {'HELD' if v else 'REFUTED'}")
    if lk["L1"]["overwrite"]:
        verdict = "NOT_FIXED"
    elif all(preds.values()):
        verdict = "FIXED_IN_TESTED_SCHEDULES"
    elif not preds["P1"] or not preds["P6"]:
        verdict = "INCONCLUSIVE"
    else:
        verdict = "UNEXPECTED"
    held = tuple(k for k, v in preds.items() if v)
    digest = hashlib.sha256(json.dumps(obs, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    print(f"DURATION_S={time.monotonic() - started:.1f}")
    print(f"VERDICT {verdict}: {len(held)} of {len(preds)} as registered")
    print("DIGEST=" + digest)
    if verdict != "FIXED_IN_TESTED_SCHEDULES":
        return 1
    if RECORDED is None:
        print("RECORDED=UNPINNED")
        return 0
    if (held, digest) != RECORDED:
        print("RECORDED MISMATCH: expected " + repr(RECORDED))
        return 1
    print("RECORDED MATCH")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
