#!/usr/bin/env python3
"""test_vacuity_audit.py - TVA-1: find tests that pass or skip for the wrong reason (docs/TVA1_PREREG.md).

Runs pytest three ways and compares the outcomes test by test (JUnit XML):
  A  as is;
  B  with skipping disabled: -p no:skipping, plus a plugin that makes unittest.TestCase.skipTest, unittest.skip*,
     pytest.skip and pytest.importorskip no-ops. A test skipped in A that PASSES in B was skipped for a reason its body
     does not need: a COLLATERAL SKIP (flagged). One that fails or errors in B had a justified skip;
  C  in a clean checkout of HEAD (git worktree). A test that passes in A but fails, errors or skips in C depends on files
     that are not in the commit: UNTRACKED DEPENDENCY (flagged). A test absent from C (its file is not committed yet) is
     reported as NOT IN HEAD (review), not flagged.
Static review (not flagged): test functions with no assert, pytest.raises/warns/fail or assert* call in their body, and
`assert` on a bare name, call, attribute or subscript (truthiness only; may be fine, may hide a non-bool value).

  python tools/test_vacuity_audit.py REPO [TEST_PATH ...] [--no-clean-checkout] [--json OUT]
Every run uses --continue-on-collection-errors. A module that cannot be collected AS IS makes the verdict NOT ESTABLISHED
(its tests are invisible to the audit). A module that cannot be collected in the clean checkout flags each of its tests
that passed as is as an UNTRACKED DEPENDENCY.
Exit: 0 nothing flagged | 1 something flagged | 2 pytest could not run, or not established. The environment is passed through unchanged
(PYTHONPATH etc.), so a caller can simulate a missing library with a shadow module. Stdlib only; pytest is run as a
subprocess with the interpreter running this script.
"""
import argparse
import ast
import json
import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

UNSKIP = '''"""vacuity_unskip: loaded with -p by tools/test_vacuity_audit.py. Turns skips into no-ops."""
import unittest
import pytest

unittest.TestCase.skipTest = lambda self, reason=None: None
unittest.skip = unittest.case.skip = lambda reason: (lambda obj: obj)
unittest.skipIf = unittest.case.skipIf = lambda condition, reason: (lambda obj: obj)
unittest.skipUnless = unittest.case.skipUnless = lambda condition, reason: (lambda obj: obj)
_skip_exception = pytest.skip.Exception


def _noskip(*args, **kwargs):
    return None


_noskip.Exception = _skip_exception
pytest.skip = _noskip
_importorskip = pytest.importorskip


def _importorskip_none(modname, *args, **kwargs):
    try:
        return _importorskip(modname, *args, **kwargs)
    except BaseException:
        return None


pytest.importorskip = _importorskip_none
'''
BOOLISH = {"isinstance", "issubclass", "callable", "all", "any", "hasattr", "bool", "exists", "isfile", "isdir",
           "startswith", "endswith", "is_file", "is_dir", "match", "fullmatch", "search", "issubset", "issuperset"}


def run_pytest(cwd, paths, extra_env=None, extra_args=()):
    """{test id: (outcome, message)} from one pytest run, or None if pytest produced no report."""
    with tempfile.TemporaryDirectory() as tmp:
        xml = os.path.join(tmp, "report.xml")
        env = dict(os.environ, **(extra_env or {}))
        subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--continue-on-collection-errors",
                        "--junitxml", xml, *extra_args, *paths], cwd=cwd, env=env, capture_output=True, text=True)
        if not os.path.exists(xml):
            return None
        out = {}
        for case in ET.parse(xml).iter("testcase"):
            tid = f"{case.get('classname')}::{case.get('name')}"
            outcome, message = "passed", ""
            for child in case:
                if child.tag in ("skipped", "failure", "error"):
                    outcome, message = child.tag, (child.get("message") or "")[:160]
                    break
            if not case.get("classname") and outcome == "error":  # a module that could not be collected
                tid, outcome = f"{COLLECT}{case.get('name')}", "collection_error"
            out[tid] = (outcome, message)
        return out


