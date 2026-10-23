#!/usr/bin/env python3
"""BT-001 blue arm: do this repository's defences catch small planted faults in the kernel?

For each target file, in the registered order, every mutation point is enumerated deterministically from the
file's AST. Each mutant is written into a scratch copy of the repository (never into this checkout), and two
oracles run against it:

  T  the test suite: `pytest -x` over every test file, the files that import the target first (order changes
     only how fast a kill is found, not whether one is)
  C  the contract check: `tools/gate_contract.py --check kernel` (4,690 published vectors, digest compared)

A mutant is KILLED by an oracle when that oracle fails (non-zero exit, timeout, or no CONFORMS verdict) and
SURVIVES when it passes. Results are appended one JSON line per mutant, so a stopped run resumes where it left
off. Bytecode caching is off (-B, PYTHONDONTWRITEBYTECODE) and __pycache__ is cleared before every mutant, so a
same-size, same-second edit cannot be masked by a stale .pyc.

Controls (run first, every launch):
  null          the Gate file byte-for-byte unchanged (Amendment A1; the launch-1 null was an AST re-emission)
  always-allow  `return Decision("ALLOW")` as the first statement of Gate.evaluate: both oracles must FAIL

Usage:
  bt001_mutate.py --list                                  # enumerate mutants, run nothing
  bt001_mutate.py --until 2026-10-23T00:00:00Z --out F    # the registered run (resumable)
  bt001_mutate.py --show ID                               # print one mutant's changed lines
"""
import argparse, ast, copy, difflib, hashlib, json, os, shutil, subprocess, sys, time
from datetime import datetime, timezone

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TARGETS = ["sovereign_veritas/decision.py", "sovereign_veritas/verification.py", "sovereign_veritas/idempotency.py",
           "sovereign_veritas/evidence.py", "sovereign_veritas/capability.py", "sovereign_veritas/runtime.py",
           "sovereign_veritas/workflow.py"]
T_TIMEOUT, C_TIMEOUT = 600, 120
# Amendment A1: this test locates its own patches by exact source text, so it fails on ANY edit to an anchored
# line whatever the behaviour. It tests gate_constraint's instrument, not the kernel, and is left out of T.
DESELECT = "tests/test_gate_constraint.py::test_gate_constraint_instrument_kills_its_mutants"
CMP_SWAP = {ast.Lt: ast.LtE, ast.LtE: ast.Lt, ast.Gt: ast.GtE, ast.GtE: ast.Gt, ast.Eq: ast.NotEq,
            ast.NotEq: ast.Eq, ast.In: ast.NotIn, ast.NotIn: ast.In, ast.Is: ast.IsNot, ast.IsNot: ast.Is}


def docstring_nodes(tree):
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.body:
            b = n.body[0]
            if isinstance(b, ast.Expr) and isinstance(b.value, ast.Constant) and isinstance(b.value.value, str):
                out.add(id(b.value))
    return out


def annotation_nodes(tree):
    out = set()
    for n in ast.walk(tree):
        anns = []
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            anns.append(n.returns)
            a = n.args
            anns += [x.annotation for x in a.posonlyargs + a.args + a.kwonlyargs]
            anns += [x.annotation for x in (a.vararg, a.kwarg) if x is not None]
        elif isinstance(n, ast.AnnAssign):
            anns.append(n.annotation)
        for t in anns:
            if t is not None:
                out.update(id(x) for x in ast.walk(t))
    return out


def points(tree):
    """(path, kind, detail) for every mutation point, in a fixed order."""
    skip = docstring_nodes(tree) | annotation_nodes(tree)
    pts = []
    for path, node in walk(tree):
        if id(node) in skip:
            continue
        if isinstance(node, ast.Compare):
            for k, op in enumerate(node.ops):
                if type(op) in CMP_SWAP:
                    pts.append((path, "cmp", k))
        elif isinstance(node, ast.BoolOp):
            pts.append((path, "boolop", None))
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            pts.append((path, "drop-not", None))
        elif isinstance(node, ast.Constant) and type(node.value) is bool:
            pts.append((path, "flip-bool", None))
        elif isinstance(node, ast.Constant) and type(node.value) in (int, float) and type(node.value) is not bool:
            pts.append((path, "num+1", None))
        elif isinstance(node, ast.Return) and node.value is not None:
            pts.append((path, "return-none", None))
        elif isinstance(node, ast.Raise):
            pts.append((path, "raise-to-pass", None))
        elif isinstance(node, ast.If):
            pts.append((path, "negate-if", None))
    return pts


def walk(node, path=()):
    yield path, node
    for field, value in ast.iter_fields(node):
        if isinstance(value, list):
            for i, v in enumerate(value):
                if isinstance(v, ast.AST):
                    yield from walk(v, path + ((field, i),))
        elif isinstance(value, ast.AST):
            yield from walk(value, path + ((field, None),))


