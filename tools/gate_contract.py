#!/usr/bin/env python3
"""gate_contract.py - the Gate contract's test vectors: write them, and check any implementation.

The contract is CONTRACT.md; this tool holds it to its vectors (contract/gate_vectors.jsonl).
Registered in docs/GATE_CONTRACT.md (C1-C5) before this code was written.

  python tools/gate_contract.py --write                  regenerate the vectors from the kernel Gate
  python tools/gate_contract.py --check kernel           the kernel (sovereign_veritas.Gate)
  python tools/gate_contract.py --check verifier         replay_gate in tools/verify_package.py
  python tools/gate_contract.py --check-command CMD ...  any program, any language: it reads one case
                                                         per line on stdin, {"id", "input"}, and writes
                                                         one line per case, {"id", "decision", "reasons"}
  python tools/gate_contract.py --serve verifier         such a program, wrapping the verifier's Gate
  python tools/gate_contract.py --mutants                switch off each rule of the verifier's Gate
                                                         in turn; every one must fail at least one vector
Exit: 0 conforms (or: written, every mutant killed) | 1 does not conform | 2 could not run

The conformance digest is sha256 over canonical JSON of [[id, decision, reasons], ...] in vector
order. An implementation that matches every vector reproduces it exactly.
Stdlib only; --write and --check kernel also need this repository's kernel importable.
"""
import ast, copy, hashlib, importlib.util, inspect, itertools, json, math, os, subprocess, sys, textwrap

sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VECTORS = os.path.join(ROOT, "contract", "gate_vectors.jsonl")
CONTRACT = "sv.gate/0"
REGISTRY_NAMES = ("root-on", "root-off", "root-str", "root-null")  # root-null: never registered
CAP_FIELDS = ("name", "authorized", "required_evidence", "parent", "min_evidence_quality", "max_steps")


