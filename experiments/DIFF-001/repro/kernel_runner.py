# DIFF-001 repro helper: runs the kernel (K) or package verifier (V) as a line-protocol program via tools/gate_contract.py adapters.
# Usage: kernel_runner.py REPO_ROOT kernel|verifier  (stdin/stdout as in CONTRACT.md). Adapter limit: K needs every runtime key, so a missing one is passed as None.
import json, sys, importlib.util, os
ROOT = sys.argv[1]
spec = importlib.util.spec_from_file_location("gc", os.path.join(ROOT, "tools", "gate_contract.py")); gc = importlib.util.module_from_spec(spec); spec.loader.exec_module(gc)
which = sys.argv[2]
decide = gc.kernel_gate() if which == "kernel" else gc.verifier_gate()
for n, line in enumerate(sys.stdin, 1):
  try:
    env = json.loads(line, parse_constant=lambda v: (_ for _ in ()).throw(ValueError(v))); inp = env["input"]
    for k in ("capability_registry", "policy"): inp.setdefault(k, None)
    inp["record"].setdefault("evidence_quality", None)
    if which == "kernel":
        for k in ("thermal_status", "compute_budget", "power_status"): inp["runtime"].setdefault(k, None)  # adapter needs every key; None = absent
    if inp.get("capability_registry"):
        for name, c in list(inp["capability_registry"].items()):
            if isinstance(c, dict):
                c.setdefault("name", name); c.setdefault("required_evidence", []); c.setdefault("parent", None)
                c.setdefault("min_evidence_quality", None); c.setdefault("max_steps", None)
    d, r = decide(inp)
    print(json.dumps({"id": env["id"], "decision": d, "reasons": list(r)}))
  except Exception as exc:
    print(f"line {n}: {type(exc).__name__}: {exc}", file=sys.stderr); sys.exit(2)
