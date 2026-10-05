#!/usr/bin/env python3
"""OBS-1 round one: harness and runner (registration docs/OBS1_PREREG.md).

  python tools/obs1_run.py      the registered run: P6, Amos Tipton's five cases (P1-P5, P10), controls P7-P9
                                writes the evidence bundle to results/obs1/run/; exit 0 only if every prediction holds
Linux; stdlib plus this repository. The observer runs as a separate process (tools/obs1_observer.py).
"""
import hashlib
import json
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.dont_write_bytecode = True

from obs1_compare import compare, invariant_violations, matches_expected  # noqa: E402
from obs1_store import Store, StoreClient  # noqa: E402
from obs1_system import PermissionSource, System  # noqa: E402

PKG = os.path.join(ROOT, "docs", "external", "amos-tipton_2026-10-04_obs1-cases_v1.0")
CASES = ["AT-1", "AT-2", "AT-3", "AT-4", "AT-4-DW"]
OUT = os.path.join(ROOT, "results", "obs1", "run")
if "--out" in sys.argv:  # Amendment 1: reruns are written apart from the registered bundle
    OUT = os.path.abspath(sys.argv[sys.argv.index("--out") + 1])
ATTEMPT_BACKSTOP_S = 20.0


def files_digest(d):
    h = hashlib.sha256()
    for name in sorted(os.listdir(d)):
        p = os.path.join(d, name)
        if os.path.isfile(p):
            h.update(name.encode() + b"\0" + open(p, "rb").read() + b"\0")
    return h.hexdigest()


def observe(store_dir, record_id, untouched):
    before = files_digest(store_dir)
    p = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "obs1_observer.py"), store_dir, record_id],
                       capture_output=True, text=True, check=True)
    untouched.append(files_digest(store_dir) == before)  # P10
    return json.loads(p.stdout)


def run_case(case, out_dir, sabotage=None, broken_store=False):
    tmp = tempfile.mkdtemp()
    store = Store(os.path.join(tmp, "store"), case["record"], broken_fence=broken_store)
    perms = PermissionSource()
    system = System(os.path.join(tmp, "system"), StoreClient(store), perms, sabotage=sabotage)
    write_perm = next(s["granted"] for s in case["permission_timeline"] if s["step"] == "execution") is True
    conds = case.get("attempt_conditions") or [{"fence_permission": True, "observation": "available"}] * case["attempts"]
    untouched, tokens, in_force, reports, timeout = [], [], {}, [], None
    rid = case["record"]["record_id"]
    before = observe(store.dir, rid, untouched)
    for i in range(case["attempts"]):
        tok = secrets.token_hex(8)
        tokens.append(tok)
        if i == 0 and case.get("fault"):
            store.configure_fault(case["fault"], tok)
        c = conds[i]
        perms._set(write_perm, c["fence_permission"])
        store.set_observation(tok, c["observation"] == "available")
        in_force[tok] = {"attempt": i + 1, "write": write_perm, "fence": bool(c["fence_permission"]),
                         "observation": c["observation"]}
        box = {}
        th = threading.Thread(target=lambda: box.setdefault("r", system.attempt(
            case["case_id"], i + 1, case["intent"], case["approval"], tok)), daemon=True)
        th.start()
        th.join(ATTEMPT_BACKSTOP_S)
        if "r" not in box:
            timeout = {"attempt": i + 1, "backstop_s": ATTEMPT_BACKSTOP_S}
            break
        reports.append(box["r"])
    store.release_at_end()
    after = observe(store.dir, rid, untouched)
    harness = {"tokens": tokens, "in_force": in_force, "release": store.release_record,
               "fault": case.get("fault"), "sabotage": sabotage, "broken_store": broken_store}
    if timeout:
        result = {"case_id": case["case_id"], "harness_timeout": timeout, "classes": [], "attempts": None}
    else:
        result = compare(case, harness, before, after, reports)
    os.makedirs(out_dir, exist_ok=True)
    for name, obj in (("harness.json", harness), ("reports.json", reports), ("observer_before.json", before),
                      ("observer_after.json", after), ("comparator.json", result)):
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as fh:
            json.dump(obj, fh, indent=1, sort_keys=True)
    shutil.copy(os.path.join(store.dir, "log.jsonl"), os.path.join(out_dir, "store_events.jsonl"))
    shutil.rmtree(tmp)
    return result, harness, reports, after, untouched


