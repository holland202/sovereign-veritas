#!/usr/bin/env python3
"""witness.py - append a package to the append-only freshness witness log.

  python tools/witness.py append PACKAGE.json [--log witness/packages.log]

Adds "<seq> <package_sha256>" as the next line, only if the package verifies and its digest is not
already logged. Commit and push the log afterwards: GitHub's copy is the witness. A challenger then
verifies with their OWN pulled copy:
  python tools/verify_package.py PACKAGE.json --witness-log witness/packages.log

What it proves: this package is the newest one the author made public. Not when it was made, and
nothing about packages the author never logged. A force-push to main can rewrite the log, so protect
the branch. Exit: 0 appended | 1 refused | 2 could not run (usage, unreadable package or log)
"""
import json, os, subprocess, sys, importlib.util

sys.dont_write_bytecode = True
DEFAULT_LOG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "witness", "packages.log")


def load_verifier():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "verify_package.py")
    spec = importlib.util.spec_from_file_location("verify_package", path)
    vp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vp)
    return vp


def git_ignores(path):
    """True if git would silently skip this file (e.g. a *.log rule). None if not in a git repo."""
    d = os.path.dirname(os.path.abspath(path)) or "."
    while not os.path.isdir(d):
        d = os.path.dirname(d)
    try:
        p = subprocess.run(["git", "check-ignore", "-q", os.path.abspath(path)], cwd=d,
                           capture_output=True)
    except OSError:
        return None
    return {0: True, 1: False}.get(p.returncode)


def main():
    args = sys.argv[1:]
    log = DEFAULT_LOG
    if "--log" in args:
        i = args.index("--log")
        if i + 1 >= len(args):
            print(__doc__.strip().splitlines()[2]); sys.exit(2)
        log = args[i + 1]
        del args[i:i + 2]
    if len(args) != 2 or args[0] != "append":
        print(__doc__.strip().splitlines()[2]); sys.exit(2)
    vp = load_verifier()
    try:
        with open(args[1], encoding="utf-8") as fh:
            pkg = json.load(fh)
        failed = [n for n, ok, _ in vp.verify(pkg) if not ok]
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        print(f"COULD NOT RUN: {type(exc).__name__}: {exc}"); sys.exit(2)
    if git_ignores(log):
        print(f"REFUSED: git ignores {log}; it would never reach GitHub, so it could not witness anything")
        sys.exit(1)
    if failed:
        print(f"REFUSED: package does not verify ({', '.join(failed)}); only consistent packages are witnessed")
        sys.exit(1)
    if os.path.exists(log):
        try:
            entries = vp.read_witness_log(log)
        except vp.WitnessUnreadable as exc:
            print(f"COULD NOT RUN: witness log unusable: {exc}"); sys.exit(2)
    else:
        os.makedirs(os.path.dirname(os.path.abspath(log)), exist_ok=True)
        with open(log, "w", encoding="utf-8") as fh:
            fh.write(vp.WITNESS_HEADER + "\n")
        entries = []
    digest = pkg["package_sha256"]
    if any(d == digest for _, d in entries):
        print(f"REFUSED: {digest} is already witnessed"); sys.exit(1)
    seq = len(entries) + 1
    with open(log, "a", encoding="utf-8") as fh:
        fh.write(f"{seq} {digest}\n")
        fh.flush()
        os.fsync(fh.fileno())
    print(f"witnessed {seq} {digest}")
    print("now commit and push the log: GitHub's copy is the witness")


if __name__ == "__main__":
    main()
