#!/usr/bin/env python3
"""gate_differential.py - run several sv.gate/0 implementations on the same inputs and report every disagreement.

The 4690 vectors are regenerated from the kernel (gate_contract.py --write), so agreeing with them is a regression pin,
not an independent oracle, and an implementation can pass them while getting untested rules wrong (a blind Rust port
found 7 of 8 deliberately wrong variants of itself still conform). This tool goes past the vectors: seeded mutations of
vector inputs, plus any extra cases given, are sent to every implementation, and disagreements are classified:

  DISAGREE   all implementations decided, and the decisions or reasons differ: a contract or implementation defect
  DOMAIN     at least one implementation raised/refused to decide while another decided: the input is outside what
             CONTRACT.md defines (an underspecification), or one side is too lenient

  python tools/gate_differential.py [--cases N] [--seed S] [--extra FILE.jsonl] [--cmd NAME=PROGRAM ...] [--out FILE]
  exit 0 no DISAGREE | 1 at least one DISAGREE | 2 could not run

Built-in implementations: kernel (sovereign_veritas.decision.Gate) and verifier (tools/verify_package.py replay_gate).
Each --cmd adds a program speaking gate_contract.py's line protocol (e.g. ports/go, a blind re-implementation).
"""
import copy
import importlib.util
import json
import os
import random
import subprocess
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True