def evidence_checks(cid, harness, reports, after):
    """The README's per-case evidence requirements, checked in the store log."""
    ev, tok = after["events"], harness["tokens"]
    by = lambda kind, t: [e for e in ev if e["event"] == kind and e.get("attempt_token") == t]  # noqa: E731
    fails = []

    def need(ok, what):
        if not ok:
            fails.append(what)

    if cid == "AT-1":
        need(len(by("write", tok[0])) == 1 and len([e for e in ev if e["event"] == "write"]) == 1,
             "exactly one write, by attempt 1")
        need(reports[0]["reason"] is None, "COMPLETED has a null reason")
    if cid == "AT-2":
        need(not by("write", tok[0]) and not by("rejected", tok[0]), "no business-write call by attempt 1")
        need(bool(reports[0]["reason"]), "REFUSED has a reason")
    if cid == "AT-3":
        need([e.get("reason") for e in by("rejected", tok[0])] == ["fault"], "one rejected (fault) by attempt 1")
        need(not [e for e in ev if e["event"] == "write"], "no write event")
        need(bool(reports[0]["reason"]), "FAILED has a reason")
    if cid == "AT-4":
        need(len(by("write", tok[0])) == 1, "one write by attempt 1")
        need(not by("write", tok[1]), "attempt 2 writes nothing")
        need(reports[1]["system_status"] == "HELD" and bool(reports[1]["reason"]), "attempt 2 HELD with a reason")
        need(all(r["result"] == "unavailable" for r in by("read", tok[1])), "attempt 2's reads are unavailable")
        need(reports[1]["reconciliation"] is None, "no reconciliation claimed")
    if cid == "AT-4-DW":
        rel = harness["release"] or {}
        f1 = [e for e in ev if e["event"] == "fence" and e["target_token"] == tok[0]]
        need(rel.get("released_at") == "fence" and rel.get("result") == "rejected", "released at fence, rejected")
        need(bool(f1) and rel.get("released_seq") == f1[0]["seq"] + 1, "released seq = fence seq + 1")
        okr = [r for r in by("read", tok[1]) if r["result"] == "ok"]
        w2 = by("write", tok[1])
        need(len(w2) == 1 and not by("write", tok[0]), "exactly one write, by attempt 2")
        need(bool(f1 and okr and w2) and f1[0]["seq"] < okr[-1]["seq"] < w2[0]["seq"], "fence, then ok read, then write")
        need(bool(okr) and rel.get("released_seq", 10**9) < okr[-1]["seq"], "the read includes the rejection")
        rc = reports[1].get("reconciliation") or {}
        need(rc.get("fenced_tokens") == [tok[0]] and okr and rc.get("observed_at_seq") == okr[-1]["seq"]
             and rc.get("observed_writes_by_fenced") == 0 and rc.get("by") == "system", "reconciliation claim matches the log")
    return fails


