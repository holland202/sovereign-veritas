"""DK probe (registration: docs/DK_PREREG.md): duplicate JSON keys and non-finite literals in evidence packages.

Runs the real verifier (tools/verify_package.py, loaded as a module) in-process on edited copies of every package
in evidence/.

  python tools/dk_probe.py              exit 0 only on the RECORDED (after-change) outcome
  python tools/dk_probe.py --baseline   print the table only (used once, on the unchanged verifier)
  python tools/dk_probe.py --sabotage   the verifier's strict parser is swapped for plain json.loads; must exit 1
"""
from __future__ import annotations

import contextlib
import glob
import hashlib
import importlib.util
import io
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RECORDED = ((True, True, True), "d775ead0a8e2dce0eb08e77d7bbac487f4deafad80e3caeaac56f4a79adf0a8a")  # pinned after the scored run
PLANT = {"decision": "REFUSE", "reasons": ["planted"]}
CELLS = ("K0", "K1", "K2", "K3", "K4", "K5", "K6")


def load_verifier():
    spec = importlib.util.spec_from_file_location("vp_dk", os.path.join(ROOT, "tools", "verify_package.py"))
    vp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vp)
    return vp


def dumps(v):
    return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def members(obj, extra_before=None, extra_after=None, nested=None):
    """Serialize a dict canonically, member by member, with optional raw members inserted."""
    parts = []
    for k in sorted(obj):
        if extra_before and k in extra_before:
            parts.append(extra_before[k])
        val = nested[k] if nested and k in nested else dumps(obj[k])
        parts.append(f"{dumps(k)}:{val}")
    if extra_after:
        parts.extend(extra_after)
    return "{" + ",".join(parts) + "}"


def edit(cell, d):
    if cell == "K0":
        return members(d)
    if cell == "K1":
        return members(d, extra_before={"decision": f'"decision":{dumps(PLANT)}'})
    if cell == "K2":
        return members(d, extra_after=[f'"decision":{dumps(PLANT)}'])
    if cell == "K3":
        gi = d["gate_inputs"]
        first = sorted(gi)[0]
        inner = members(gi, extra_before={first: f'{dumps(first)}:"planted"'})
        return members(d, nested={"gate_inputs": inner})
    if cell == "K4":
        return members(d, extra_before={"schema": f'"schema":{dumps(d["schema"])}'})
    if cell == "K5":
        return members(d, extra_after=['"x_nan":NaN'])
    if cell == "K6":
        return members(d, extra_after=['"x_inf":Infinity'])
    raise KeyError(cell)


def run_verifier(vp, path):
    old = sys.argv
    sys.argv = ["verify_package.py", path]
    out = io.StringIO()
    code = 0
    try:
        with contextlib.redirect_stdout(out):
            vp.main()
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
    finally:
        sys.argv = old
    return code


def collect(sabotage):
    vp = load_verifier()
    if sabotage:
        vp.loads_bounded = lambda text: json.loads(text)
    table = {c: [] for c in CELLS}
    k0_identical = True
    with tempfile.TemporaryDirectory() as tmp:
        for p in sorted(glob.glob(os.path.join(ROOT, "evidence", "*.json"))):
            raw = open(p, encoding="utf-8").read()
            d = json.loads(raw)
            for cell in CELLS:
                text = edit(cell, d)
                if cell == "K0":
                    k0_identical &= text.strip() == raw.strip()
                q = os.path.join(tmp, f"{cell}.json")
                with open(q, "w", encoding="utf-8") as fh:
                    fh.write(text)
                table[cell].append(run_verifier(vp, q))
    return table, k0_identical


def main(argv):
    baseline, sabotage = "--baseline" in argv, "--sabotage" in argv
    table, k0_identical = collect(sabotage)
    n = len(table["K0"])
    print(f"packages {n}; K0 text identical to the original bytes: {k0_identical}")
    for c in CELLS:
        counts = {code: table[c].count(code) for code in sorted(set(table[c]))}
        print(f"{c}  exit codes {table[c]}  {counts}")
    if baseline:
        dk1 = all(v == 0 for c in ("K0", "K1", "K3", "K4") for v in table[c])
        dk2 = all(v == 1 for c in ("K2", "K5", "K6") for v in table[c])
        print(f"{'HELD   ' if dk1 else 'REFUTED'} DK1 (before the change)")
        print(f"{'HELD   ' if dk2 else 'REFUTED'} DK2 (before the change)")
        return 0
    dk3 = all(v == 0 for v in table["K0"]) and all(v == 2 for c in CELLS[1:] for v in table[c])
    dk5 = all(v == 2 for v in table["K4"])
    held = (dk3, dk5, k0_identical)
    print(f"{'HELD   ' if dk3 else 'REFUTED'} DK3 (after the change)")
    print(f"{'HELD   ' if dk5 else 'REFUTED'} DK5 (K4 refused: the stated cost)")
    digest = hashlib.sha256(json.dumps(table, sort_keys=True).encode()).hexdigest()
    print(f"DIGEST {digest}")
    if RECORDED is None:
        print("RECORDED not pinned yet")
        return 1
    return 0 if (held, digest) == RECORDED else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