def resolve(tree, path):
    node = tree
    for field, i in path:
        node = getattr(node, field) if i is None else getattr(node, field)[i]
    return node


def apply(tree, pt):
    t = copy.deepcopy(tree)
    path, kind, k = pt
    n = resolve(t, path)
    if kind == "cmp":
        n.ops[k] = CMP_SWAP[type(n.ops[k])]()
    elif kind == "boolop":
        n.op = ast.Or() if isinstance(n.op, ast.And) else ast.And()
    elif kind == "drop-not":
        parent_path, (field, i) = path[:-1], path[-1]
        parent = resolve(t, parent_path)
        if i is None:
            setattr(parent, field, n.operand)
        else:
            getattr(parent, field)[i] = n.operand
    elif kind == "flip-bool":
        n.value = not n.value
    elif kind == "num+1":
        n.value = n.value + 1
    elif kind == "return-none":
        n.value = ast.Constant(None)
    elif kind == "raise-to-pass":
        parent_path, (field, i) = path[:-1], path[-1]
        getattr(resolve(t, parent_path), field)[i] = ast.Pass()
    elif kind == "negate-if":
        n.test = ast.UnaryOp(op=ast.Not(), operand=n.test)
    return ast.unparse(ast.fix_missing_locations(t))


def span_patch(src, node, new_text):
    """Replace exactly `node`'s source span (UTF-8 byte offsets, as ast reports them); every other byte is kept."""
    b = src.encode("utf-8")
    starts = [0]
    for line in src.encode("utf-8").splitlines(keepends=True):
        starts.append(starts[-1] + len(line))
    lo = starts[node.lineno - 1] + node.col_offset
    hi = starts[node.end_lineno - 1] + node.end_col_offset
    return (b[:lo] + new_text.encode("utf-8") + b[hi:]).decode("utf-8")


def apply_text(src, tree, pt):
    """Amendment A1: the same mutation as `apply`, written as a minimal edit of the original text, so formatting
    and comments elsewhere are byte-identical. Checked: the patched text parses to the same AST as `apply`."""
    path, kind, k = pt
    n = resolve(tree, path)
    seg = lambda x: ast.get_source_segment(src, x)
    if kind in ("cmp", "boolop"):
        target, new = n, "(" + ast.unparse(resolve(ast.parse(apply(tree, pt)), path)) + ")"
    elif kind == "drop-not":
        target, new = n, "(" + seg(n.operand) + ")"
    elif kind == "flip-bool":
        target, new = n, repr(not n.value)
    elif kind == "num+1":
        target, new = n, repr(n.value + 1)
    elif kind == "return-none":
        target, new = n.value, "None"
    elif kind == "raise-to-pass":
        target, new = n, "pass"
    elif kind == "negate-if":
        target, new = n.test, "not (" + seg(n.test) + ")"
    text = span_patch(src, target, new)
    if ast.dump(ast.parse(text)) != ast.dump(ast.parse(apply(tree, pt))):
        raise SystemExit(f"apply_text disagrees with apply at {kind} line {getattr(n, 'lineno', '?')}")
    return text


def always_allow(src, tree):
    """Amendment A1: Gate.evaluate's first statement (after its docstring, if any) becomes `return Decision("ALLOW")`,
    as a minimal text edit."""
    for n in ast.walk(tree):
        if isinstance(n, ast.ClassDef) and n.name == "Gate":
            for f in n.body:
                if isinstance(f, ast.FunctionDef) and f.name == "evaluate":
                    first = f.body[1] if id(f.body[0].value if isinstance(f.body[0], ast.Expr) else None) in docstring_nodes(tree) else f.body[0]
                    return span_patch(src, first, 'return Decision("ALLOW")')
    raise SystemExit("control always-allow: Gate.evaluate not found")


def mutants(target):
    src = open(os.path.join(ROOT, target), encoding="utf-8").read()
    tree = ast.parse(src)
    base = ast.unparse(tree)
    out = []
    base_dump = ast.dump(tree)
    for k, pt in enumerate(points(tree)):
        text = apply_text(src, tree, pt)
        line = getattr(resolve(tree, pt[0]), "lineno", None)
        out.append({"id": f"{target}#{k}", "target": target, "op": pt[1], "line": line,
                    "equal_to_base": ast.dump(ast.parse(text)) == base_dump,
                    "sha256": hashlib.sha256(text.encode()).hexdigest(), "text": text})
    return src, out


def tests_order(work, target):
    mod = os.path.splitext(os.path.basename(target))[0]
    files = sorted(f for f in os.listdir(os.path.join(work, "tests")) if f.startswith("test_") and f.endswith(".py"))
    near = [f for f in files if mod in open(os.path.join(work, "tests", f), encoding="utf-8").read()]
    return [os.path.join("tests", f) for f in near + [f for f in files if f not in near]]


def clear_pyc(work):
    for d, subdirs, _ in os.walk(work):
        for s in list(subdirs):
            if s == "__pycache__":
                shutil.rmtree(os.path.join(d, s), ignore_errors=True)


