#!/usr/bin/env python3
"""verifier_mutants.py - is every guard in tools/verify_package.py load-bearing?

Method from EACE's mutation_check.py (github.com/holland202/eace @ 1991750): switch off one guard
at a time and require the tests to fail. A guard the tests do not notice being removed is inert,
and an inert guard is a log line, not a control. Registered in docs/INTEGRATION.md (I1).

Each guard is forced to PASS where its result enters the verdict: through the check() helper
inside verify(), and in main() for `signature` and `freshness_witness`. The mutation is made in a
temporary copy of the repository's tracked files; the working tree is never edited. Every test file
runs against each copy (a first version ran only files naming verify_package and missed
test_field_sweep.py, which loads the verifier indirectly).

The null mutant applies the same rewrite but names no guard. It must pass, or KILLED would mean
nothing: the tool has to be able to report SURVIVED.

  python tools/verifier_mutants.py [--only GUARD ...] [--list]
Exit: 0 every guard KILLED and the null mutant passed | 1 a guard SURVIVED | 2 could not run
Stdlib only (pytest runs the tests).
"""
import os, re, shutil, subprocess, sys, tempfile, time

sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join("tools", "verify_package.py")
NULL = "__no_guard__"
HELPER = "        checks.append((name, bool(ok), detail))"
CLI = {  # guards outside verify(): the line where each enters the verdict, and its mutant
    "signature": ('            checks.append(("signature", ok, detail))',
                  '            checks.append(("signature", True, detail))'),
    "freshness_witness": ('            checks.append(("freshness_witness", ok, f"{freshness}: {detail}"))',
                          '            checks.append(("freshness_witness", True, f"{freshness}: {detail}"))'),
}


def could_not_run(msg):
    print(f"COULD NOT RUN: {msg}")
    sys.exit(2)


def guards(source):
    names = sorted(set(re.findall(r'check\("([a-z_]+)"', source)))
    return names + sorted(CLI)


def mutate(source, guard):
    """The verifier source with `guard` forced to PASS. Each target line must occur exactly once."""
    old, new = CLI.get(guard, (HELPER, HELPER.replace("bool(ok)", f"True if name == {guard!r} else bool(ok)")))
    if source.count(old) != 1:
        could_not_run(f"{guard}: expected exactly one line {old.strip()!r} in {TARGET}")
    return source.replace(old, new)


def tracked_files():
    if os.path.isdir(os.path.join(ROOT, ".git")):
        out = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                             cwd=ROOT, capture_output=True, check=True).stdout
        return [p for p in out.decode("utf-8").split("\0") if p]
    return [os.path.relpath(os.path.join(d, f), ROOT) for d, dirs, files in os.walk(ROOT)
            for f in files if "__pycache__" not in d and ".git" not in d.split(os.sep)]


def verifier_tests(files):
    return sorted(p for p in files if p.startswith("tests/") and os.path.basename(p).startswith("test_")
                  and p.endswith(".py"))


def run_mutant(files, tests, source, guard):
    with tempfile.TemporaryDirectory(prefix="sv_mutant_") as tmp:
        for p in files:
            src = os.path.join(ROOT, p)
            if os.path.isfile(src):
                os.makedirs(os.path.dirname(os.path.join(tmp, p)) or tmp, exist_ok=True)
                shutil.copy2(src, os.path.join(tmp, p))
        with open(os.path.join(tmp, TARGET), "w", encoding="utf-8") as fh:
            fh.write(mutate(source, guard))
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        p = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", *tests],
                           cwd=tmp, capture_output=True, text=True, env=env, timeout=900)
    first = next((l.split()[1] for l in p.stdout.splitlines() if l.startswith("FAILED ")), "")
    last = (p.stdout.strip().splitlines() or [""])[-1]
    verdict = {0: "SURVIVED", 1: "KILLED"}.get(p.returncode, f"ERROR(pytest exit {p.returncode})")
    return verdict, first or last


def main():
    args = sys.argv[1:]
    only = []
    if "--only" in args:
        i = args.index("--only")
        only, args = args[i + 1:], args[:i]
    with open(os.path.join(ROOT, TARGET), encoding="utf-8") as fh:
        source = fh.read()
    names = guards(source)
    if "--list" in args:
        print("\n".join(names))
        return
    if args:
        print("usage: python tools/verifier_mutants.py [--only GUARD ...] [--list]"); sys.exit(2)
    unknown = [g for g in only if g not in names]
    if unknown:
        could_not_run(f"no such guard: {', '.join(unknown)}")
    files = tracked_files()
    tests = verifier_tests(files)
    if TARGET.replace(os.sep, "/") not in [f.replace(os.sep, "/") for f in files] or not tests:
        could_not_run("verifier or its tests not found among tracked files")
    t0 = time.time()
    print(f"verifier_mutants | {len(names)} guards | {len(tests)} test files")
    verdict, detail = run_mutant(files, tests, source, NULL)
    print(f"  {'(null mutant)':<34} {verdict:<9} {detail}")
    if verdict != "SURVIVED":
        could_not_run("the null mutant did not pass, so a KILLED verdict would mean nothing")
    survived, errors = [], []
    for g in (only or names):
        verdict, detail = run_mutant(files, tests, source, g)
        print(f"  {g:<34} {verdict:<9} {detail}")
        if verdict == "SURVIVED":
            survived.append(g)
        elif verdict != "KILLED":
            errors.append(g)
    n = len(only or names)
    print(f"VERDICT  {n - len(survived) - len(errors)} of {n} KILLED, {len(survived)} SURVIVED"
          f"{', ' + str(len(errors)) + ' ERROR' if errors else ''}  ({time.time() - t0:.0f} s)")
    if errors:
        sys.exit(2)
    sys.exit(1 if survived else 0)


if __name__ == "__main__":
    main()
