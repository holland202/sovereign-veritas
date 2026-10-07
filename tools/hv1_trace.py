#!/usr/bin/env python3
"""hv1_trace.py - observe the trials behind HV-1's outcomes (docs/HV1_RESULTS.md). Written AFTER the registered run.

It re-runs tools/hv1_sim.py's registered run unchanged, watching it through wrappers that record the truth and every
adapter's inputs without consuming randomness. It then checks that every cell's decision digest equals the registered
events.jsonl, so what it prints is the registered run, not a re-creation. It prints:
- each sensor's worst-case honest error against the domain margin;
- every false ALLOW by provenance, diverse and split_reasons (ICS common mode and adaptive excepted: both keys spoofed,
  summarized), and naive's under replay and robot copy_spoof, with every reading;
- how many of them involved an honest reading classified SAFE while the truth is unsafe, and a counted UNCERTAIN reading;
- false holds under `fresh` by domain (the mechanism behind H4).

  python tools/hv1_trace.py   # exit 0 iff the digests match the registered run
"""
import json
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.dont_write_bytecode = True
import hv1_sim as H  # noqa: E402

REGISTERED = os.path.join(ROOT, "results", "hv1", "hv1-20261007-2000-registered", "events.jsonl")
CUR = {"cell": None, "trial": -1, "in_scenario": False, "x": None, "x_h": None}
CALLS = []  # (domain, condition, trial, adapter, readings, (status, meta, quality), decision)


class _Random(random.Random):
    def __init__(self, s):
        CUR["cell"] = s.split(":", 1)[1].split(":")  # "seed:domain:condition"
        CUR["trial"] = -1
        super().__init__(s)


class _RandomModule:
    Random = _Random


_scenario, _honest, _decide, _adapt = H.scenario, H.honest, H.decide, H.adapt


def scenario(d, cond, rng, margin):
    CUR["in_scenario"], CUR["trial"] = True, CUR["trial"] + 1
    try:
        out = _scenario(d, cond, rng, margin)
    finally:
        CUR["in_scenario"] = False
    CUR["x"] = out[0]
    return out


def honest(d, rng, x, age, margin_unused=None):
    if not CUR["in_scenario"]:  # only the adaptive branch calls honest directly, once per trial, with the truth
        CUR["trial"] += 1
        CUR["x_h"] = x
    return _honest(d, rng, x, age, margin_unused)


def decide(adapter, d, rs, margin):
    out = _decide(adapter, d, rs, margin)
    domain, cond = CUR["cell"]
    x = CUR["x_h"] if cond == "adaptive" else CUR["x"]
    CALLS.append((domain, cond, CUR["trial"], adapter, x, rs, _adapt(adapter, d, rs, margin), out[0], margin))
    return out


H.random, H.scenario, H.honest, H.decide = _RandomModule, scenario, honest, decide


def describe(d, x, r, margin):
    if r is None:
        return "absent"
    cls = H.classify(d, r["value"], margin)
    if r["age"] > H.MAX_AGE:
        kind = f"replayed (age {r['age']})"
    elif r["value"] == H.safe_looking(d, margin) and r["age"] == 0:
        kind = "spoofed"
    else:
        kind = f"honest, error {r['value'] - x:+.3f}"
    copy = f" copy of {r['key']}" if r["key"] != r["source"] else ""
    return f"{r['source']}{copy} [{r['modality']}] {r['value']:.3f} -> {cls} ({kind})"