def oracles(work, target):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    env.pop("PYTHONPATH", None)
    clear_pyc(work)
    res = {}
    t0 = time.time()
    try:
        p = subprocess.run([sys.executable, "-B", "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider",
                            "--deselect", DESELECT, *tests_order(work, target)], cwd=work, env=env, capture_output=True, text=True,
                           timeout=T_TIMEOUT)
        tail = p.stdout.strip().splitlines()[-1:] or [""]
        res["T"] = {"verdict": "PASS" if p.returncode == 0 else "FAIL", "rc": p.returncode, "tail": tail[0][:300]}
    except subprocess.TimeoutExpired:
        res["T"] = {"verdict": "FAIL", "rc": "timeout", "tail": ""}
    res["T"]["seconds"] = round(time.time() - t0, 1)
    clear_pyc(work)
    t0 = time.time()
    try:
        p = subprocess.run([sys.executable, "-B", "tools/gate_contract.py", "--check", "kernel"], cwd=work, env=env,
                           capture_output=True, text=True, timeout=C_TIMEOUT)
        ok = p.returncode == 0 and "VERDICT  CONFORMS" in p.stdout
        res["C"] = {"verdict": "PASS" if ok else "FAIL", "rc": p.returncode,
                    "tail": ((p.stdout + p.stderr).strip().splitlines()[-1:] or [""])[0][:300]}
    except subprocess.TimeoutExpired:
        res["C"] = {"verdict": "FAIL", "rc": "timeout", "tail": ""}
    res["C"]["seconds"] = round(time.time() - t0, 1)
    return res


def make_work(work):
    if os.path.exists(work):
        shutil.rmtree(work)
    shutil.copytree(ROOT, work, ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"))


def run_one(work, target, text):
    path = os.path.join(work, target)
    orig = open(os.path.join(ROOT, target), encoding="utf-8").read()
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    try:
        return oracles(work, target)
    finally:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(orig)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--show")
    ap.add_argument("--until")
    ap.add_argument("--out", default="bt001_results.jsonl")
    ap.add_argument("--work", default=None)
    a = ap.parse_args(argv)
    if a.list:
        total = 0
        for t in TARGETS:
            _, ms = mutants(t)
            kinds = {}
            for m in ms:
                kinds[m["op"]] = kinds.get(m["op"], 0) + 1
            same = sum(m["equal_to_base"] for m in ms)
            print(f"{t}: {len(ms)} mutants {json.dumps(kinds, sort_keys=True)} equal_to_base={same}")
            total += len(ms)
        print(f"total {total}")
        return 0
    if a.show:
        t = a.show.split("#")[0]
        base, ms = mutants(t)
        m = next(m for m in ms if m["id"] == a.show)
        print(f"{m['id']} op={m['op']} line={m['line']}")
        sys.stdout.writelines(difflib.unified_diff(base.splitlines(True), m["text"].splitlines(True), "base", "mutant", n=1))
        return 0
    deadline = datetime.fromisoformat(a.until.replace("Z", "+00:00")).timestamp()
    work = a.work or os.path.join(os.path.dirname(os.path.abspath(a.out)), "bt001_work")
    make_work(work)
    done = set()
    if os.path.exists(a.out):
        done = {json.loads(l)["id"] for l in open(a.out, encoding="utf-8") if l.strip()}
    out = open(a.out, "a", encoding="utf-8")

    def emit(rec):
        rec["utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        out.write(json.dumps(rec, sort_keys=True) + "\n")
        out.flush()

    # controls, every launch
    dsrc = open(os.path.join(ROOT, "sovereign_veritas/decision.py"), encoding="utf-8").read()
    dtree = ast.parse(dsrc)
    launch = sum(1 for i in done if i.startswith("control:")) // 2 + 1
    for name, text, want in (("null", dsrc, "PASS"), ("always-allow", always_allow(dsrc, dtree), "FAIL")):
        r = run_one(work, "sovereign_veritas/decision.py", text)
        ok = r["T"]["verdict"] == want and r["C"]["verdict"] == want
        emit({"id": f"control:{name}:launch{launch}", "control": name, "expected": want, "as_expected": ok, **r})
        if not ok:
            print(f"CONTROL {name} NOT AS EXPECTED: {r}", file=sys.stderr)
            return 2
    n = 0
    for t in TARGETS:
        _, ms = mutants(t)
        for m in ms:
            if m["id"] in done:
                continue
            if time.time() >= deadline:
                print(f"deadline reached after {n} mutants this launch")
                return 0
            r = run_one(work, t, m["text"])
            emit({k: m[k] for k in ("id", "target", "op", "line", "equal_to_base", "sha256")} | r)
            n += 1
    print(f"all targets done after {n} mutants this launch")
    return 0


if __name__ == "__main__":
    sys.exit(main())
