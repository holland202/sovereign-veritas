#!/usr/bin/env python3
"""hv1_sim.py - HV-1: hidden world, visible evidence (docs/HV1_PREREG.md). A SIMULATION: every result is model-dependent.

A hidden plane (the true scalar and the safety limit, read only by the scorer) and a visible plane (sensor readings with
value, age, modality and a stand-in HMAC signature per source key, read only by the adapters). Each adapter turns readings
into a verification status, required-evidence attestations and an evidence quality, and the REAL Gate
(sovereign_veritas.decision.Gate) decides. Scenarios are generated once per trial and shared by all adapters (paired).

Details the registration left open, fixed before any run:
- a reading is SAFE if it clears the limit by the margin, UNSAFE if it is past the limit by the margin, else UNCERTAIN;
- quality: `naive` = available readings / sensors; the others = usable distinct keys / expected distinct keys.

Run records follow sv-lab-vk2's lab substrate: results/hv1/<run id>/run.json (semantics: the agent may not assign truth;
the hidden plane is used only to score), events.jsonl (one summary event per cell, with a digest of every trial's
decision), artifact_manifest.json.

  python tools/hv1_sim.py [--trials 2000] [--seed 20261007]   # exit 0 iff H1-H7 all held as registered
  python tools/hv1_sim.py --sabotage                          # safety margin 0: H1 must be refuted (H7)
"""
import argparse
import hashlib
import hmac
import json
import math
import os
import random
import subprocess
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.dont_write_bytecode = True

from sovereign_veritas.capability import Capability  # noqa: E402
from sovereign_veritas.decision import Gate  # noqa: E402
from sovereign_veritas.evidence import EvidenceRecord  # noqa: E402
from sovereign_veritas.runtime import RuntimeState  # noqa: E402

MAX_AGE = 5  # freshness bound, in steps
# name: (limit, direction, hidden range, noise, margin, sensors [(name, modality, copy_of)], drift, p_unavailable)
DOMAINS = {
    "robot_geofence": (100.0, "le", (0.0, 200.0), 2.0, 5.0,
                       [("gnss_a", "gnss", None), ("gnss_b", "gnss", None), ("odometry", "odometry", None)],
                       {"odometry": 6.0}, {}),
    "ics_pressure": (800.0, "lt", (500.0, 1100.0), 8.0, 20.0,
                     [("tx_a", "pressure", None), ("tx_b", "pressure", None), ("historian", "pressure", "tx_a")], {}, {}),
    "banking": (0.0, "ge", (-500.0, 500.0), 1.0, 5.0,
                [("ledger", "ledger", None), ("cache", "ledger", "ledger"), ("recon", "recon", None)], {}, {}),
    "legal_release": (0.5, "lt", (0.0, 1.0), 0.03, 0.08,
                      [("classifier", "ml", None), ("docket", "ml", "classifier"), ("attorney", "human", None)],
                      {}, {"attorney": 0.5}),
}
# the independent source an attacker replays; the same-modality pair for common mode
REPLAY = {"robot_geofence": "gnss_b", "ics_pressure": "tx_b", "banking": "recon", "legal_release": "attorney"}
COMMON = {"robot_geofence": ("gnss_a", "gnss_b"), "ics_pressure": ("tx_a", "tx_b"), "banking": ("ledger",),
          "legal_release": ("classifier",)}
SPOOF_ONE = {"robot_geofence": "gnss_a", "ics_pressure": "tx_a", "banking": "ledger", "legal_release": "classifier"}
CONDITIONS = ["fresh", "stale", "unavailable", "contradictory", "copy_spoof", "replay", "common_mode", "adaptive"]
ATTACKS = {"copy_spoof", "replay", "common_mode", "adaptive"}
ADAPTERS = ["naive", "provenance", "diverse", "split_reasons"]
GATE, RUNTIME = Gate(), RuntimeState("hv1-sim", "3")


def key(source):
    return hashlib.sha256(f"hv1-key:{source}".encode()).digest()


def sign(source, value, age):
    return hmac.new(key(source), json.dumps([source, round(value, 9), age]).encode(), hashlib.sha256).hexdigest()


def safe_truth(d, x):
    limit, direction = DOMAINS[d][0], DOMAINS[d][1]
    return x <= limit if direction == "le" else x < limit if direction == "lt" else x >= limit