COLLECT = "<collection error>::"


def uncollected(run):
    """Modules (dotted, as pytest names them) that could not be collected in this run."""
    return sorted(t[len(COLLECT):] for t, (o, _) in (run or {}).items() if o == "collection_error")


def in_module(test_id, modules):
    cls = test_id.split("::", 1)[0]
    return next((m for m in modules if cls == m or cls.startswith(m + ".")), None)


def unskipped_run(cwd, paths):
    with tempfile.TemporaryDirectory() as plugdir:
        with open(os.path.join(plugdir, "vacuity_unskip.py"), "w", encoding="utf-8") as fh:
            fh.write(UNSKIP)
        pp = plugdir + (os.pathsep + os.environ["PYTHONPATH"] if os.environ.get("PYTHONPATH") else "")
        return run_pytest(cwd, paths, {"PYTHONPATH": pp}, ("-p", "no:skipping", "-p", "vacuity_unskip"))


def clean_checkout_run(repo, paths):
    if subprocess.run(["git", "-C", repo, "rev-parse", "HEAD"], capture_output=True).returncode != 0:
        return None, "not a git repository"
    tmp = tempfile.mkdtemp()
    wt = os.path.join(tmp, "clean")
    try:
        p = subprocess.run(["git", "-C", repo, "worktree", "add", "-q", "--detach", wt, "HEAD"], capture_output=True, text=True)
        if p.returncode != 0:
            return None, p.stderr.strip()
        return run_pytest(wt, paths), ""
    finally:
        subprocess.run(["git", "-C", repo, "worktree", "remove", "--force", wt], capture_output=True)
        shutil.rmtree(tmp, ignore_errors=True)


def test_files(repo, paths):
    out = []
    for p in paths or ["tests"]:
        full = os.path.join(repo, p)
        if os.path.isfile(full) and full.endswith(".py"):
            out.append(full)
        elif os.path.isdir(full):
            for root, _, files in os.walk(full):
                out += [os.path.join(root, f) for f in sorted(files)
                        if f.endswith(".py") and (f.startswith("test_") or f.endswith("_test.py"))]
    return sorted(set(out))


def _asserts_anything(fn):
    for node in ast.walk(fn):
        if isinstance(node, ast.Assert):
            return True
        if isinstance(node, ast.Raise):
            return True
        if isinstance(node, ast.Call):
            f = node.func
            name = f.attr if isinstance(f, ast.Attribute) else f.id if isinstance(f, ast.Name) else ""
            if name in ("raises", "warns", "fail", "deprecated_call") or name.startswith("assert"):
                return True
    return False


def _bare(test):
    if isinstance(test, ast.Call):
        f = test.func
        name = f.attr if isinstance(f, ast.Attribute) else f.id if isinstance(f, ast.Name) else ""
        return name not in BOOLISH
    return isinstance(test, (ast.Name, ast.Attribute, ast.Subscript))


