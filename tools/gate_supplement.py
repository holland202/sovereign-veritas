#!/usr/bin/env python3
"""gate_supplement.py - in-contract cases the frozen sv.gate/0 vectors never exercise, pinned by cross-implementation agreement.

A blind Rust implementation (ports/rust) found that 7 of 8 deliberately wrong variants of itself still pass all 4690 vectors:
the runtime words `high`, `critical`, `unsafe` and `low` appear in no vector, and ties-to-even rounding is pinned by one case.
This tool builds targeted cases that CONTRACT.md defines, from the all-healthy base vector, and runs every implementation it
is given. A case is written to contract/gate_vectors_supplement.jsonl only if ALL implementations agree; disagreements are
printed and the tool exits 1.

  python tools/gate_supplement.py --write [--cmd NAME=PROGRAM ...]   # (re)generate, needs agreement
  python tools/gate_supplement.py                                     # check kernel and verifier against the file

The expected outputs are a DERIVED oracle: agreement of implementations, all by the same vendor (one with a separate
context). They are not the frozen sv.gate/0 vectors and do not change its digest.
"""
import copy
import importlib.util
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "contract", "gate_vectors_supplement.jsonl")
sys.dont_write_bytecode = True


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def cases(base):
    out = []

    def add(cid, **paths):
        inp = copy.deepcopy(base)
        for path, value in paths.items():
            node = inp
            keys = path.split("__")
            for k in keys[:-1]:
                node = node[k]
            node[keys[-1]] = value
        out.append({"id": cid, "input": inp})

    words = {"thermal_status": ["normal", "cool", "warning", "high", "hot", "critical", "unsafe", "Normal", "warm", ""],
             "compute_budget": ["available", "constrained", "low", "exhausted", "LOW", "none"],
             "power_status": ["stable", "unsafe", "Stable", "ok"]}
    for field, ws in words.items():
        for w in ws:
            add(f"S:{field}={w or '<empty>'}", **{f"runtime__{field}": w})
    for st in ["PASS", "FAIL", "REFUTED", "INSUFFICIENT_EVIDENCE", "NOT_VERIFIED", "UNKNOWN", "pass", "Pass", "PASSED", ""]:
        add(f"S:status={st or '<empty>'}", record__verification={"status": st})
    for q in [0.5, 0.49995, 0.49985, 0.00005, 0.00015, 0.00025, 0.12345, 0.99995, 0.0, 1.0, 1, 0, -0.0]:
        add(f"S:quality={q!r}", record__evidence_quality=q)
    for floor in [0.5, 0.00025, 0.99995, 1, 0]:
        add(f"S:floor={floor!r},q=0.2", record__evidence_quality=0.2, capability__min_evidence_quality=floor)
    for steps in [1, 3, 4, 0, -1]:
        add(f"S:step_count={steps}", record__metadata__step_count=steps)
    return out


def run_all(cmds, cs):
    gc = _load("gate_contract")
    diff = _load("gate_differential")
    impls = {"kernel": diff.run_builtin(gc.kernel_gate(), cs), "verifier": diff.run_builtin(gc.verifier_gate(), cs)}
    for name, cmd in cmds.items():
        impls[name] = diff.run_cmd(cmd, cs)
    return impls


def main(argv):
    gc = _load("gate_contract")
    base = next(v for v in gc.read_vectors() if v["expect"]["decision"] == "ALLOW")
    if "--write" not in argv:
        with open(OUT, encoding="utf-8") as fh:
            vs = [json.loads(l) for l in fh if l.strip()]
        impls = run_all({}, vs)
        bad = [(v["id"], k, impls[k][i]) for i, v in enumerate(vs) for k in impls
               if list(impls[k][i]) != [v["expect"]["decision"], v["expect"]["reasons"]]]
        for b in bad[:10]:
            print("  MISMATCH", *b)
        print(f"gate_supplement | {len(vs)} cases | {', '.join(impls)} | VERDICT  "
              + ("CONFORMS" if not bad else f"{len(bad)} mismatches"))
        return 1 if bad else 0
    cmds, it = {}, iter(argv)
    for a in it:
        if a == "--cmd":
            name, _, prog = next(it).partition("=")
            cmds[name] = prog.split()
    cs = cases(base["input"])
    impls = run_all(cmds, cs)
    agreed, disagreed = [], []
    for i, c in enumerate(cs):
        row = {k: list(impls[k][i]) for k in impls}
        vals = list(row.values())
        if all(v == vals[0] for v in vals) and vals[0][0] in ("ALLOW", "DEFER", "REFUSE"):
            agreed.append({"id": c["id"], "input": c["input"], "expect": {"decision": vals[0][0], "reasons": vals[0][1]},
                           "agreed_by": sorted(impls)})
        else:
            disagreed.append((c["id"], row))
    for cid, row in disagreed:
        print("  DISAGREE", cid, row)
    with open(OUT, "w", encoding="utf-8") as fh:
        for v in agreed:
            fh.write(json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n")
    print(f"gate_supplement --write | {len(cs)} cases, {len(agreed)} agreed by {', '.join(impls)}, "
          f"{len(disagreed)} disagreed (not written)")
    return 1 if disagreed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
