#!/usr/bin/env python3
"""SEC-006: randomized multi-process stress test of the SEC-005 lock. Registration: docs/SEC006_PREREG.md
(committed and pushed before this file existed).

Two arms on the same seeds: LOCK (code as is) and NOLOCK (FileReservations._key_lock replaced by a no-op in every
worker). Oracle I1, per key: the tokens found in the active file plus the released files equal the granted tokens,
each exactly once. `--sabotage` disables the lock in the LOCK arm too. `--seeds dev` runs the unscored dev seeds.
Counts depend on OS scheduling, so the DIGEST is printed for the record but not pinned.
"""
from __future__ import annotations

import collections
import hashlib
import json
import platform
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sovereign_veritas.idempotency import FileReservations  # noqa: E402

P_WORKERS = 6
K_KEYS = 8
M_OPS = 250
TRIAL_TIMEOUT_S = 120.0
REGISTERED_SEEDS = list(range(1, 21))
DEV_SEEDS = [101, 102, 103]

WORKER = r"""
import contextlib, json, random, sys, time
sys.path.insert(0, sys.argv[1])
from sovereign_veritas.idempotency import FileReservations, ReservationRefused
root, d, seed, idx, arm, m, k = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5], int(sys.argv[6]), int(sys.argv[7])
if arm == "nolock":
    @contextlib.contextmanager
    def _no_lock(self, key):
        yield
    FileReservations._key_lock = _no_lock
rng = random.Random(seed * 1000 + idx)
_real_write = FileReservations._write
def _slow_write(self, key, entry):
    time.sleep(rng.uniform(0.0, 0.003))
    _real_write(self, key, entry)
FileReservations._write = _slow_write
store = FileReservations(d)
keys = [f"K{i}" for i in range(k)]
current = {}          # key -> token this worker currently holds
held = {key: [] for key in keys}   # every token this worker was ever granted, per key
c = {"reserve_ok": 0, "reserve_refused": 0, "release_ok": 0, "release_refused": 0, "unknown_calls": 0,
     "complete_calls": 0, "stale_complete_calls": 0}
errors = []
ops = ["reserve", "unknown", "complete", "stale_complete", "release"]
weights = [0.35, 0.20, 0.05, 0.10, 0.30]
for _ in range(m):
    op = rng.choices(ops, weights)[0]
    key = rng.choice(keys)
    try:
        if op == "reserve":
            try:
                tok = store.reserve(key, lease_s=0)
                current[key] = tok; held[key].append(tok); c["reserve_ok"] += 1
            except ReservationRefused:
                c["reserve_refused"] += 1
        elif op == "unknown" and key in current:
            store.unknown(key, "stress", token=current[key]); c["unknown_calls"] += 1
        elif op == "complete" and key in current:
            store.complete(key, token=current[key]); c["complete_calls"] += 1
        elif op == "stale_complete":
            old = [t for t in held[key] if t != current.get(key)]
            if old:
                store.complete(key, token=rng.choice(old)); c["stale_complete_calls"] += 1
        elif op == "release":
            try:
                store.release(key, by="stress", reason="stress"); c["release_ok"] += 1
                current.pop(key, None)
            except ValueError:
                c["release_refused"] += 1
    except Exception as exc:  # anything else is unexpected and reported
        errors.append(f"{op}:{type(exc).__name__}:{exc}"[:200])
json.dump({"granted": held, "counts": c, "errors": errors}, open(f"{d}/worker{idx}.json", "w"))
"""


