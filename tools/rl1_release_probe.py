#!/usr/bin/env python3
"""RL-1 probe (registration: docs/RL1_PREREG.md, commit 2169410, pushed before this file existed).

  python tools/rl1_release_probe.py                  judges L1, L2, L4 as registered; prints L3 (context, not scored)
  python tools/rl1_release_probe.py --sabotage       release() raises unless by == "operator"; exit 1 only if L1 is REFUTED
  python tools/rl1_release_probe.py --sabotage-noop  the sabotage path with the unmodified method; L1 must hold, exit 0

Imports the real stores from sovereign_veritas/idempotency.py. Stdlib only. Timestamps and tokens are left out of
the digest; everything else that the predictions read is in it.
"""
import ast
import hashlib
import json
import os
import sys
import tempfile
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.dont_write_bytecode = True

from sovereign_veritas import idempotency as idem  # noqa: E402

RECORDED = None  # pinned in a separate commit after the registered run
BY, WHY = "human:chad", "checked downstream"
RELEASED_KEYS = {"at", "to", "by", "why"}


def to_unknown(store, key):
    token = store.reserve(key, lease_s=30.0)
    store.unknown(key, "executor raised", token=token)
    return store.state(key)


def released_entry(store, key):
    hist = store.released_history(key)
    return hist[-1][-1] if hist and hist[-1] else None


def attempt(store, key):
    try:
        store.release(key, by=BY, reason=WHY)
        return "accepted"
    except ValueError as e:
        return f"raised: {e}"


def run_class(name, store):
    out = {}
    # R0 / L4: a key that is not UNKNOWN (fresh IN_FLIGHT, 30 s lease) must be refused.
    store.reserve("R0", lease_s=30.0)
    try:
        store.release("R0", by="operator", reason="anti-vacuity")
        out["R0"] = "accepted"
    except ValueError as e:
        out["R0"] = "refused" if "only from UNKNOWN" in str(e) else f"other error: {e}"
    # R1: a script releases directly.
    out["R1_state_before"] = to_unknown(store, "R1")
    out["R1"] = attempt(store, "R1")
    # R2: the same call from a thread started by an automated loop.
    out["R2_state_before"] = to_unknown(store, "R2")
    box = {}
    for _ in range(1):  # the "automated loop": one iteration, starts the releasing thread
        t = threading.Thread(target=lambda: box.setdefault("r", attempt(store, "R2")))
        t.start()
        t.join()
    out["R2"] = box["r"]
    e1, e2 = released_entry(store, "R1"), released_entry(store, "R2")
    out["R1_entry_keys"] = sorted(e1) if e1 else None
    out["R2_entry_keys"] = sorted(e2) if e2 else None
    out["R1_entry_wo_at"] = {k: v for k, v in e1.items() if k != "at"} if e1 else None
    out["R2_entry_wo_at"] = {k: v for k, v in e2.items() if k != "at"} if e2 else None
    print(f"  {name:20s} R0 {out['R0']}; R1 {out['R1']}; R2 {out['R2']}")
    print(f"  {name:20s} R1 entry {out['R1_entry_wo_at']}  R2 entry {out['R2_entry_wo_at']}")
    return out


def l3_scan():
    sites = []
    for top in ("sovereign_veritas", "tools"):
        for dp, _, fs in os.walk(os.path.join(ROOT, top)):
            for f in fs:
                if not f.endswith(".py"):
                    continue
                p = os.path.join(dp, f)
                for node in ast.walk(ast.parse(open(p, encoding="utf-8").read())):
                    if (isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "release"
                            and any(k.arg == "by" and isinstance(k.value, ast.Constant) and k.value.value == "system"
                                    for k in node.keywords)):
                        sites.append(f"{os.path.relpath(p, ROOT)}:{node.lineno}")
    return sorted(sites)


def main():
    sabotage = "--sabotage" in sys.argv
    noop = "--sabotage-noop" in sys.argv
    mode = "SABOTAGE: release() raises unless by == 'operator'" if sabotage else (
        "SABOTAGE-NOOP: sabotage path, unmodified release()" if noop else "registered run")
    print(f"RL-1 | {mode} | python {sys.version.split()[0]}")
    if sabotage or noop:
        for cls in (idem.MemoryReservations, idem.FileReservations):
            orig = cls.release
            if sabotage:
                def guarded(self, key, by, reason, _orig=orig):
                    if by != "operator":
                        raise ValueError(f"sabotage: release by {by!r} refused")
                    return _orig(self, key, by, reason)
                cls.release = guarded
            else:
                cls.release = orig

    res = {}
    with tempfile.TemporaryDirectory() as d:
        res["memory"] = run_class("MemoryReservations", idem.MemoryReservations())
        res["file"] = run_class("FileReservations", idem.FileReservations(d))
    sites = l3_scan()
    print(f"  L3 (context, not scored) release(..., by='system') call sites in sovereign_veritas/ and tools/: "
          f"{len(sites)} {sites}")

    v = {}
    v["L1"] = all(res[c][r] == "accepted" and res[c][f"{r}_entry_wo_at"] is not None
                  and res[c][f"{r}_entry_wo_at"].get("by") == BY for c in res for r in ("R1", "R2"))
    v["L2"] = all(res[c][f"{r}_entry_keys"] is not None and set(res[c][f"{r}_entry_keys"]) == RELEASED_KEYS
                  for c in res for r in ("R1", "R2")) and all(
                  res[c]["R1_entry_wo_at"] == res[c]["R2_entry_wo_at"] for c in res)
    v["L4"] = all(res[c]["R0"] == "refused" for c in res)

    for k, ok in v.items():
        print(f"  {k}  {'HELD' if ok else 'REFUTED'}")
    held = tuple(k for k, ok in v.items() if ok)
    dg = hashlib.sha256(json.dumps({"r": res, "v": v, "l3": sites}, sort_keys=True).encode()).hexdigest()
    print(f"VERDICT {len(held)} of {len(v)} as registered (L3 is context; sabotage and no-op control run separately)")
    print(f"DIGEST {dg}")
    if sabotage:
        return 1 if not v["L1"] else 0   # exit 1 only because L1 is refuted
    if noop:
        return 0 if v["L1"] else 1
    if RECORDED is None:
        return 0 if all(v.values()) else 1
    return 0 if (held, dg) == RECORDED else 1


if __name__ == "__main__":
    sys.exit(main())