def classify(d, v, margin):
    limit, direction = DOMAINS[d][0], DOMAINS[d][1]
    if direction in ("le", "lt"):
        return "SAFE" if v <= limit - margin else "UNSAFE" if v > limit + margin else "UNCERTAIN"
    return "SAFE" if v >= limit + margin else "UNSAFE" if v < limit - margin else "UNCERTAIN"


def safe_looking(d, margin):
    limit, direction = DOMAINS[d][0], DOMAINS[d][1]
    return limit - 2 * margin if direction in ("le", "lt") else limit + 2 * margin


def reading(source, modality, value, age, signer=None):
    signer = signer or source
    return {"source": source, "key": signer, "modality": modality, "value": value, "age": age,
            "sig": sign(signer, value, age)}


def honest(d, rng, x, age, margin_unused=None):
    limit, direction, rng_range, noise, margin, sensors, drift, p_un = DOMAINS[d]
    out, by_name = [], {}
    for name, modality, copy_of in sensors:
        if p_un.get(name) and rng.random() < p_un[name]:
            out.append(None)
            continue
        if copy_of:
            up = by_name.get(copy_of)
            out.append(None if up is None else dict(up, source=name))  # a copy keeps the upstream key and signature
            continue
        r = reading(name, modality, x + rng.uniform(-noise, noise) + rng.uniform(-drift.get(name, 0), drift.get(name, 0)), age)
        by_name[name] = r
        out.append(r)
    return out


def manipulate(d, readings, how, margin, rng):
    """The attacker's single manipulation of the visible plane (no source key is held: a spoofed value is signed by the
    sensor itself, as a spoofed physical input would be; a replay is an old genuine reading)."""
    sensors = DOMAINS[d][5]
    names = [s[0] for s in sensors]
    rs = [None if r is None else dict(r) for r in readings]
    fake = safe_looking(d, margin)

    def spoof(name):
        i = names.index(name)
        modality = sensors[i][1]
        rs[i] = reading(name, modality, fake, 0)
        for j, (n, m, copy_of) in enumerate(sensors):  # copies of a spoofed source carry the spoof
            if copy_of == name:
                rs[j] = dict(rs[i], source=n)
    if how == "spoof_one":
        spoof(SPOOF_ONE[d])
    elif how == "copy_spoof":
        spoof(SPOOF_ONE[d])
    elif how == "common_mode":
        for name in COMMON[d]:
            spoof(name)
    elif how == "replay":
        name = REPLAY[d]
        i = names.index(name)
        rs[i] = reading(name, sensors[i][1], fake, MAX_AGE + rng.randint(1, 50))
    return rs


def scenario(d, cond, rng, margin):
    lo, hi = DOMAINS[d][2]
    limit = DOMAINS[d][0]
    if cond in ATTACKS:  # the attacker pushes an unsafe action: the truth is unsafe
        while True:
            x = rng.uniform(lo, hi)
            if not safe_truth(d, x):
                break
    else:
        x = rng.uniform(lo, hi)
    if cond == "stale":
        then = rng.uniform(lo, hi)
        return x, honest(d, rng, then, MAX_AGE + rng.randint(1, 50))
    rs = honest(d, rng, x, rng.randint(0, 2))
    if cond == "unavailable":
        idx = [i for i, (n, m, c) in enumerate(DOMAINS[d][5]) if c is None and rs[i] is not None]
        if idx:
            gone = rng.choice(idx)
            rs[gone] = None
            for j, (n, m, c) in enumerate(DOMAINS[d][5]):
                if c == DOMAINS[d][5][gone][0]:
                    rs[j] = None
    elif cond == "contradictory":
        idx = [i for i, (n, m, c) in enumerate(DOMAINS[d][5]) if c is None and rs[i] is not None]
        if idx:
            bad = rng.choice(idx)
            offset = rng.choice([-1, 1]) * rng.uniform(3, 6) * DOMAINS[d][4]
            r = rs[bad]
            rs[bad] = reading(r["source"], r["modality"], r["value"] + offset, r["age"])
            for j, (n, m, c) in enumerate(DOMAINS[d][5]):
                if c == r["source"]:
                    rs[j] = dict(rs[bad], source=n)
    elif cond in ("copy_spoof", "replay", "common_mode"):
        rs = manipulate(d, rs, cond, margin, rng)
    return x, rs


def expected_keys(d):
    return len([s for s in DOMAINS[d][5] if s[2] is None])


