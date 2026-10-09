#!/usr/bin/env python3
"""p001_mutants.py - ACCEPTANCE C06: the frozen P-001 tests must catch three planted defects.

  python tools/p001_mutants.py
Exit: 0 baseline passes and every mutant is killed | 1 a mutant survived or the baseline failed |
      2 could not run (a mutant's patch did not apply: the mutant would be a no-op, which proves nothing)

Each run copies the repository (without .git) to a temporary directory, applies one exact source
replacement there, and runs tests/test_p001_w1.py + tests/test_p001_w2.py against the copy. The real
checkout is never modified. The unmutated copy runs first: if it fails, a "killed" mutant would mean
nothing, so the run stops with exit 1.

  M-sig-skip      the consumer treats every signature as valid
  M-self-digest   the verifier trusts the package's own contract fields (no local anchor)
  M-refuse-all    the consumer refuses everything (a guard that only ever says no is not a guard)

Written by Claude (Opus 5.5) for P-001 under Chad Holland's direction (2026-10-09).
"""
import os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS = ["tests/test_p001_w1.py", "tests/test_p001_w2.py"]

MUTANTS = {
    "M-sig-skip": ("tools/consumer.py",
                   'checks = [("signature", *vp.check_signature(data, a.signature, a.allowed_signers, a.identity)),',
                   'checks = [("signature", True, "MUTANT: not checked"),'),
    "M-self-digest": ("tools/verify_package.py",
                      "    if cid not in TRUSTED_CONTRACTS:\n"
                      "        return False, f\"contract.id {cid!r} is not a locally trusted contract\"\n"
                      "    if dig != TRUSTED_CONTRACTS[cid]:",
                      "    if False:\n"
                      "        return False, f\"contract.id {cid!r} is not a locally trusted contract\"\n"
                      "    if dig != c.get(\"conformance_digest\"):"),
    "M-refuse-all": ("tools/consumer.py",
                     "    if all(ok for _, ok, _ in checks):\n        try:\n            write_state(a.state, new)",
                     "    if False:\n        try:\n            write_state(a.state, new)"),
}


def copy_repo(dst):
    shutil.copytree(ROOT, dst, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))


def run_tests(repo):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    p = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-x", *TESTS],
                       cwd=repo, capture_output=True, text=True, env=env)
    last = (p.stdout.strip().splitlines() or ["(no output)"])[-1]
    return p.returncode, last


def main():
    tmp = tempfile.mkdtemp(prefix="sv_p001_mut_")
    try:
        base = os.path.join(tmp, "baseline")
        copy_repo(base)
        rc, last = run_tests(base)
        print(f"BASELINE        {'PASS' if rc == 0 else 'FAIL'}   {last}")
        if rc != 0:
            print("VERDICT  baseline fails: mutant results would mean nothing")
            return 1
        survived = []
        for name, (rel, old, new) in MUTANTS.items():
            repo = os.path.join(tmp, name)
            copy_repo(repo)
            path = os.path.join(repo, rel)
            with open(path, encoding="utf-8") as fh:
                src = fh.read()
            if src.count(old) != 1:
                print(f"COULD NOT RUN: {name}: patch matches {src.count(old)} times in {rel}, expected 1")
                return 2
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(src.replace(old, new))
            rc, last = run_tests(repo)
            killed = rc != 0
            print(f"{name:<15} {'KILLED' if killed else 'SURVIVED'}   {last}")
            if not killed:
                survived.append(name)
        print(f"VERDICT  {len(MUTANTS) - len(survived)} of {len(MUTANTS)} mutants killed"
              + (f"; SURVIVED: {', '.join(survived)}" if survived else ""))
        return 1 if survived else 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