def canon(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def could_not_run(msg):
    print(f"COULD NOT RUN: {msg}")
    sys.exit(2)


def conformance_digest(rows):
    return hashlib.sha256(canon([[i, d, list(r)] for i, d, r in rows]).encode("utf-8")).hexdigest()


# ---- generating the vectors (from the kernel, over tools/gate_constraint.py's cases) ----------------
EXTRA = [  # docs/GATE_CONTRACT.md F2-F4: pin quality reading and reason formatting
    ("quality=true (not 1.0)", {"quality": True}),
    ("quality='0.9' (a string is not a number)", {"quality": "0.9"}),
    ("quality=1 (an integer is a number)", {"quality": 1}),
    ("quality=0.5 (equal to the floor)", {"quality": 0.5}),
    ("quality=0.49999 (reason rounds to 0.5000)", {"quality": 0.49999}),
    ("quality=0.03125 (tie: half-to-even gives 0.0312)", {"quality": 0.03125}),
    ("quality=10**400 (beyond float range)", {"quality": 10 ** 400}),
    ("quality=-0.5 (negative)", {"quality": -0.5}),
    ("top-level quality 'high', metadata 0.9 (top level wins)", {"top_quality": "high"}),
    ("top-level quality 0.9, metadata 0.2 (top level wins)", {"top_quality": 0.9, "quality": 0.2}),
    ("quality=1e16 (repr uses an exponent)", {"quality": 1e16}),
    ("quality=-1e-05 (repr uses an exponent)", {"quality": -1e-05}),
    # CONTRACT.md's other porting traps: truthiness, integers, Python equality, null entries
    ("input_digest=0 (0 is not present)", {"digest": 0}),
    ("authorized='true' (a string is not true)", {"authorized": "true"}),
    ("authorized=1 (1 is not true)", {"authorized": 1}),
    ("parent's registry entry is null", {"parent": "root-null"}),
    ("step_count=0 (checked, below 1)", {"steps": 0}),
    ("step_count=2.0 (not an integer)", {"steps": 2.0}),
    ("allow_only=null (no policy check)", {"policy": None}),
    ("requested=1, allow_only=[true] (Python equality)", {"requested": 1, "policy": [True]}),
]


def build(sv, gc, creg, cfg):
    """Kernel objects for one case: the construction of gate_constraint.evaluate, plus top_quality."""
    c = dict(gc.BASE, **cfg)
    verification = None
    if c["status"] is not gc.NOVERIF:
        verification = {} if c["status"] is gc.MISSING else {"status": c["status"]}
    action = None
    if c["action"]:
        action = {"requested": c["requested"]}
        if c["binding"] is not gc.MISSING:
            action["capability"] = c["binding"]
    metadata = {}
    for key, name in (("evidence", "calibration"), ("quality", "evidence_quality"), ("steps", "step_count")):
        if c[key] is not gc.MISSING:
            metadata[name] = c[key]
    record = sv.EvidenceRecord(record_id="gc", input_digest=c["digest"], verification=verification,
                               action=action, metadata=metadata, evidence_quality=cfg.get("top_quality"),
                               timestamp="2026-01-01T00:00:00+00:00")
    cap = (sv.Capability("read_sensor", authorized=c["authorized"], required_evidence=("calibration",),
                         parent=c["parent"], min_evidence_quality=0.5, max_steps=3) if c["cap"] else None)
    runtime = sv.RuntimeState("gate-constraint", "n/a", thermal_status=c["thermal"],
                              compute_budget=c["compute"], power_status=c["power"])
    policy = None if c["policy"] is gc.MISSING else {"allow_only": c["policy"]}
    return record, cap, runtime, policy, (creg if c["capreg"] else None)


def cap_json(cap):
    return None if cap is None else {k: v for k, v in cap.to_dict().items() if k in CAP_FIELDS}


def to_input(record, cap, runtime, policy, registry):
    r = record.to_dict()
    rt = runtime.to_dict()
    return {
        "record": {k: r[k] for k in ("input_digest", "verification", "action", "metadata", "evidence_quality")},
        "capability": cap_json(cap),
        "capability_registry": None if registry is None else {n: cap_json(registry.get(n)) for n in REGISTRY_NAMES},
        "runtime": {k: rt[k] for k in ("thermal_status", "compute_budget", "power_status")},
        "policy": policy,
    }


def generate():
    sys.path.insert(0, ROOT)
    import sovereign_veritas as sv
    gc = load("gate_constraint", os.path.join(ROOT, "tools", "gate_constraint.py"))
    vp = load("verify_package", os.path.join(ROOT, "tools", "verify_package.py"))
    creg = gc.cap_registry(sv)
    cases = [("L" + "".join(map(str, p)), {gc.AXES[i][0]: gc.AXES[i][1][k][0] for i, k in enumerate(p)}, True)
             for p in itertools.product(*[range(len(v)) for _, v in gc.AXES])]
    cases += [("S:" + cid, cfg, True) for cid, cfg, *_ in gc.S]
    cases += [("X:" + cid, cfg, False) for cid, cfg in EXTRA]
    lines, excluded, disagree = [], [], []
    for cid, cfg, from_gc in cases:
        objs = build(sv, gc, creg, cfg)
        d = sv.Gate().evaluate(*objs[:3], policy=objs[3], registry=objs[4])
        expect = {"decision": d.decision, "reasons": list(d.reasons)}
        if from_gc and gc.evaluate(sv, creg, cfg) != (d.decision, tuple(d.reasons)):
            could_not_run(f"{cid}: this builder and gate_constraint.evaluate disagree")
        try:
            inp = json.loads(canon(to_input(*objs)))
        except ValueError:  # NaN or infinity: not standard JSON
            excluded.append(cid)
            continue
        got = vp.replay_gate(inp["record"], inp["capability"], inp["capability_registry"],
                             inp["runtime"], inp["policy"])
        if [got[0], list(got[1])] != [expect["decision"], expect["reasons"]]:
            disagree.append((cid, expect, got))
        lines.append(canon({"id": cid, "input": inp, "expect": expect}))
    return lines, excluded, disagree


# ---- implementations under test ------------------------------------------------------------------
def read_vectors():
    try:
        with open(VECTORS, encoding="utf-8") as fh:
            return [json.loads(line) for line in fh if line.strip()]
    except (OSError, ValueError) as exc:
        could_not_run(f"vectors unreadable: {exc}")


def kernel_gate():
    sys.path.insert(0, ROOT)
    import sovereign_veritas as sv

    def cap(d):
        return None if d is None else sv.Capability(
            d["name"], authorized=d["authorized"], required_evidence=tuple(d["required_evidence"]),
            parent=d["parent"], min_evidence_quality=d["min_evidence_quality"], max_steps=d["max_steps"])

    def decide(inp):
        r = inp["record"]
        record = sv.EvidenceRecord(record_id="contract", input_digest=r["input_digest"],
                                   verification=r["verification"], action=r["action"],
                                   metadata=r["metadata"], evidence_quality=r["evidence_quality"])
        registry = None
        if inp["capability_registry"] is not None:
            registry = sv.CapabilityRegistry()
            for c in inp["capability_registry"].values():
                if c is not None:
                    registry.register(cap(c))
        rt = inp["runtime"]
        runtime = sv.RuntimeState("contract", "n/a", thermal_status=rt["thermal_status"],
                                  compute_budget=rt["compute_budget"], power_status=rt["power_status"])
        d = sv.Gate().evaluate(record, cap(inp["capability"]), runtime, policy=inp["policy"], registry=registry)
        return d.decision, list(d.reasons)
    return decide


def verifier_gate(replay=None):
    if replay is None:
        replay = load("verify_package", os.path.join(ROOT, "tools", "verify_package.py")).replay_gate

    def decide(inp):
        d, reasons = replay(inp["record"], inp["capability"], inp["capability_registry"],
                            inp["runtime"], inp["policy"])
        return d, list(reasons)
    return decide


def run(decide, vectors):
    rows = []
    for v in vectors:
        try:
            d, reasons = decide(copy.deepcopy(v["input"]))
        except Exception as exc:  # a crash is never a decision
            d, reasons = f"RAISE:{type(exc).__name__}", []
        rows.append((v["id"], d, reasons))
    return rows


def run_command(cmd, vectors):
    payload = "".join(canon({"id": v["id"], "input": v["input"]}) + "\n" for v in vectors)
    try:
        p = subprocess.run(cmd, input=payload, capture_output=True, text=True, timeout=600)
    except (OSError, subprocess.SubprocessError) as exc:
        could_not_run(f"{' '.join(cmd)}: {exc}")
    out = [line for line in p.stdout.splitlines() if line.strip()]
    if p.returncode != 0 or len(out) != len(vectors):
        could_not_run(f"{' '.join(cmd)}: exit {p.returncode}, {len(out)} lines for {len(vectors)} cases"
                      + (f"; stderr: {p.stderr.strip().splitlines()[-1]}" if p.stderr.strip() else ""))
    rows = []
    for v, line in zip(vectors, out):
        try:
            o = json.loads(line)
            ok = (isinstance(o, dict) and o.get("id") == v["id"] and isinstance(o.get("decision"), str)
                  and isinstance(o.get("reasons"), list) and all(isinstance(r, str) for r in o["reasons"]))
        except ValueError:
            ok = False
        if not ok:
            could_not_run(f"case {v['id']}: not a decision line: {line[:120]!r}")
        rows.append((o["id"], o["decision"], o["reasons"]))
    return rows


def report(label, rows, vectors):
    expected = conformance_digest([(v["id"], v["expect"]["decision"], v["expect"]["reasons"]) for v in vectors])
    bad = [(v, r) for v, r in zip(vectors, rows) if [r[1], list(r[2])] != [v["expect"]["decision"], v["expect"]["reasons"]]]
    print(f"gate_contract {CONTRACT} | {label} | {len(vectors)} vectors")
    for v, r in bad[:10]:
        print(f"  MISMATCH {v['id']}: expected {v['expect']['decision']} {v['expect']['reasons']}, got {r[1]} {list(r[2])}")
    if len(bad) > 10:
        print(f"  ... and {len(bad) - 10} more")
    got = conformance_digest(rows)
    print(f"conformance digest {got}  (expected {expected})")
    print(f"VERDICT  {'CONFORMS' if not bad else f'{len(bad)} of {len(vectors)} vectors differ'}")
    return 0 if not bad and got == expected else 1


# ---- rule mutants of the verifier's Gate ------------------------------------------------------------
# Rules no input can reach, each with the reason. A listed rule that becomes reachable (killed) fails
# too, so this list cannot go stale; a survivor not listed here is a gap in the vectors.
EQUIVALENT = {
    'elif status != "PASS":': "unreachable: coerce_status yields one of six statuses, and every one but "
                              "PASS and INSUFFICIENT_EVIDENCE is refused by the rule before it; a guard "
                              "for statuses added later",
}

def mutants(vectors):
    """Each `if` in replay_gate is a rule; a mutant replaces one test with False."""
    vp = load("verify_package", os.path.join(ROOT, "tools", "verify_package.py"))
    src = textwrap.dedent(inspect.getsource(vp.replay_gate))
    tree = ast.parse(src)
    ifs = [n for n in ast.walk(tree) if isinstance(n, ast.If)]
    lines = src.splitlines()

    def compiled(index):
        t = copy.deepcopy(tree)
        if index is not None:
            node = [n for n in ast.walk(t) if isinstance(n, ast.If)][index]
            node.test = ast.copy_location(ast.Constant(value=False), node.test)
        ns = dict(vars(vp))
        exec(compile(ast.fix_missing_locations(t), "<replay_gate mutant>", "exec"), ns)
        return ns["replay_gate"]

    expected = [[v["expect"]["decision"], v["expect"]["reasons"]] for v in vectors]

    def mismatches(replay):
        return sum([r[1], list(r[2])] != e for r, e in zip(run(verifier_gate(replay), vectors), expected))

    null = mismatches(compiled(None))
    print(f"gate_contract mutants | {len(ifs)} rules in replay_gate | {len(vectors)} vectors")
    print(f"  {'(null mutant)':<72} {'passes' if null == 0 else f'{null} mismatches'}")
    if null:
        could_not_run("the unmutated Gate does not pass its own vectors")
    survived, stale, equivalent = [], [], 0
    for i, node in enumerate(ifs):
        n = mismatches(compiled(i))
        rule = lines[node.lineno - 1].strip()
        if rule in EQUIVALENT:
            verdict = f"EQUIVALENT ({EQUIVALENT[rule].split(':')[0]})" if not n else f"KILLED by {n} - listed as EQUIVALENT"
            equivalent += not n
            if n:
                stale.append(rule)
        else:
            verdict = f"KILLED by {n}" if n else "SURVIVED"
            if not n:
                survived.append(rule)
        print(f"  {rule[:70]:<72} {verdict}")
    killed = len(ifs) - len(survived) - equivalent
    print(f"VERDICT  {killed} of {len(ifs)} rules pinned by the vectors, {equivalent} listed as unreachable, "
          f"{len(survived)} SURVIVED{', ' + str(len(stale)) + ' listed but reachable' if stale else ''}")
    return 1 if survived or stale else 0


def git_ignores(path):
    """True if git would silently leave this file out of a commit (a *.jsonl rule did, once)."""
    try:
        p = subprocess.run(["git", "check-ignore", "-q", path], cwd=ROOT, capture_output=True)
    except OSError:
        return False
    return p.returncode == 0


def serve(decide):
    for line in sys.stdin:
        if line.strip():
            case = json.loads(line)
            d, reasons = decide(case["input"])
            sys.stdout.write(canon({"id": case["id"], "decision": d, "reasons": reasons}) + "\n")


def main():
    a = sys.argv[1:]
    if a == ["--write"]:
        if git_ignores(VECTORS):
            print(f"REFUSED: git ignores {os.path.relpath(VECTORS, ROOT)}; the vectors would never be committed")
            sys.exit(1)
        lines, excluded, disagree = generate()
        if disagree:
            for cid, expect, got in disagree[:10]:
                print(f"  DISAGREE {cid}: kernel {expect}, verifier {got}")
            print(f"NOT WRITTEN: kernel and verifier disagree on {len(disagree)} vectors")
            sys.exit(1)
        os.makedirs(os.path.dirname(VECTORS), exist_ok=True)
        data = "".join(line + "\n" for line in lines).encode("utf-8")
        with open(VECTORS, "wb") as fh:
            fh.write(data)
        vectors = [json.loads(line) for line in lines]
        print(f"wrote {os.path.relpath(VECTORS, ROOT)}: {len(lines)} vectors, {len(data)} bytes")
        print(f"file sha256        {hashlib.sha256(data).hexdigest()}")
        print(f"conformance digest {conformance_digest([(v['id'], v['expect']['decision'], v['expect']['reasons']) for v in vectors])}")
        print(f"excluded (not standard JSON): {', '.join(excluded) or 'none'}")
        return
    if len(a) == 2 and a[0] == "--check" and a[1] in ("kernel", "verifier"):
        vectors = read_vectors()
        decide = kernel_gate() if a[1] == "kernel" else verifier_gate()
        sys.exit(report(a[1], run(decide, vectors), vectors))
    if len(a) >= 2 and a[0] == "--check-command":
        vectors = read_vectors()
        sys.exit(report(" ".join(a[1:]), run_command(a[1:], vectors), vectors))
    if a == ["--serve", "verifier"]:
        serve(verifier_gate())
        return
    if a == ["--mutants"]:
        sys.exit(mutants(read_vectors()))
    print(__doc__.strip().split("\n\n")[1])
    sys.exit(2)


if __name__ == "__main__":
    main()
