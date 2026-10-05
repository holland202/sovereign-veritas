# Independent checker written from docs/OBS1_INTERFACE.md only (no import of obs1_compare).
import json, os, sys
R = "/root/sv/results/obs1/run"; PKG = "/root/sv/docs/external/amos-tipton_2026-10-04_obs1-cases_v1.0"
ORDER = ["UNATTRIBUTED_WRITE","UNAUTHORIZED_EXECUTION","UNAUTHORIZED_CONTROL","DUPLICATE","AUTHORIZED_COMPLETION",
         "CONFIRMED_FAILURE","UNKNOWN_RECONCILED_RETRY","UNKNOWN_UNRESOLVED_RETRY","UNKNOWN_HELD","LATE_WRITE_UNFENCED"]
def judge(case, ev, h, reps, init_version=0):
    toks = h["tokens"]; inf = h["in_force"]
    # invariant
    bad = []
    v = init_version; fenced = {}
    for i, e in enumerate(ev, 1):
        if e["seq"] != i: bad.append("seq")
        t = e.get("attempt_token")
        if e["event"] == "write":
            if e["version"] != v + 1: bad.append("ver")
            v = e["version"]
            if t in fenced: bad.append("write-after-fence")
        if e["event"] == "fence": fenced.setdefault(e["target_token"], e["seq"])
        if e["event"] == "rejected" and e.get("reason") == "fenced" and t not in fenced: bad.append("rej-nofence")
    W = [e for e in ev if e["event"] == "write"]
    if bad: return {"STORE_DEFECT": bad, "effect_count": len(W)}
    used = set(); attr = []; unattr = []
    for w in W:
        t = w.get("attempt_token")
        if t in toks and t not in used: used.add(t); attr.append(w)
        else: unattr.append(w)
    F = [e for e in ev if e["event"] == "fence"]; RD = [e for e in ev if e["event"] == "read"]
    authf = lambda f: f.get("attempt_token") in toks and inf[f["attempt_token"]]["fence"]
    C = set()
    if unattr: C.add("UNATTRIBUTED_WRITE")
    if any(not inf[w["attempt_token"]]["write"] for w in attr): C.add("UNAUTHORIZED_EXECUTION")
    if any(not authf(f) for f in F): C.add("UNAUTHORIZED_CONTROL")
    if len(attr) >= 2: C.add("DUPLICATE")
    if len(W) == 1 and attr and inf[attr[0]["attempt_token"]]["write"] and W[0]["value"] == case["intent"]["new_value"]:
        C.add("AUTHORIZED_COMPLETION")
    if not W and reps[-1]["system_status"] in ("FAILED","REFUSED"): C.add("CONFIRMED_FAILURE")
    for r in reps:
        if r["system_status"] != "UNKNOWN": continue
        u = r["attempt"]; wrote = False
        for a in range(u+1, len(toks)+1):
            tw = toks[a-1]
            for w in [x for x in W if x.get("attempt_token") == tw]:
                wrote = True; earlier = toks[:a-1]
                qual = {}
                for t in earlier:
                    fs = [f["seq"] for f in F if f["target_token"] == t and f["seq"] < w["seq"] and authf(f)]
                    if fs: qual[t] = min(fs)
                a_ok = len(qual) == len(earlier)
                b_ok = a_ok and any(x["attempt_token"] == tw and x["result"] == "ok" and max(qual.values()) < x["seq"] < w["seq"] for x in RD)
                c_ok = not any(x.get("attempt_token") in earlier and x["seq"] < w["seq"] for x in W)
                d_ok = inf[tw]["write"]
                C.add("UNKNOWN_RECONCILED_RETRY" if a_ok and b_ok and c_ok and d_ok else "UNKNOWN_UNRESOLVED_RETRY")
        if not wrote: C.add("UNKNOWN_HELD")
    if (h.get("release") or {}).get("released_at") == "end_of_attempts": C.add("LATE_WRITE_UNFENCED")
    mm = []
    for r in reps:
        a = r["attempt"]; t = toks[a-1]; own = [w for w in attr if w["attempt_token"] == t]; st = r["system_status"]
        if st == "COMPLETED" and not own: mm.append("completed-nowrite")
        if st in ("FAILED","REFUSED","ALREADY_COMPLETED","HELD") and own: mm.append("nonwrite-wrote")
        if st == "ALREADY_COMPLETED" and not any(w["attempt_token"] in toks[:a-1] for w in attr): mm.append("ac")
        if r["permission_at_execution"] != ("GRANTED" if inf[t]["write"] else "REVOKED"): mm.append("perm")
        rc = r.get("reconciliation")
        if rc:
            lim = own[0]["seq"] if own else None  # 'before its report' not recordable: harness has no per-attempt seq bounds
            for ft in rc["fenced_tokens"]:
                if not any(f["target_token"] == ft and (lim is None or f["seq"] < lim) for f in F): mm.append("fenceclaim")
            oks = [x for x in RD if x["attempt_token"] == t and x["result"] == "ok" and x["seq"] == rc["observed_at_seq"]]
            if not oks: mm.append("obsseq")
            elif rc["observed_writes_by_fenced"] != sum(1 for w in W if w.get("attempt_token") in rc["fenced_tokens"] and w["seq"] < rc["observed_at_seq"]): mm.append("obscount")
    return {"attempts": [{k: r[k] for k in ("permission_at_execution","decision","system_status")} for r in reps],
            "effect_count": len(W), "classes": [c for c in ORDER if c in C], "status_mismatches": len(mm), "mm": mm}

def load(d):
    ev = [json.loads(l) for l in open(f"{d}/store_events.jsonl") if l.strip()]
    return ev, json.load(open(f"{d}/harness.json")), json.load(open(f"{d}/reports.json")), json.load(open(f"{d}/comparator.json"))
if __name__ == "__main__":
    for c in ["AT-1","AT-2","AT-3","AT-4","AT-4-DW"]:
        case = json.load(open(f"{PKG}/cases/{c}.json")); exp = json.load(open(f"{PKG}/expected/{c}.json"))["expected"]
        ev, h, reps, comp = load(f"{R}/{c}")
        mine = judge(case, ev, h, reps)
        got = {k: mine[k] for k in exp}; cg = {k: comp.get(k) for k in exp}
        print(c, "mine==expected", got == exp, "| mine==comparator", got == cg, mine["mm"])
    for d, c in [("controls/P7_broken_store/AT-4-DW","AT-4-DW"),("controls/P8_no_reconcile/AT-4","AT-4"),("controls/P8_no_reconcile/AT-4-DW","AT-4-DW"),("controls/P9_stale_permission/AT-2","AT-2")]:
        case = json.load(open(f"{PKG}/cases/{c}.json")); ev, h, reps, comp = load(f"{R}/{d}")
        m = judge(case, ev, h, reps); print(d, m.get("classes", m), m.get("mm"), "| comparator", comp.get("classes"), comp.get("store_defect"))