def run_trial(seed: int, arm: str, d: Path) -> dict:
    procs = [subprocess.Popen([sys.executable, "-I", "-c", WORKER, str(ROOT), str(d), str(seed), str(i), arm,
                               str(M_OPS), str(K_KEYS)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
             for i in range(P_WORKERS)]
    deadline = time.monotonic() + TRIAL_TIMEOUT_S
    timed_out, rcs = False, []
    for p in procs:
        try:
            p.wait(timeout=max(0.1, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            timed_out = True
            p.kill()
            p.wait()
        rcs.append(p.returncode)
    granted: dict[str, list[str]] = collections.defaultdict(list)
    counts: collections.Counter = collections.Counter()
    errors: list[str] = []
    for i in range(P_WORKERS):
        f = d / f"worker{i}.json"
        if not f.exists():
            errors.append(f"worker{i}: no log")
            continue
        w = json.loads(f.read_text())
        for key, toks in w["granted"].items():
            granted[key].extend(toks)
        counts.update(w["counts"])
        errors.extend(w["errors"])
    store = FileReservations(d)
    violations, unreadable, late_complete = [], 0, 0
    for key in [f"K{i}" for i in range(K_KEYS)]:
        active = store._path(key)
        files = ([active] if active.exists() else []) + sorted(active.parent.glob(active.stem + ".released-*.json"))
        found = []
        for f in files:
            try:
                found.append(json.loads(f.read_text())["token"])
            except Exception:
                unreadable += 1
        if collections.Counter(found) != collections.Counter(granted[key]):
            violations.append(key)
        # Amendment 1 (2026-11-06, docs/SEC006_RESULTS.md): read the late-event log line by line here instead of
        # store.late_events(), which raises on a corrupted line. That crashed the oracle in the NOLOCK arm on
        # Windows CI. An unreadable line counts in `unreadable`, so in the LOCK arm it fails P1.
        lp = store._late_path(key)
        if lp.exists():
            for line in lp.read_bytes().decode("utf-8", "replace").splitlines():
                if not line.strip():
                    continue
                try:
                    e = json.loads(line)
                except ValueError:
                    unreadable += 1
                    continue
                late_complete += 1 if isinstance(e, dict) and e.get("event") == "late_complete" else 0
    return {"seed": seed, "arm": arm, "violations": len(violations), "unreadable": unreadable,
            "late_complete": late_complete, "counts": dict(sorted(counts.items())), "errors": errors,
            "timed_out": timed_out, "worker_rcs": rcs}


def main() -> int:
    sabotage = "--sabotage" in sys.argv[1:]
    dev = "--seeds" in sys.argv[1:] and sys.argv[sys.argv.index("--seeds") + 1] == "dev"
    seeds = DEV_SEEDS if dev else REGISTERED_SEEDS
    body = (ROOT / "sovereign_veritas" / "idempotency.py").read_bytes()
    print("EXPERIMENT=SEC-006")
    print("REGISTRATION=docs/SEC006_PREREG.md")
    print("PYTHON=" + platform.python_version())
    print("PLATFORM=" + platform.platform())
    print("IDEMPOTENCY_BLOB=" + hashlib.sha1(b"blob " + str(len(body)).encode() + b"\0" + body).hexdigest())
    print(f"SEEDS={'dev' if dev else 'registered'} {seeds[0]}..{seeds[-1]}  SABOTAGE={sabotage}")
    print(f"WORKLOAD P={P_WORKERS} K={K_KEYS} M={M_OPS}")
    started = time.monotonic()
    trials = []
    for seed in seeds:
        for arm in ("lock", "nolock"):
            run_arm = "nolock" if (sabotage or arm == "nolock") else "lock"
            with tempfile.TemporaryDirectory(prefix="sec006-") as t:
                r = run_trial(seed, run_arm, Path(t))
            r["arm"] = arm
            trials.append(r)
            print(f"seed {seed:3d} {arm:6s} violations={r['violations']} late_complete={r['late_complete']:3d} "
                  f"release_ok={r['counts'].get('release_ok', 0):3d} errors={len(r['errors'])} "
                  f"timeout={r['timed_out']} rcs={r['worker_rcs']}", flush=True)
    lk = [r for r in trials if r["arm"] == "lock"]
    nl = [r for r in trials if r["arm"] == "nolock"]
    for r in lk:
        for e in r["errors"][:3]:
            print(f"  LOCK seed {r['seed']} error: {e}")
    preds = {
        "P1": all(r["violations"] == 0 and r["unreadable"] == 0 for r in lk),
        "P2": sum(1 for r in nl if r["violations"] > 0) >= 1,
        "P3": all(not r["timed_out"] and all(rc == 0 for rc in r["worker_rcs"]) and not r["errors"] for r in lk),
        "P4": (sum(r["late_complete"] for r in lk) >= 100 and sum(r["counts"].get("release_ok", 0) for r in lk) >= 100),
    }
    print(f"LOCK   trials with a violation: {sum(1 for r in lk if r['violations'])} of {len(lk)}; "
          f"late_complete total {sum(r['late_complete'] for r in lk)}; "
          f"releases {sum(r['counts'].get('release_ok', 0) for r in lk)}")
    print(f"NOLOCK trials with a violation: {sum(1 for r in nl if r['violations'])} of {len(nl)}; "
          f"keys violated total {sum(r['violations'] for r in nl)}")
    for k, v in preds.items():
        print(f"{k} {'HELD' if v else 'REFUTED'}")
    if not preds["P1"]:
        verdict = "VIOLATION"
    elif all(preds.values()):
        verdict = "NO_VIOLATION_IN_TESTED_SCHEDULES"
    else:
        verdict = "INCONCLUSIVE"
    summary = [(r["seed"], r["arm"], r["violations"], r["late_complete"], r["counts"]) for r in trials]
    digest = hashlib.sha256(json.dumps(summary, sort_keys=True).encode()).hexdigest()
    print(f"DURATION_S={time.monotonic() - started:.1f}")
    print(f"VERDICT {verdict}: {sum(preds.values())} of {len(preds)} as registered")
    print("DIGEST=" + digest + "  (not pinned: counts depend on OS scheduling)")
    if dev:
        print("NOTE dev seeds: not scored")
    return 0 if verdict == "NO_VIOLATION_IN_TESTED_SCHEDULES" else 1


if __name__ == "__main__":
    raise SystemExit(main())