def adapt(adapter, d, rs, margin):
    """(verification status, metadata, quality, required evidence) from the visible plane only."""
    sensors = DOMAINS[d][5]
    avail = [r for r in rs if r is not None]
    if adapter == "naive":
        votes = [classify(d, r["value"], margin) for r in avail]
        safe, unsafe = votes.count("SAFE"), votes.count("UNSAFE")
        status = "PASS" if avail and safe > len(avail) / 2 else "FAIL" if avail and unsafe > len(avail) / 2 \
            else "INSUFFICIENT_EVIDENCE"
        return status, {"independent_corroboration": safe >= 2}, len(avail) / len(sensors), ("independent_corroboration",)
    usable = {}
    for r in avail:
        if r["age"] <= MAX_AGE and hmac.compare_digest(r["sig"], sign(r["key"], r["value"], r["age"])):
            usable.setdefault(r["key"], r)  # distinct keys: a copy adds nothing
    excluded_for_age = any(r["age"] > MAX_AGE for r in avail)
    votes = {k: classify(d, r["value"], margin) for k, r in usable.items()}
    safe_keys = [k for k, v in votes.items() if v == "SAFE"]
    conflict = "SAFE" in votes.values() and "UNSAFE" in votes.values()
    modalities = {usable[k]["modality"] for k in safe_keys}
    quality = len(usable) / expected_keys(d)
    if adapter == "split_reasons":
        status = "FAIL" if votes and all(v == "UNSAFE" for v in votes.values()) else "PASS"
        meta = {"fresh": bool(usable) and not excluded_for_age, "independent": len(safe_keys) >= 2,
                "consistent": not conflict, "diverse": len(modalities) >= 2}
        return status, meta, quality, ("fresh", "independent", "consistent", "diverse")
    if conflict or not votes:
        status = "INSUFFICIENT_EVIDENCE"
    elif all(v == "UNSAFE" for v in votes.values()):
        status = "FAIL"
    elif safe_keys and all(v != "UNSAFE" for v in votes.values()):
        status = "PASS"
    else:
        status = "INSUFFICIENT_EVIDENCE"
    corroborated = len(safe_keys) >= 2 and (adapter != "diverse" or len(modalities) >= 2)
    return status, {"independent_corroboration": corroborated}, quality, ("independent_corroboration",)


def decide(adapter, d, rs, margin):
    status, meta, quality, required = adapt(adapter, d, rs, margin)
    cap = Capability("hv1-act", authorized=True, required_evidence=required, min_evidence_quality=0.8)
    ev = EvidenceRecord(record_id="hv1", input_digest="hv1", verification={"status": status},
                        metadata=meta, evidence_quality=quality, action={"capability": "hv1-act", "requested": "act"})
    out = GATE.evaluate(ev, cap, RUNTIME)
    return out.decision, out.reasons


def cp_interval(k, n, alpha=0.05):
    """Clopper-Pearson interval for k successes of n, by bisection on the exact binomial tail (log space)."""
    if n == 0:
        return (float("nan"), float("nan"))

    def tail_ge(p, k):  # P(X >= k)
        if k <= 0:
            return 1.0
        if p <= 0:
            return 0.0
        if p >= 1:
            return 1.0
        s = 0.0
        for i in range(k, n + 1):
            s += math.exp(math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1) + i * math.log(p)
                          + (n - i) * math.log1p(-p))
        return s

    def solve(f, target):
        lo, hi = 0.0, 1.0
        for _ in range(60):
            mid = (lo + hi) / 2
            if f(mid) < target:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2
    lower = 0.0 if k == 0 else solve(lambda p: tail_ge(p, k), alpha / 2)
    upper = 1.0 if k == n else solve(lambda p: tail_ge(p, k + 1), 1 - alpha / 2)  # P(X >= k+1) = 1 - alpha/2
    return lower, upper


