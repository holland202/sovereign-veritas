#!/usr/bin/env python3
"""OBS-1 Amendment 1 probe (docs/OBS1_AMENDMENT1_PREREG.md): A1-A3. A4 is a run of tools/obs1_run.py --out ...

  python tools/obs1_amendment1.py      exit 0 only if A1-A3 hold as registered
"""
import copy
import importlib.util
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.dont_write_bytecode = True
import obs1_compare as new  # noqa: E402

PKG = os.path.join(ROOT, "docs", "external", "amos-tipton_2026-10-04_obs1-cases_v1.0")
RUN = os.path.join(ROOT, "results", "obs1", "run")
BASELINE = "0ba3aa7"


def load_old():
    src = subprocess.run(["git", "show", f"{BASELINE}:tools/obs1_compare.py"], cwd=ROOT, capture_output=True,
                         text=True, check=True).stdout
    path = os.path.join(tempfile.mkdtemp(), "obs1_compare_baseline.py")
    open(path, "w").write(src)
    spec = importlib.util.spec_from_file_location("obs1_compare_baseline", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def bundle(cid):
    d = os.path.join(RUN, cid)
    j = lambda n: json.load(open(os.path.join(d, n)))  # noqa: E731
    return (json.load(open(os.path.join(PKG, "cases", f"{cid}.json"))),
            json.load(open(os.path.join(PKG, "expected", f"{cid}.json"))),
            j("harness.json"), j("observer_before.json"), j("observer_after.json"), j("reports.json"))


def score(mod, cid, mutate=lambda a: a):
    case, exp, h, b, a, r = bundle(cid)
    res = mod.compare(case, h, b, mutate(copy.deepcopy(a)), r)
    ok, _ = mod.matches_expected(res, exp)
    fs = [v for v in res.get("invariant", []) if v.startswith("FINAL_STATE_INCONSISTENT")]
    return ok, res, fs


MUTATIONS = [("version 99", lambda a: {**a, "version": 99}), ("value 'off'", lambda a: {**a, "value": "off"}),
             ("writes 5", lambda a: {**a, "writes": 5})]


def main():
    old = load_old()
    v = {}
    ok0, res0, fs0 = score(new, "AT-1")
    print(f"A1  unmutated AT-1, amended comparator: match {ok0} final-state {fs0}")
    caught = []
    for name, m in MUTATIONS:
        ok, res, fs = score(new, "AT-1", m)
        caught.append(bool(fs) and res.get("store_defect") is True and res.get("classes") == [] and not ok)
        print(f"A1  {name:<12} amended:  match {ok} store_defect {res.get('store_defect')} classes {res.get('classes')} {fs}")
    v["A1"] = ok0 and not fs0 and all(caught)
    still = []
    for name, m in MUTATIONS:
        ok, res, _ = score(old, "AT-1", m)
        still.append(not res.get("invariant"))
        print(f"A2  {name:<12} {BASELINE}: match {ok} invariant {res.get('invariant')} classes {res.get('classes')}")
    v["A2"] = all(still)
    a3 = []
    for cid in ["AT-1", "AT-2", "AT-3", "AT-4", "AT-4-DW"]:
        ok, res, fs = score(new, cid)
        a3.append(ok and not fs)
        print(f"A3  {cid:<8} registered bundle, amended comparator: match {ok} final-state {fs}")
    v["A3"] = all(a3)
    print()
    for k, ok in v.items():
        print(f"  {k}  {'HELD' if ok else 'REFUTED'}")
    print("  A4  run: python tools/obs1_run.py --out results/obs1/rerun_amendment1")
    print(f"VERDICT  {sum(v.values())} of {len(v)} as registered")
    return 0 if all(v.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
