import json, copy, sys, tempfile
sys.path.insert(0, "/root/sv/tools"); sys.dont_write_bytecode = True
from obs1_compare import compare
from check import judge, load, PKG, R
case = json.load(open(f"{PKG}/cases/AT-4-DW.json"))
ev0, h0, rep0, _ = load(f"{R}/AT-4-DW"); t1, t2 = h0["tokens"]
def snap(ev): return {"value": [e for e in ev if e["event"]=="write"][-1]["value"] if any(e["event"]=="write" for e in ev) else "off",
                      "version": 0, "writes": sum(e["event"]=="write" for e in ev), "events": ev}
before = {"value":"off","version":0,"writes":0,"events":[]}
def reseq(ev): return [dict(e, seq=i) for i, e in enumerate(ev, 1)]
F,RJ,RD,WR = ev0
muts = {
 "read before fence": (reseq([RD, F, RJ, WR]), h0, rep0),
 "read unavailable": (reseq([F, RJ, dict(RD, result="unavailable"), WR]), h0, rep0),
 "read by attempt-1 token": (reseq([F, RJ, dict(RD, attempt_token=t1), WR]), h0, rep0),
 "fence called by unknown token": (reseq([dict(F, attempt_token="zz"), RJ, RD, WR]), h0, rep0),
 "fence perm off for t2": (ev0, dict(h0, in_force={**h0["in_force"], t2: dict(h0["in_force"][t2], fence=False)}), rep0),
 "write perm off for t2": (ev0, dict(h0, in_force={**h0["in_force"], t2: dict(h0["in_force"][t2], write=False)}), rep0),
 "no fence at all": (reseq([RD, WR]), dict(h0, release=None), rep0),
}
r_bad = copy.deepcopy(rep0); r_bad[1]["reconciliation"]["observed_at_seq"] = 2
r_bad2 = copy.deepcopy(rep0); r_bad2[1]["reconciliation"]["observed_writes_by_fenced"] = 1
r_bad3 = copy.deepcopy(rep0); r_bad3[1]["reconciliation"]["fenced_tokens"] = ["nope"]
r_bad4 = copy.deepcopy(rep0); r_bad4[1]["system_status"] = "HELD"
muts.update({"claim observed_at_seq wrong": (ev0,h0,r_bad), "claim count wrong": (ev0,h0,r_bad2),
             "claim fenced token never fenced": (ev0,h0,r_bad3), "HELD but wrote": (ev0,h0,r_bad4)})
for k,(ev,h,rp) in muts.items():
    c = compare(case, h, before, snap(ev), rp); m = judge(case, ev, h, rp)
    print(f"{k:34} comparator {c.get('classes')} mm={c.get('status_mismatches')} inv={c.get('invariant')} | mine {m.get('classes', m)} mm={m.get('status_mismatches')}")
# fence-claim limit for a non-writing attempt: fence placed AFTER the attempt's report (by a later attempt) still accepted