def _gc():
    spec = importlib.util.spec_from_file_location("gc_diff", os.path.join(ROOT, "tools", "gate_contract.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


VOCAB = ["normal", "cool", "warning", "high", "hot", "critical", "unsafe", "available", "constrained", "low",
         "exhausted", "stable", "Normal", "unknown", ""]
STATUSES = ["PASS", "FAIL", "REFUTED", "INSUFFICIENT_EVIDENCE", "NOT_VERIFIED", "UNKNOWN", "pass", "PASS "]
POOL = [None, True, False, 0, 1, -1, 2, 3, 0.0, -0.0, 0.5, 0.49999, 0.03125, 1.0, 2.0, 1e-05, 1e16, 1.7976931348623157e308,
        10 ** 20, 10 ** 400, -(10 ** 400), "", "x", "true", "false", "0.9", [], {}, ["read_sensor"], ["calibration"],
        {"status": "PASS"}, "read_sensor", "root-on", "root-off", "root-null", "root-str", "calibration"]
PATHS = [
    ("record", "input_digest"), ("record", "verification"), ("record", "verification", "status"),
    ("record", "action"), ("record", "action", "capability"), ("record", "action", "requested"),
    ("record", "metadata"), ("record", "metadata", "calibration"), ("record", "metadata", "evidence_quality"),
    ("record", "metadata", "step_count"), ("record", "evidence_quality"),
    ("capability",), ("capability", "name"), ("capability", "authorized"), ("capability", "required_evidence"),
    ("capability", "parent"), ("capability", "min_evidence_quality"), ("capability", "max_steps"),
    ("capability_registry",), ("runtime", "thermal_status"), ("runtime", "compute_budget"), ("runtime", "power_status"),
    ("policy",), ("policy", "allow_only"),
]


def _value_for(path, rng):
    last = path[-1]
    if last in ("thermal_status", "compute_budget", "power_status"):
        return rng.choice(VOCAB + POOL[:6])
    if last == "status":
        return rng.choice(STATUSES + POOL[:4])
    return copy.deepcopy(rng.choice(POOL))


def mutate(inp, rng):
    inp = copy.deepcopy(inp)
    applied = []
    for _ in range(rng.randint(1, 3)):
        path = rng.choice(PATHS)
        node = inp
        for key in path[:-1]:
            if not isinstance(node, dict) or not isinstance(node.get(key), dict):
                node = None
                break
            node = node[key]
        if node is None:
            continue
        if rng.random() < 0.15 and path[-1] in node:
            del node[path[-1]]
            applied.append(".".join(path) + "=<deleted>")
        else:
            node[path[-1]] = _value_for(path, rng)
            applied.append(".".join(path) + "=" + json.dumps(node[path[-1]])[:40])
    return inp, applied


def run_builtin(decide, cases):
    out = []
    for c in cases:
        try:
            d, reasons = decide(copy.deepcopy(c["input"]))
            out.append((d, list(reasons)))
        except Exception as exc:  # outside the domain this implementation accepts
            out.append((f"RAISE:{type(exc).__name__}", []))
    return out


def _run_cmd_batch(cmd, cases):
    payload = "".join(json.dumps({"id": c["id"], "input": c["input"]}, sort_keys=True) + "\n" for c in cases)
    p = subprocess.run(cmd, input=payload, capture_output=True, text=True, timeout=600)
    lines = [l for l in p.stdout.splitlines() if l.strip()]
    if p.returncode != 0 or len(lines) != len(cases):
        return None
    return [(o["decision"], o["reasons"]) for o in map(json.loads, lines)]


def run_cmd(cmd, cases, chunk=200):
    out = []
    for i in range(0, len(cases), chunk):
        part = cases[i:i + chunk]
        got = _run_cmd_batch(cmd, part)
        if got is None:  # someone in this chunk was refused: fall back to one process per case
            got = [(_run_cmd_batch(cmd, [c]) or [("REFUSED_INPUT", [])])[0] for c in part]
        out.extend(got)
    return out


def classify(row):
    decided = [d for d in row if d[0] in ("ALLOW", "DEFER", "REFUSE")]
    if len(decided) == len(row):
        return None if all(d == row[0] for d in row) else "DISAGREE"
    if decided:
        return "DOMAIN"
    return None  # nobody decided: consistent refusal of the input


def main(argv):
    n, seed, extra, out, cmds = 3000, 20261007, None, None, {}
    it = iter(argv)
    for a in it:
        if a == "--cases":
            n = int(next(it))
        elif a == "--seed":
            seed = int(next(it))
        elif a == "--extra":
            extra = next(it)
        elif a == "--out":
            out = next(it)
        elif a == "--cmd":
            name, _, prog = next(it).partition("=")
            cmds[name] = prog.split()
        else:
            print(__doc__)
            return 2
    gc = _gc()
    vectors = gc.read_vectors()
    rng = random.Random(seed)
    cases = []
    for i in range(n):
        base = rng.choice(vectors)
        inp, applied = mutate(base["input"], rng)
        cases.append({"id": f"F{i:06d}", "input": inp, "mutations": applied, "base": base["id"]})
    if extra:
        with open(extra, encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    c = json.loads(line)
                    cases.append({"id": c["id"], "input": c["input"], "mutations": ["<extra>"], "base": None})
    impls = {"kernel": run_builtin(gc.kernel_gate(), cases), "verifier": run_builtin(gc.verifier_gate(), cases)}
    for name, cmd in cmds.items():
        try:
            impls[name] = run_cmd(cmd, cases)
        except (OSError, subprocess.SubprocessError) as exc:
            print(f"COULD NOT RUN: {name}: {exc}")
            return 2
    names = list(impls)
    counts, examples = Counter(), {}
    records = []
    for i, c in enumerate(cases):
        row = [impls[k][i] for k in names]
        kind = classify(row)
        if kind:
            # group by which implementations differ and on what, so one root cause is one group
            sig = (kind, tuple(sorted({k: (r[0] if r[0] in ("ALLOW", "DEFER", "REFUSE") else "NO-DECISION")
                                       for k, r in zip(names, row)}.items())))
            counts[sig] += 1
            examples.setdefault(sig, (c, row))
            records.append({"id": c["id"], "kind": kind, "mutations": c["mutations"],
                            "results": {k: list(r) for k, r in zip(names, row)}, "input": c["input"]})
    disagree = sum(v for (k, _), v in counts.items() if k == "DISAGREE")
    domain = sum(v for (k, _), v in counts.items() if k == "DOMAIN")
    print(f"gate_differential | implementations: {', '.join(names)} | {len(cases)} cases (seed {seed})")
    for sig, v in counts.most_common():
        c, row = examples[sig]
        print(f"  {sig[0]:<8} x{v:<5} {dict(sig[1])}")
        print(f"           e.g. {c['id']} {c['mutations']}")
        for k, r in zip(names, row):
            print(f"             {k:<9} {r[0]} {r[1][:2]}")
    print(f"VERDICT  {disagree} DISAGREE, {domain} DOMAIN, {len(cases) - disagree - domain} agree")
    if out:
        with open(out, "w", encoding="utf-8") as fh:
            for r in records:
                fh.write(json.dumps(r, sort_keys=True, default=str) + "\n")
    return 1 if disagree else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
