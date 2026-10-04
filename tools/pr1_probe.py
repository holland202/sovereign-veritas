"""PR-1 probe (registration: docs/PR1_PREREG.md, committed 8d16f45 before this file existed).

Does changing only an evidence-state tag change the Gate's decision?

  python tools/pr1_probe.py              exit 0 only if every registered prediction holds
  python tools/pr1_probe.py --sabotage   the replay is swapped for one that DEFERs on any DEFAULTED tag; must exit 1
"""
from __future__ import annotations

import copy
import inspect
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

from test_thermal_policy import reseal, tree, vp  # noqa: E402  (the test suite's own helpers)

from sovereign_veritas.decision import Gate  # noqa: E402

FIELDS = ("thermal_status", "compute_budget", "power_status")
STATES = ("MEASURED", "OPERATOR", "DERIVED", "INFERRED", "ABSENT", "DEFAULTED", "NEVER_WIRED", "UNVERIFIED")
SABOTAGE = "--sabotage" in sys.argv


def base_package(tmp):
    zones = os.path.join(tmp, "z")
    tree(__import__("pathlib").Path(zones))
    home = os.path.join(tmp, "home")
    os.makedirs(home, exist_ok=True)
    out = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "make_package.py"), "--rounds", "10",
                          "--thermal-root", zones, "--thermal-status", "normal", "--compute-budget", "available",
                          "--power-status", "stable"], capture_output=True, text=True,
                         env=dict(os.environ, HOME=home), check=True).stdout
    path = next(line.split()[1] for line in out.splitlines() if line.startswith("package "))
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def replay(pkg):
    rec = pkg["provenance"]["chain"][-1]["record"]
    gi, rs = pkg["gate_inputs"], pkg["resource_state"]
    if SABOTAGE and "DEFAULTED" in (rs.get("evidence_states") or {}).values():
        return "DEFER", ["sabotage:defaulted_tag"]
    d, r = vp.replay_gate(rec, gi["capability"], gi["capability_registry"], rs["runtime"], gi["policy"])
    return d, list(r)


def failed(pkg):
    return sorted(n for n, ok, _ in vp.verify(json.loads(vp.canon(pkg))) if not ok)


def relabel(base, tags):
    p = copy.deepcopy(base)
    p["resource_state"]["evidence_states"].update(tags)
    p["known_limitations"][3] = vp.evidence_statement(p["resource_state"]["evidence_states"])
    return reseal(p)


def outside_allowed(p):
    q = copy.deepcopy(p)
    q["resource_state"].pop("evidence_states", None)
    q["known_limitations"][3] = None
    q.pop("package_sha256", None)
    return vp.canon(q)


def main():
    with tempfile.TemporaryDirectory() as tmp:
        base = base_package(tmp)
    held = {}
    base_tags = dict(base["resource_state"]["evidence_states"])
    base_dec = replay(base)
    print("base tags", base_tags, "| replay", base_dec, "| recorded", base["decision"]["decision"],
          "| failed checks", failed(base))

    # PR0a: change a VALUE, not a tag
    v = copy.deepcopy(base)
    v["resource_state"]["runtime"]["compute_budget"] = "exhausted"
    v_dec = replay(v)
    held["PR0a"] = v_dec[0] == "DEFER" and v_dec != base_dec
    print("PR0a value control: compute_budget exhausted ->", v_dec)

    # PR1: structural
    srcs = {f: open(os.path.join(ROOT, "sovereign_veritas", f), encoding="utf-8").read()
            for f in ("decision.py", "runtime.py", "capability.py", "verification.py")}
    srcs["replay_gate"] = inspect.getsource(vp.replay_gate)
    mentions = [k for k, s in srcs.items() if "evidence_states" in s or "evidence_state" in s]
    params = list(inspect.signature(Gate.evaluate).parameters)
    held["PR1"] = not mentions and not any("state" in p and p != "runtime" for p in params)
    print("PR1 files mentioning evidence states:", mentions or "none", "| Gate.evaluate params:", params)

    # the 24 relabels
    base_outside = outside_allowed(base)
    same, ev_pass, only_ev, undecided = 0, 0, 0, 0
    print("\nfield            state        replay              invariant  failed checks")
    for field in FIELDS:
        for state in STATES:
            p = relabel(base, {field: state})
            dec = replay(p)
            inv = outside_allowed(p) == base_outside
            f = failed(p)
            undecided += not inv
            same += inv and dec == base_dec
            ev_pass += inv and "evidence_states" not in f
            only_ev += inv and f == ["evidence_states"]
            print(f"{field:16} {state:12} {dec[0]:6} {str(dec[1]):12} {str(inv):10} {f}")
    held["PR2"] = same == 24
    held["PR3"] = undecided == 0
    held["PR4"] = ev_pass == 6 and only_ev == 18
    print(f"\nreplay unchanged {same} of 24 | UNDECIDED {undecided} | evidence_states pass {ev_pass} of 24 |"
          f" failing on evidence_states alone {only_ev} of 18")

    # PR5: honest all-DEFAULTED
    d = relabel(base, {f: "DEFAULTED" for f in FIELDS})
    d_dec, d_fail = replay(d), failed(d)
    held["PR5"] = d_dec == ("ALLOW", []) and d_fail == []
    print("PR5 all-DEFAULTED: replay", d_dec, "| failed checks", d_fail or "none")

    held["PR0b"] = None  # judged by running --sabotage separately; this run cannot judge itself
    print("\nmode:", "SABOTAGE" if SABOTAGE else "normal")
    for k in ("PR0a", "PR1", "PR2", "PR3", "PR4", "PR5"):
        print(f"  {k:5} {'HELD' if held[k] else 'NOT HELD'}")
    n = sum(1 for k in ("PR0a", "PR1", "PR2", "PR3", "PR4", "PR5") if held[k])
    print(f"VERDICT  {n} of 6 as registered (PR0b: run --sabotage, expect exit 1)")
    return 0 if n == 6 else 1


if __name__ == "__main__":
    sys.exit(main())
