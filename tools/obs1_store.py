"""OBS-1 sandbox store (docs/OBS1_INTERFACE.md, frozen at 04bca2d; registration docs/OBS1_PREREG.md).

One record and an append-only log in a directory. set_value, fence and read run one at a time under one exclusive
lock, and each call's event is appended while the lock is held. The store checks no permissions: like any
downstream system it does what it is asked, and the comparator checks each logged action afterwards.

Files: <dir>/record.json, <dir>/log.jsonl. The observer (tools/obs1_observer.py) reads these directly.
"""
import json
import os
import threading


class StoreTimeout(Exception):
    """What the system sees when a reply is lost or a write is held."""


class Store:
    def __init__(self, directory, record, *, broken_fence=False):
        self.dir = directory
        os.makedirs(directory, exist_ok=True)
        self._lock = threading.Lock()
        self._seq = 0
        self._fenced = set()
        self._unavailable = set()
        self._fault, self._fault_token, self._fault_used = None, None, False
        self._held = None            # attempt 1's intercepted set_value under hold_write_until_fence
        self.release_record = None   # {"held_token", "released_at", "released_seq", "result"}
        self._broken_fence = broken_fence  # P7 control: lets a fenced write land
        self._record = dict(record)
        self._write_record()
        open(self._log_path(), "w").close()

    # --- configuration by the harness (not callable by the system: the system only gets a StoreClient) ---
    def configure_fault(self, fault, first_token):
        self._fault, self._fault_token = fault, first_token

    def set_observation(self, token, available):
        if not available:
            self._unavailable.add(token)

    # --- files ---
    def _log_path(self):
        return os.path.join(self.dir, "log.jsonl")

    def _write_record(self):
        tmp = os.path.join(self.dir, "record.json.tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self._record, fh, sort_keys=True)
        os.replace(tmp, os.path.join(self.dir, "record.json"))

    def _append(self, event):
        self._seq += 1
        ev = {"seq": self._seq, **event}
        with open(self._log_path(), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(ev, sort_keys=True) + "\n")
        return ev

    def _events(self):
        with open(self._log_path(), encoding="utf-8") as fh:
            return [json.loads(line) for line in fh if line.strip()]

    # --- the write path, lock held ---
    def _apply_set(self, record_id, new_value, token):
        if token in self._fenced and not self._broken_fence:
            ev = self._append({"event": "rejected", "record_id": record_id, "attempt_token": token, "reason": "fenced"})
            return ev, "rejected"
        self._record["value"] = new_value
        self._record["version"] += 1
        self._write_record()
        ev = self._append({"event": "write", "record_id": record_id, "version": self._record["version"],
                           "value": new_value, "attempt_token": token})
        return ev, "write"

    # --- the three calls of the interface ---
    def set_value(self, record_id, new_value, attempt_token):
        first = (not self._fault_used) and attempt_token == self._fault_token
        if first and self._fault == "hold_write_until_fence":
            self._fault_used = True
            self._held = (record_id, new_value, attempt_token)  # intercepted before the store: not applied, not logged
            raise StoreTimeout("write held by the fault layer; no reply")
        with self._lock:
            if first and self._fault == "fail_before_effect":
                self._fault_used = True
                self._append({"event": "rejected", "record_id": record_id, "attempt_token": attempt_token,
                              "reason": "fault"})
                return {"result": "rejected", "reason": "fault"}
            ev, kind = self._apply_set(record_id, new_value, attempt_token)
            if kind == "rejected":
                return {"result": "rejected", "reason": "fenced"}
            lose = first and self._fault == "lose_ack_after_effect"
            if lose:
                self._fault_used = True
        if lose:
            raise StoreTimeout("write landed; reply lost")
        return {"result": "ok", "version": ev["version"]}

    def fence(self, target_token, attempt_token):
        with self._lock:
            ev = self._append({"event": "fence", "target_token": target_token, "attempt_token": attempt_token})
            self._fenced.add(target_token)
            if self._held and self._held[2] == target_token and self.release_record is None:
                rid, val, tok = self._held          # checkpoint A: inside the same locked step, right after the fence
                rel, kind = self._apply_set(rid, val, tok)
                self.release_record = {"held_token": tok, "released_at": "fence", "released_seq": rel["seq"],
                                       "result": kind}
            return {"result": "ok", "seq": ev["seq"]}

    def read(self, record_id, attempt_token):
        with self._lock:
            if attempt_token in self._unavailable:
                ev = self._append({"event": "read", "record_id": record_id, "attempt_token": attempt_token,
                                   "result": "unavailable"})
                return {"result": "unavailable", "seq": ev["seq"]}
            earlier = self._events()
            ev = self._append({"event": "read", "record_id": record_id, "attempt_token": attempt_token, "result": "ok"})
            return {"result": "ok", "seq": ev["seq"], "events": earlier, "record": dict(self._record)}

    # --- harness only ---
    def release_at_end(self):
        """Checkpoint B: the last attempt has reported and no fence of the held token was applied."""
        with self._lock:
            if self._held and self.release_record is None:
                rid, val, tok = self._held
                rel, kind = self._apply_set(rid, val, tok)
                self.release_record = {"held_token": tok, "released_at": "end_of_attempts",
                                       "released_seq": rel["seq"], "result": kind}


class StoreClient:
    """The only handle the system under test gets: the three calls, nothing else."""

    def __init__(self, store):
        self.set_value, self.fence, self.read = store.set_value, store.fence, store.read