def main():
    cells, _ = H.run(2000, "20261007", False)
    registered = {}
    with open(REGISTERED) as fh:
        for line in fh:
            e = json.loads(line)
            if e.get("schema") == "sv-hv1/cell/v0.1":
                registered[(e["domain"], e["condition"], e["adapter"])] = e
    same = sum(cells[k]["trace"] == registered[k]["trace"] and cells[k]["allow_unsafe"] == registered[k]["allow_unsafe"]
               for k in registered)
    print(f"HV-1 trace | registered run re-observed: {same} of {len(registered)} cells have the registered digest")
    print("worst-case honest error per sensor (noise + drift) against the margin:")
    for d, (limit, _, _, noise, margin, sensors, drift, _) in H.DOMAINS.items():
        for name, modality, copy_of in sensors:
            if copy_of is None:
                worst = noise + drift.get(name, 0.0)
                print(f"  {d:<15} {name:<10} {worst:>7.3f}  margin {margin:<6g} {'EXCEEDS the margin' if worst > margin else 'below'}")

    # group decide calls into trials: (domain, condition, trial) -> adapter -> [calls]
    trials = {}
    for c in CALLS:
        trials.setdefault(c[:3], {}).setdefault(c[3], []).append(c)
    traced, honest_safe, uncertain, both = 0, 0, 0, 0
    recount = {}
    print("false ALLOWs traced (truth unsafe):")
    for (d, cond, t), per in sorted(trials.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2])):
        for adapter, calls in per.items():
            final = next((c for c in calls if c[7] == "ALLOW"), calls[0])
            x, margin = final[4], final[8]
            if final[7] != "ALLOW" or H.safe_truth(d, x):
                continue
            recount[(d, cond, adapter)] = recount.get((d, cond, adapter), 0) + 1
            both_spoofed = cond in ("common_mode", "adaptive") and d == "ics_pressure"
            show = (adapter != "naive" and not both_spoofed) or (adapter == "naive" and (
                cond == "replay" or (cond == "copy_spoof" and d == "robot_geofence")))
            if not show:
                continue
            traced += 1
            rs = final[5]
            hs = any(r is not None and r["age"] <= H.MAX_AGE and r["value"] != H.safe_looking(d, margin)
                     and H.classify(d, r["value"], margin) == "SAFE" for r in rs)
            un = any(r is not None and r["age"] <= H.MAX_AGE and H.classify(d, r["value"], margin) == "UNCERTAIN"
                     for r in rs)
            honest_safe += hs
            uncertain += un
            both += hs and un
            status, meta, quality = final[6][0], final[6][1], final[6][2]
            print(f"  {d} {cond} trial {t} {adapter}: truth {x:.3f} (limit {H.DOMAINS[d][0]:g}, margin {margin:g})")
            for r in rs:
                print(f"      {describe(d, x, r, margin)}")
            print(f"      adapter: status {status}, attestations {meta}, quality {quality:.4f} -> ALLOW")
    print(f"traced false ALLOWs: {traced}; with an honest reading classified SAFE: {honest_safe}; "
          f"with a fresh UNCERTAIN reading: {uncertain}; with both: {both}")
    mismatch = [k for k, v in recount.items() if v != cells[k]["allow_unsafe"]]
    mismatch += [k for k, s in cells.items() if s["allow_unsafe"] and k not in recount]
    print(f"recount of false ALLOWs from the trace against the run's own counts: {'equal' if not mismatch else mismatch}")
    # legal copy_spoof: does a dissenting attorney reading change naive's decision? (it raises naive's quality)
    split = {}
    for (d, cond, t), per in trials.items():
        if d != "legal_release" or cond != "copy_spoof":
            continue
        for adapter, calls in per.items():
            c = calls[0]
            att = c[5][2]
            present = att is not None
            row = split.setdefault((adapter, present), {"n": 0, "allow": 0, "classes": {}})
            row["n"] += 1
            row["allow"] += c[7] == "ALLOW"
            if c[7] == "ALLOW" and present:
                cls = H.classify(d, att["value"], c[8])
                row["classes"][cls] = row["classes"].get(cls, 0) + 1
    print("legal_release copy_spoof (truth unsafe): ALLOW by whether the attorney reading is present:")
    for adapter in H.ADAPTERS:
        p, q = split[(adapter, True)], split[(adapter, False)]
        print(f"  {adapter:<14} present: {p['allow']}/{p['n']} ALLOW (attorney said {p['classes'] or '-'})   "
              f"absent: {q['allow']}/{q['n']} ALLOW")
    print("false hold under fresh, by domain (not ALLOW while safe):")
    for d in H.DOMAINS:
        row = "  ".join(f"{a} {cells[(d, 'fresh', a)]['hold_safe']}/{cells[(d, 'fresh', a)]['safe']}" for a in H.ADAPTERS)
        print(f"  {d:<15} {row}")
    return 0 if same == len(registered) and not mismatch else 1


if __name__ == "__main__":
    sys.exit(main())