def main():
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    dirty = bool(subprocess.run(["git", "status", "--porcelain", "--", "tools", "sovereign_veritas"], cwd=ROOT,
                                capture_output=True, text=True).stdout.strip())
    print(f"OBS-1 round one | implementation {commit}{' (DIRTY tree)' if dirty else ''} | cases v1.0 {PKG[len(ROOT)+1:]}")
    v, untouched_all = {}, []

    # P6: the invariant check can fail (before scoring anything)
    clean = [{"seq": 1, "event": "write", "record_id": "r1", "version": 1, "value": "on", "attempt_token": "a"},
             {"seq": 2, "event": "fence", "target_token": "a", "attempt_token": "b"},
             {"seq": 3, "event": "rejected", "record_id": "r1", "attempt_token": "a", "reason": "fenced"}]
    broken = {
        "seq gap": [clean[0], dict(clean[1], seq=3)],
        "version jump": [clean[0], dict(clean[0], seq=2, version=3, attempt_token="c")],
        "write after fence": clean[:2] + [dict(clean[0], seq=3, version=2)],
        "fenced rejection without fence": [dict(clean[2], seq=1)],
    }
    found = {k: invariant_violations(b) for k, b in broken.items()}
    for k, f in found.items():
        print(f"P6  broken log '{k}': {f}")
    print(f"P6  clean log: {invariant_violations(clean)}")
    v["P6"] = all(found.values()) and not invariant_violations(clean)

    for n, cid in enumerate(CASES, 1):
        case = json.load(open(os.path.join(PKG, "cases", f"{cid}.json")))
        exp = json.load(open(os.path.join(PKG, "expected", f"{cid}.json")))
        result, harness, reports, after, untouched = run_case(case, os.path.join(OUT, cid))
        untouched_all += untouched
        ok, diffs = matches_expected(result, exp)
        ev_fails = evidence_checks(cid, harness, reports, after) if "harness_timeout" not in result else ["HARNESS_TIMEOUT"]
        print(f"P{n}  {cid:<8} attempts {[(a['decision'], a['system_status']) for a in result.get('attempts') or []]} "
              f"effects {result.get('effect_count')} classes {result.get('classes')} "
              f"mismatches {result.get('status_mismatches')} {result.get('mismatch_detail') or ''}")
        print(f"     expected match: {'yes' if ok else 'NO ' + str(diffs)}; evidence: {'ok' if not ev_fails else ev_fails}"
              f"; release {harness['release']}")
        with open(os.path.join(OUT, cid, "expected_match.json"), "w") as fh:
            json.dump({"matches": ok, "diffs": diffs, "evidence_failures": ev_fails}, fh, indent=1)
        v[f"P{n}"] = ok and not ev_fails

    load = lambda c: json.load(open(os.path.join(PKG, "cases", f"{c}.json")))  # noqa: E731
    exp = lambda c: json.load(open(os.path.join(PKG, "expected", f"{c}.json")))  # noqa: E731
    r7, *_ = run_case(load("AT-4-DW"), os.path.join(OUT, "controls", "P7_broken_store", "AT-4-DW"), broken_store=True)
    print(f"P7  broken store, AT-4-DW: store_defect {r7.get('store_defect')} invariant {r7['invariant']} classes {r7['classes']}")
    v["P7"] = bool(r7.get("store_defect")) and r7["classes"] == []

    r8a, *_ = run_case(load("AT-4"), os.path.join(OUT, "controls", "P8_no_reconcile", "AT-4"), sabotage="no-reconcile")
    r8b, *_ = run_case(load("AT-4-DW"), os.path.join(OUT, "controls", "P8_no_reconcile", "AT-4-DW"), sabotage="no-reconcile")
    m8a, m8b = matches_expected(r8a, exp("AT-4"))[0], matches_expected(r8b, exp("AT-4-DW"))[0]
    print(f"P8  no reconciliation: AT-4 classes {r8a['classes']} matches {m8a}; AT-4-DW classes {r8b['classes']} matches {m8b}")
    v["P8"] = (not m8a and not m8b and {"DUPLICATE", "UNKNOWN_UNRESOLVED_RETRY"} <= set(r8a["classes"])
               and "LATE_WRITE_UNFENCED" in r8b["classes"])

    r9, *_ = run_case(load("AT-2"), os.path.join(OUT, "controls", "P9_stale_permission", "AT-2"), sabotage="stale-permission")
    m9 = matches_expected(r9, exp("AT-2"))[0]
    print(f"P9  stale permission: AT-2 classes {r9['classes']} matches {m9} mismatches {r9.get('mismatch_detail')}")
    v["P9"] = not m9 and "UNAUTHORIZED_EXECUTION" in r9["classes"]

    print(f"P10 observer calls {len(untouched_all)}, store files unchanged by every call: {all(untouched_all)}")
    v["P10"] = bool(untouched_all) and all(untouched_all)

    print()
    for k in ["P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "P9", "P10"]:
        print(f"  {k:<4} {'HELD' if v[k] else 'REFUTED'}")
    print(f"VERDICT  {sum(v.values())} of {len(v)} as registered")
    with open(os.path.join(OUT, "run.json"), "w") as fh:
        json.dump({"implementation_commit": commit, "dirty": dirty, "command": " ".join(["python"] + sys.argv),
                   "verdicts": v}, fh, indent=1)
    return 0 if all(v.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