def static_review(repo, files):
    no_assert, truthy = [], []
    for path in files:
        try:
            tree = ast.parse(open(path, encoding="utf-8").read())
        except (SyntaxError, UnicodeDecodeError):
            continue
        rel = os.path.relpath(path, repo)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
                if not _asserts_anything(node):
                    no_assert.append(f"{rel}::{node.name}")
                for a in (n for n in ast.walk(node) if isinstance(n, ast.Assert)):
                    if _bare(a.test):
                        truthy.append(f"{rel}:{a.lineno} in {node.name}: assert {ast.unparse(a.test)[:70]}")
    return no_assert, truthy


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("repo")
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--no-clean-checkout", action="store_true")
    ap.add_argument("--json")
    a = ap.parse_args(argv)
    repo = os.path.abspath(a.repo)
    runs = {"A": run_pytest(repo, a.paths), "B": unskipped_run(repo, a.paths)}
    if runs["A"] is None or runs["B"] is None:
        print("COULD NOT RUN: pytest produced no report (is pytest installed?)")
        return 2
    c_note = "skipped (--no-clean-checkout)"
    if not a.no_clean_checkout:
        runs["C"], why = clean_checkout_run(repo, a.paths)
        c_note = why or ""
    A, B, C = runs["A"], runs["B"], runs.get("C")
    col_a, col_b, col_c = uncollected(A), uncollected(B), uncollected(C)
    A = {t: v for t, v in A.items() if v[0] != "collection_error"}
    skipped = {t: m for t, (o, m) in A.items() if o == "skipped"}
    collateral = sorted(t for t in skipped if B.get(t, ("missing", ""))[0] == "passed")
    justified = sorted(t for t in skipped if t not in collateral)
    untracked = sorted(t for t, (o, _) in A.items() if o == "passed" and C is not None and (
        (t in C and C[t][0] != "passed") or (t not in C and in_module(t, col_c))))
    not_in_head = sorted(t for t in A if C is not None and t not in C and not in_module(t, col_c))
    no_assert, truthy = static_review(repo, test_files(repo, a.paths))
    counts = {k: sum(1 for o, _ in A.values() if o == k) for k in ("passed", "failed", "error", "skipped")}
    counts["failed"] = sum(1 for o, _ in A.values() if o == "failure")
    print(f"test_vacuity_audit | {repo} | as is: {len(A)} tests, {counts}")
    for m in col_a:
        print(f"  NOT ESTABLISHED  could not be collected as is: {m}  (its tests are invisible to this audit)")
    print(f"  skipped as is: {len(skipped)}; with skipping disabled: {len(collateral)} pass (collateral), "
          f"{len(justified)} fail or error (justified)")
    for t in collateral:
        print(f"  FLAG  collateral skip: {t}  (skip reason: {skipped[t]!r})")
    for t in justified:
        how = B.get(t, ("collection error" if in_module(t, col_b) else "missing", ""))[0]
        print(f"  ok    justified skip:  {t}  -> {how} when un-skipped")
    if C is None:
        print(f"  clean checkout: not run ({c_note})")
    else:
        print(f"  clean checkout of HEAD: {len(C)} tests; {len(untracked)} pass as is but not there; "
              f"{len(not_in_head)} not in HEAD at all")
        for m in col_c:
            print(f"  clean checkout: could not collect {m}")
        for t in untracked:
            why = C[t] if t in C else ("its module could not be collected", in_module(t, col_c))
            print(f"  FLAG  untracked dependency: {t}  -> {why[0]} in the clean checkout: {why[1][:90]}")
        for t in not_in_head[:20]:
            print(f"  review  not in HEAD (uncommitted test): {t}")
    print(f"  review: {len(no_assert)} test(s) with no assertion in their body; {len(truthy)} truthiness-only assert(s)")
    for t in no_assert[:40]:
        print(f"  review  no assertion: {t}")
    for t in truthy[:40]:
        print(f"  review  truthiness: {t}")
    flagged = len(collateral) + len(untracked)
    if col_a:
        print(f"VERDICT  NOT ESTABLISHED: {len(col_a)} module(s) could not be collected as is; "
              f"{flagged} flagged among the tests that ran")
    else:
        print(f"VERDICT  {flagged} flagged ({len(collateral)} collateral skip(s), {len(untracked)} untracked dependenc(ies))")
    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump({"repo": repo, "as_is": counts, "collateral": collateral, "justified": justified,
                       "untracked": untracked, "not_in_head": not_in_head if C is not None else [],
                       "clean_checkout": c_note if C is None else len(C),
                       "no_assert": no_assert, "truthy": truthy, "uncollected_as_is": col_a,
                       "uncollected_clean_checkout": col_c}, fh, indent=1)
    return 2 if col_a else 1 if flagged else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
