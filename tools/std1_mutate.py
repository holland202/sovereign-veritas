#!/usr/bin/env python3
"""STD-1 (docs/STD1_PREREG.md): no-op mutation of each _reject(...) call site in the aap-conformance Python
reference verifier, judged by the suite's own fixtures.

  python tools/std1_mutate.py /path/to/aap-conformance          control + every mutant
  python tools/std1_mutate.py /path/to/aap-conformance --sabotage   harness self-test: pretend nothing fails

A mutant is KILLED when the mutated verifier exits non-zero over the fixture set (some fixture's expected verdict
or category is not met), CRASHED when it exits non-zero with a traceback, SURVIVED when it exits 0.
Exit codes: 0 = ran and the controls held; 1 = a control failed (the harness cannot be trusted); 2 = could not run.
"""
import ast
import os
import re
import subprocess
import sys
import tempfile

NOOP = "def _std1_noop(*a, **k):\n    return None\n\n\n"


def could_not_run(msg):
    print("COULD NOT RUN", msg)
    sys.exit(2)


def sites(src):
    """(line, category, function) for every _reject(...) call, from the AST, so the def line is not counted."""
    tree = ast.parse(src)
    out = []
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for node in ast.walk(fn):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_reject":
                arg = node.args[0] if node.args else None
                cat = arg.value if isinstance(arg, ast.Constant) else ast.unparse(arg) if arg else "?"
                out.append((node.lineno, node.col_offset, cat, fn.name))
    # a call inside a nested function is found twice (once per enclosing def); keep the innermost name
    best = {}
    for line, col, cat, name in out:
        best.setdefault((line, col), (cat, name))
        best[(line, col)] = (cat, name)
    inner = {}
    for fn in ast.walk(tree):
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for node in ast.walk(fn):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_reject":
                    key = (node.lineno, node.col_offset)
                    prev = inner.get(key)
                    if prev is None or fn.lineno > prev[1]:
                        inner[key] = (fn.name, fn.lineno)
    return [(line, col, best[(line, col)][0], inner[(line, col)][0]) for (line, col) in sorted(best)]


def mutate(src, line, col):
    lines = src.splitlines(keepends=True)
    row = lines[line - 1]
    if row[col:col + len("_reject(")] != "_reject(":
        could_not_run(f"site {line}:{col} is not a _reject( call")
    lines[line - 1] = row[:col] + "_std1_noop(" + row[col + len("_reject("):]
    out = "".join(lines)
    anchor = re.search(r"^def _reject\(.*?\n(?:[ \t]+.*\n)+", out, re.M)
    if not anchor:
        could_not_run("def _reject not found")
    return out[:anchor.end()] + "\n\n" + NOOP + out[anchor.end():]


def run(verifier, root):
    p = subprocess.run([sys.executable, verifier, "fixtures"], cwd=root, capture_output=True, text=True)
    failing = sorted(set(re.findall(r"^FAIL\s+(\S+)", p.stdout, re.M)))
    crashed = "Traceback" in p.stderr
    return p.returncode, failing, crashed, p.stdout.strip().splitlines()[-1:] or [""]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        could_not_run(__doc__)
    root = os.path.abspath(args[0])
    sabotage = "--sabotage" in sys.argv
    target = os.path.join(root, "verifiers", "python", "verify.py")
    if not os.path.isfile(target):
        could_not_run(f"{target} not found")
    src = open(target, encoding="utf-8").read()
    found = sites(src)
    print(f"SITES  {len(found)} _reject(...) call sites in verifiers/python/verify.py")

    tmpdir = os.path.join(root, "verifiers", "python")
    fd, mpath = tempfile.mkstemp(prefix="_std1_mutant_", suffix=".py", dir=tmpdir)
    os.close(fd)
    try:
        def judge(text):
            open(mpath, "w", encoding="utf-8").write(text)
            rc, failing, crashed, last = run(mpath, root)
            if sabotage:
                rc, failing = 0, []
            return rc, failing, crashed, last

        rc0, f0, c0, last0 = judge(src)
        control_clean = rc0 == 0 and not f0
        print(f"CONTROL unmutated: exit {rc0}, failing {len(f0)}  {last0[0]}")
        # Deviation from the registration (which said "the single BAD_SIGNATURE site"): there are two, one per
        # token form. The control uses the compact-form site, because the fixture it names is a compact token.
        sig = [s for s in found if s[2] == "BAD_SIGNATURE" and s[3] == "verify_compact_structure"]
        if len(sig) != 1:
            could_not_run(f"expected 1 compact-form BAD_SIGNATURE site, found {len(sig)}")
        rcs, fs, cs, _ = judge(mutate(src, *sig[0][:2]))
        control_sig = "fixtures/cgt-compact-bad-signature.json" in fs
        print(f"CONTROL signature check removed (line {sig[0][0]}): exit {rcs}, failing {fs}")
        if not (control_clean and control_sig):
            print("VERDICT  HARNESS CONTROL FAILED: P2 refuted; P3/P4 not judged")
            sys.exit(1)

        killed = survived = crashed_n = 0
        per_fixture = {}
        for line, col, cat, fn in found:
            rc, failing, crashed, last = judge(mutate(src, line, col))
            if rc == 0 and not failing:
                status = "SURVIVED"
                survived += 1
            elif crashed and not failing:
                status = "CRASHED"
                crashed_n += 1
            else:
                status = "KILLED"
                killed += 1
                for f in failing:
                    per_fixture[f] = per_fixture.get(f, 0) + 1
            print(f"{status:8s} line {line:4d}  {cat:22s} in {fn:34s} by {len(failing)}: {' '.join(os.path.basename(f) for f in failing[:4])}{' ...' if len(failing) > 4 else ''}")
        top = max(per_fixture.items(), key=lambda kv: kv[1]) if per_fixture else ("-", 0)
        print(f"TOTAL    {len(found)} sites: {killed} killed, {crashed_n} crashed only, {survived} survived")
        print(f"SPREAD   most kills by one fixture: {top[1]} of {killed} ({os.path.basename(top[0])})")
    finally:
        os.remove(mpath)


if __name__ == "__main__":
    main()
