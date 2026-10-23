#!/usr/bin/env python3
"""BT-001: score the blue arm's results JSONL against the registered predictions (docs/BT001_PREREG.md).

    python tools/bt001_score.py RESULTS.jsonl            # verdicts + the survivor list for triage
Stdlib only. Mutants textually identical to the original (equal_to_base) are excluded from every rate, as registered.
"""
import json
import sys
from collections import OrderedDict


def main(path):
    recs = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    controls = [r for r in recs if "control" in r]
    muts = [r for r in recs if "control" not in r]
    scored = [r for r in muts if not r["equal_to_base"]]
    print(f"records {len(recs)}: controls {len(controls)}, mutants {len(muts)} "
          f"({len(muts) - len(scored)} textually identical to the original, left out of rates)")
    for c in controls:
        print(f"  {c['id']:28} expected {c['expected']:4} T {c['T']['verdict']} C {c['C']['verdict']} "
              f"as_expected={c['as_expected']}")

    by = OrderedDict()
    for r in scored:
        by.setdefault(r["target"], []).append(r)
    print("\nper target           mutants  T-killed   T-rate  C-killed   C-rate  T-collection-errors")
    for t, rs in by.items():
        tk = sum(r["T"]["verdict"] == "FAIL" for r in rs)
        ck = sum(r["C"]["verdict"] == "FAIL" for r in rs)
        coll = sum(r["T"]["rc"] in (2, 3, 4) for r in rs)
        print(f"  {t.split('/')[-1]:18} {len(rs):7}  {tk:8}  {tk / len(rs):7.1%}  {ck:8}  {ck / len(rs):7.1%}  {coll}")
    allk = sum(r["T"]["verdict"] == "FAIL" for r in scored)
    print(f"  {'ALL':18} {len(scored):7}  {allk:8}  {allk / len(scored):7.1%}")

    dec = by.get("sovereign_veritas/decision.py", [])
    d_t = sum(r["T"]["verdict"] == "FAIL" for r in dec) / len(dec)
    d_c = sum(r["C"]["verdict"] == "FAIL" for r in dec) / len(dec)
    c_not_t = [r["id"] for r in dec if r["C"]["verdict"] == "FAIL" and r["T"]["verdict"] == "PASS"]
    rp = [r for r in scored if r["op"] == "raise-to-pass"
          and r["target"] in ("sovereign_veritas/idempotency.py", "sovereign_veritas/workflow.py")]
    rp_surv = [r["id"] for r in rp if r["T"]["verdict"] == "PASS"]
    timeouts = [r["id"] for r in scored if r["T"]["rc"] == "timeout" or r["C"]["rc"] == "timeout"]

    v = OrderedDict()
    v["BT-P1"] = all(c["as_expected"] for c in controls)
    v["BT-P2"] = d_t >= 0.90
    v["BT-P3"] = d_c >= 0.80
    v["BT-P4"] = not c_not_t
    v["BT-P5"] = allk / len(scored) >= 0.80
    v["BT-P6"] = len(rp) == 10 and not rp_surv
    print(f"\ndecision.py: T {d_t:.1%}, C {d_c:.1%}; killed by C but not T: {c_not_t or 'none'}")
    print(f"raise->pass in idempotency/workflow: {len(rp)} mutants, T survivors: {rp_surv or 'none'}")
    print(f"timeouts: {timeouts or 'none'}")
    for k, ok in v.items():
        print(f"  {k}  {'HELD' if ok else 'REFUTED'}")
    print("  BT-P7  needs the survivor triage below (by reading each one)")

    surv = [r for r in scored if r["T"]["verdict"] == "PASS"]
    print(f"\nT survivors ({len(surv)}), for triage:")
    for r in surv:
        print(f"  {r['id']:42} {r['op']:14} line {r['line']}  C={r['C']['verdict']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
