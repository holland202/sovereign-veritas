#!/usr/bin/env python3
"""DIFF-001: three-way differential test of sv.gate/0 implementations on generated inputs.

Implementations compared (each called in-process on a deep copy of the same input):
  K = kernel Gate        (tools/gate_contract.kernel_gate)
  V = package verifier   (tools/gate_contract.verifier_gate -> tools/verify_package.replay_gate)
  I = independent port   (ports/python_independent/independent_gate.decide, SV PR #86)

Inputs: case i is generated deterministically from (SEED, i): a published contract vector chosen at random,
then 1-6 random mutations that keep every member inside the contract's declared types (CONTRACT.md "Input"),
plus registry keys equal to entry names. Outcome per implementation: (decision, reasons) or ("ERROR", type).
A DISAGREEMENT is any case where the three outcomes are not identical. The first MAX_SAVED disagreements are
saved in full; all are counted by pair and by a short signature.

Usage:
  diff_fuzz.py --worker W --workers N --until 2026-10-22T20:30:00Z --out DIR      # the registered run
  diff_fuzz.py --mutant NAME --cases 100000 --out DIR                             # anti-vacuity control
  diff_fuzz.py --replay INDEX                                                     # re-generate one case
"""
import argparse, copy, importlib.util, json, os, random, sys, time
from collections import Counter
from datetime import datetime, timezone

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SEED = 20261022
MAX_SAVED = 1000


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


GC = load("gate_contract", os.path.join(ROOT, "tools", "gate_contract.py"))
IND_PATH = os.path.join(ROOT, "ports", "python_independent", "independent_gate.py")
VECTORS = [json.loads(l) for l in open(os.path.join(ROOT, "contract", "gate_vectors.jsonl"), encoding="utf-8") if l.strip()]

STATUS = ["PASS", "FAIL", "REFUTED", "INSUFFICIENT_EVIDENCE", "NOT_VERIFIED", "UNKNOWN", "pass", "", "PASSED", None]
THERMAL = ["normal", "cool", "warning", "high", "hot", "critical", "unsafe", "Normal", "", "melting"]
BUDGET = ["available", "constrained", "low", "exhausted", "AVAILABLE", "", "infinite"]
POWER = ["stable", "unsafe", "Stable", "", "brownout"]
TRUTHY = [True, False, None, "true", "false", "", 1, 0, "x", []]
NUMS = [0, 1, 0.0, 1.0, -0.0, 0.5, 0.49999, 0.50001, 0.99999, 1.00001, -0.1, 2, 1e-9, 1e300, 10 ** 400, 3, 0.1 + 0.2]
INTS = [0, 1, 2, 3, 5, -1, 10 ** 20]
NAMES = ["read_sensor", "write_actuator", "root-on", "root-off", "root-str", "root-null", "ghost", "", "Read_Sensor"]
EVID = ["calibration", "operator_ok", "sensor_selftest", "", "Calibration"]


def mutate(rng, inp):
    rec, cap, reg, rt, pol = inp["record"], inp["capability"], inp["capability_registry"], inp["runtime"], inp["policy"]
    k = rng.randrange(19)
    if k == 0:
        rec["input_digest"] = rng.choice(["sha256:abc", "", None, "x", 0, 1])
    elif k == 1:
        rec["verification"] = None if rng.random() < 0.15 else {"status": rng.choice(STATUS)}
    elif k == 2:
        rec["evidence_quality"] = rng.choice(NUMS + [None])
    elif k == 3:
        rec["metadata"]["evidence_quality"] = rng.choice(NUMS + [None])
    elif k == 4:
        rec["metadata"]["step_count"] = rng.choice(INTS + [None, True, 1.5])
    elif k == 5:
        rec["metadata"][rng.choice(EVID)] = rng.choice(TRUTHY)
    elif k == 6:
        rec["action"] = None if rng.random() < 0.15 else {"capability": rng.choice(NAMES + [None]), "requested": rng.choice(NAMES + [None])}
    elif k == 7:
        inp["capability"] = None if rng.random() < 0.1 else (cap or {"name": "read_sensor", "authorized": True, "required_evidence": [], "parent": None, "min_evidence_quality": None, "max_steps": None})
    elif k == 8 and cap is not None:
        cap["authorized"] = rng.choice(TRUTHY)
    elif k == 9 and cap is not None:
        cap["parent"] = rng.choice(NAMES + [None, None])
    elif k == 10 and cap is not None:
        cap["min_evidence_quality"] = rng.choice(NUMS + [None])
    elif k == 11 and cap is not None:
        cap["max_steps"] = rng.choice(INTS + [None])
    elif k == 12 and cap is not None:
        cap["required_evidence"] = rng.sample(EVID, rng.randrange(0, 3))
    elif k == 13 and cap is not None:
        cap["name"] = rng.choice(NAMES)
    elif k == 14:
        if rng.random() < 0.15:
            inp["capability_registry"] = None
        else:
            reg = inp["capability_registry"] = reg or {}
            name = rng.choice(NAMES)
            reg[name] = None if rng.random() < 0.2 else {"name": name, "authorized": rng.choice(TRUTHY), "required_evidence": [],
                                                       "parent": None, "min_evidence_quality": None, "max_steps": None}
    elif k == 15:
        rt["thermal_status"] = rng.choice(THERMAL)
    elif k == 16:
        rt["compute_budget"] = rng.choice(BUDGET)
    elif k == 17:
        rt["power_status"] = rng.choice(POWER)
    elif k == 18:
        inp["policy"] = None if rng.random() < 0.2 else {"allow_only": rng.sample(NAMES, rng.randrange(0, 4)) if rng.random() < 0.9 else None}