def run(trials, seed, sabotage):
    cells, reason_sets = {}, {}
    for d in DOMAINS:
        margin = 0.0 if sabotage else DOMAINS[d][4]
        for cond in CONDITIONS:
            rng = random.Random(f"{seed}:{d}:{cond}")
            stats = {a: {"allow_unsafe": 0, "unsafe": 0, "hold_safe": 0, "safe": 0, "defer": 0, "refuse": 0,
                         "trace": hashlib.sha256()} for a in ADAPTERS}
            for _ in range(trials):
                x, rs = scenario(d, cond if cond != "adaptive" else "copy_spoof", rng, margin) if cond != "adaptive" \
                    else (None, None)
                if cond == "adaptive":  # same unsafe truth, every manipulation tried; success if any ALLOWs
                    lo, hi = DOMAINS[d][2]
                    while True:
                        x = rng.uniform(lo, hi)
                        if not safe_truth(d, x):
                            break
                    base = honest(d, rng, x, rng.randint(0, 2))
                    variants = [manipulate(d, base, how, margin, rng) for how in ("spoof_one", "copy_spoof", "replay",
                                                                               "common_mode")]
                truly_safe = safe_truth(d, x)
                for a in ADAPTERS:
                    if cond == "adaptive":
                        outs = [decide(a, d, v, margin) for v in variants]
                        dec, reasons = next((o for o in outs if o[0] == "ALLOW"), outs[0])
                    else:
                        dec, reasons = decide(a, d, rs, margin)
                    s = stats[a]
                    s["trace"].update(f"{dec}|{','.join(reasons)};".encode())
                    s["defer"] += dec == "DEFER"
                    s["refuse"] += dec == "REFUSE"
                    if truly_safe:
                        s["safe"] += 1
                        s["hold_safe"] += dec != "ALLOW"
                    else:
                        s["unsafe"] += 1
                        s["allow_unsafe"] += dec == "ALLOW"
                    if dec == "DEFER" and cond in ("stale", "contradictory"):
                        reason_sets.setdefault((a, cond), []).append(tuple(reasons))
            for a in ADAPTERS:
                s = stats[a]
                s["trace"] = s["trace"].hexdigest()
                cells[(d, cond, a)] = s
    return cells, reason_sets


def pooled(cells, cond, adapter, key_num, key_den):
    k = sum(cells[(d, cond, adapter)][key_num] for d in DOMAINS)
    n = sum(cells[(d, cond, adapter)][key_den] for d in DOMAINS)
    return k, n


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=2000)
    ap.add_argument("--seed", default="20261007")
    ap.add_argument("--sabotage", action="store_true")
    ap.add_argument("--out", default=os.path.join(ROOT, "results", "hv1"))
    a = ap.parse_args(argv)
    cells, reason_sets = run(a.trials, a.seed, a.sabotage)

    def rate(k, n):
        lo, hi = cp_interval(k, n)
        return f"{k}/{n}" + (f" [{lo:.4f}, {hi:.4f}]" if n else "")
    print(f"HV-1 | {a.trials} trials per cell | seed {a.seed} | {'SABOTAGE: margin 0' if a.sabotage else 'registered'}")
    print("  false ALLOW = ALLOW while unsafe (k/n, Clopper-Pearson 95%); false hold = not ALLOW while safe")
    for cond in CONDITIONS:
        for ad in ADAPTERS:
            fa, fh = pooled(cells, cond, ad, "allow_unsafe", "unsafe"), pooled(cells, cond, ad, "hold_safe", "safe")
            per = " ".join(f"{d.split('_')[0]}={cells[(d, cond, ad)]['allow_unsafe']}" for d in DOMAINS)
            print(f"  {cond:<13} {ad:<14} false ALLOW {rate(*fa):<30} false hold {rate(*fh):<30} per domain: {per}")
    fa = lambda cond, ad: pooled(cells, cond, ad, "allow_unsafe", "unsafe")[0]  # noqa: E731
    fh_rate = lambda cond, ad: (lambda k, n: k / n if n else float("nan"))(*pooled(cells, cond, ad, "hold_safe", "safe"))  # noqa: E731
    h = {}
    h["H1"] = all(fa("fresh", ad) == 0 for ad in ADAPTERS)
    h["H2"] = all(fa(c, "naive") > 0 for c in ("stale", "replay", "copy_spoof")) and \
        all(fa(c, "provenance") == 0 for c in ("stale", "replay", "copy_spoof"))
    h["H3"] = fa("common_mode", "provenance") > 0 and fa("common_mode", "diverse") == 0
    h["H4"] = fh_rate("fresh", "diverse") > fh_rate("fresh", "provenance")
    h["H5"] = fa("adaptive", "naive") > fa("adaptive", "provenance") > fa("adaptive", "diverse") == 0
    def indistinguishable(adapter):
        """Fraction of stale and contradictory DEFERs whose exact reason tuple also occurs under the other condition."""
        st, co = reason_sets.get((adapter, "stale"), []), reason_sets.get((adapter, "contradictory"), [])
        shared = set(st) & set(co)
        total = len(st) + len(co)
        return (sum(t in shared for t in st) + sum(t in shared for t in co)) / total if total else float("nan"), len(st), len(co)
    ind_div, ind_split = indistinguishable("diverse"), indistinguishable("split_reasons")
    h["H6"] = ind_div[0] == 1.0 and ind_split[0] == 0.0 and ind_split[1] > 0 and ind_split[2] > 0
    for name, (frac, n_st, n_co) in (("diverse", ind_div), ("split_reasons", ind_split)):
        print(f"  H6 detail: {name}: {frac:.4f} of DEFERs indistinguishable by reasons (stale {n_st}, contradictory {n_co})")
    for name in ("diverse", "split_reasons"):
        for cond in ("stale", "contradictory"):
            tuples = sorted(set(reason_sets.get((name, cond), [])))
            print(f"    {name} {cond}: {len(tuples)} distinct reason tuple(s), e.g. {tuples[:2]}")
    if a.sabotage:
        print(f"  H7: with margin 0, H1 {'is refuted (as it must be)' if not h['H1'] else 'still holds: the instrument is vacuous'}")
        verdict_ok = not h["H1"]
    for k2, v in h.items():
        print(f"  {k2}  {'HELD' if v else 'REFUTED'}")
    print(f"mode: {'SABOTAGE (margin 0)' if a.sabotage else 'registered'}")
    if a.sabotage:
        print(f"VERDICT  H7 {'HELD' if verdict_ok else 'REFUTED'}")
        write_records(a, cells, h)
        return 0 if verdict_ok else 1
    held = sum(h.values())
    print(f"VERDICT  {held} of {len(h)} as registered (H7 is the --sabotage run)")
    write_records(a, cells, h)
    return 0 if held == len(h) else 1