def case(i):
    rng = random.Random(SEED * 1_000_003 + i)
    inp = copy.deepcopy(rng.choice(VECTORS)["input"])
    for _ in range(rng.randint(1, 6)):
        mutate(rng, inp)
    return inp


def outcome(fn, inp):
    try:
        d, reasons = fn(copy.deepcopy(inp))
        return [d, list(reasons)]
    except Exception as exc:  # recorded, compared like any other outcome
        return ["ERROR", type(exc).__name__]


MUTANTS = {
    # anti-vacuity: each makes the independent port wrong in one small, plausible way
    "steps-ge": ("elif steps > maximum:", "elif steps >= maximum:"),
    "insufficient-is-pass": ('        reasons.append("verification_insufficient_evidence")', '        pass'),
}


def implementations(mutant=None):
    src = open(IND_PATH, encoding="utf-8").read()
    if mutant:
        old, new = MUTANTS[mutant]
        assert src.count(old) == 1, mutant
        src = src.replace(old, new)
    ns = {"__name__": "independent_gate_under_test"}
    exec(compile(src, IND_PATH, "exec"), ns)
    return {"K": GC.kernel_gate(), "V": GC.verifier_gate(), "I": ns["decide"]}


def signature(outs):
    return " | ".join(f"{k}:{o[0]}:{(o[1][0] if o[1] and isinstance(o[1], list) else o[1]) if o[0] != 'ERROR' else o[1]}" for k, o in outs.items())


def run(indices, impls, out_dir, label, deadline=None):
    os.makedirs(out_dir, exist_ok=True)
    pairs, sigs, decisions, saved, n = Counter(), Counter(), Counter(), 0, 0
    first_t = time.time()
    dis_path = os.path.join(out_dir, f"{label}.disagreements.jsonl")
    with open(dis_path, "w", encoding="utf-8") as dis:
        for i in indices:
            if deadline and time.time() >= deadline:
                break
            inp = case(i)
            outs = {k: outcome(f, inp) for k, f in impls.items()}
            n += 1
            decisions[outs["K"][0]] += 1
            if not (outs["K"] == outs["V"] == outs["I"]):
                for a, b in (("K", "V"), ("K", "I"), ("V", "I")):
                    if outs[a] != outs[b]:
                        pairs[a + b] += 1
                sigs[signature(outs)] += 1
                if saved < MAX_SAVED:
                    dis.write(json.dumps({"index": i, "input": inp, "outcomes": outs}, sort_keys=True) + "\n")
                    saved += 1
            if n % 20000 == 0:
                write_summary(out_dir, label, n, pairs, sigs, decisions, first_t, final=False)
    return write_summary(out_dir, label, n, pairs, sigs, decisions, first_t, final=True)


def write_summary(out_dir, label, n, pairs, sigs, decisions, t0, final):
    s = {"label": label, "final": final, "cases": n, "seconds": round(time.time() - t0, 1),
         "utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
         "kernel_decisions": dict(decisions), "disagreeing_pairs": dict(pairs),
         "disagreement_cases": sum(sigs.values()), "top_signatures": sigs.most_common(25),
         "python": sys.version.split()[0]}
    tmp = os.path.join(out_dir, f"{label}.summary.json.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(s, fh, indent=1, sort_keys=True)
    os.replace(tmp, os.path.join(out_dir, f"{label}.summary.json"))
    return s


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--worker", type=int, default=0)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--until", help="UTC deadline, e.g. 2026-10-22T20:30:00Z")
    ap.add_argument("--cases", type=int, help="fixed number of cases instead of a deadline")
    ap.add_argument("--mutant", choices=sorted(MUTANTS))
    ap.add_argument("--out", default="diff001_out")
    ap.add_argument("--replay", type=int)
    a = ap.parse_args(argv)
    if a.replay is not None:
        inp = case(a.replay)
        print(json.dumps({"index": a.replay, "input": inp,
                          "outcomes": {k: outcome(f, inp) for k, f in implementations().items()}}, indent=1, sort_keys=True))
        return 0
    impls = implementations(a.mutant)
    deadline = datetime.fromisoformat(a.until.replace("Z", "+00:00")).timestamp() if a.until else None
    stop = a.cases if a.cases else 10 ** 12
    label = (f"mutant-{a.mutant}" if a.mutant else f"worker{a.worker}")
    s = run(range(a.worker, stop, a.workers), impls, a.out, label, deadline)
    print(json.dumps({k: s[k] for k in ("label", "cases", "seconds", "disagreement_cases", "disagreeing_pairs", "kernel_decisions")}, sort_keys=True))
    if a.mutant:
        return 0 if s["disagreeing_pairs"].get("KI", 0) > 0 else 1   # a mutant that is NOT caught means a vacuous harness
    return 0


if __name__ == "__main__":
    sys.exit(main())