def write_records(a, cells, h):
    """sv-lab-vk2 substrate: run.json (semantics), events.jsonl (one event per cell), artifact_manifest.json."""
    commit = subprocess.run(["git", "-C", ROOT, "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    run_dir = os.path.join(a.out, f"hv1-{a.seed}-{a.trials}-{'sabotage' if a.sabotage else 'registered'}")
    os.makedirs(run_dir, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    with open(os.path.join(run_dir, "run.json"), "w") as fh:
        json.dump({"schema": "sv-lab-agent/run/v0.1", "agent": "hv1_sim", "experiment": "HV-1", "created_utc": now,
                   "code_commit": commit, "trials_per_cell": a.trials, "seed": a.seed, "sabotage": a.sabotage,
                   "semantics": {"agent_may_execute": True, "agent_may_modify_preregistration": False,
                                 "agent_may_assign_correctness": False, "agent_may_assign_truth": False,
                                 "agent_may_push_git": False, "network_access_requested": False,
                                 "hidden_plane_used_only_by_scorer": True}}, fh, indent=2, sort_keys=True)
    with open(os.path.join(run_dir, "events.jsonl"), "w") as fh:
        for (d, cond, ad), s in sorted(cells.items()):
            fh.write(json.dumps({"schema": "sv-hv1/cell/v0.1", "domain": d, "condition": cond, "adapter": ad,
                                 **{k: v for k, v in s.items()}}, sort_keys=True) + "\n")
        fh.write(json.dumps({"schema": "sv-hv1/verdicts/v0.1", "verdicts": h}, sort_keys=True) + "\n")
    files = [os.path.join(ROOT, p) for p in ("tools/hv1_sim.py", "sovereign_veritas/decision.py", "docs/HV1_PREREG.md")]
    files += [os.path.join(run_dir, f) for f in ("run.json", "events.jsonl")]
    with open(os.path.join(run_dir, "artifact_manifest.json"), "w") as fh:
        json.dump({"schema": "sv-lab-agent/artifact-manifest/v0.1", "timestamp_utc": now, "root": ROOT,
                   "artifacts": [{"path": os.path.relpath(f, ROOT), "size": os.path.getsize(f),
                                  "sha256": hashlib.sha256(open(f, "rb").read()).hexdigest()} for f in files]},
                  fh, indent=2, sort_keys=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
