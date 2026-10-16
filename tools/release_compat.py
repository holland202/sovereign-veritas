#!/usr/bin/env python3
"""release_compat.py - does a new verify_package.py change any committed package's verdict?

Runs the verifier at an old git revision and the working-tree verifier, both with --legacy, on every
committed JSON file whose schema is sv.package/*, and prints one line per package plus a tally.

  python tools/release_compat.py v0.2.0          # old revision (tag or SHA) to compare against

Exit 0: compared (differences are listed, not judged) | 2: could not look (no git, unknown revision, no packages).
Stdlib only. Read-only: writes the old verifier to a temporary directory, nothing in the repository.
"""
import os, re, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def verdict(verifier, pkg):
    p = subprocess.run([sys.executable, "-I", verifier, "--legacy", pkg], cwd=ROOT, capture_output=True, text=True)
    line = next((l for l in p.stdout.splitlines() if l.startswith("VERDICT")), "(no VERDICT line)")
    return p.returncode, re.sub(r"\s+", " ", line)


def main():
    if len(sys.argv) != 2:
        print("usage: release_compat.py <old-revision>", file=sys.stderr)
        return 2
    old = sys.argv[1]
    try:
        src = subprocess.run(["git", "show", f"{old}:tools/verify_package.py"], cwd=ROOT, capture_output=True,
                             text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError) as e:
        print(f"COULD_NOT_LOOK: cannot read tools/verify_package.py at {old}: {type(e).__name__}", file=sys.stderr)
        return 2
    pkgs = []
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = sorted(d for d in dirs if d not in (".git", "__pycache__") and not d.startswith("."))
        for f in sorted(files):
            if f.endswith(".json"):
                path = os.path.join(base, f)
                try:
                    head = open(path, encoding="utf-8", errors="replace").read()
                except OSError:
                    continue
                if '"sv.package/' in head:
                    pkgs.append(os.path.relpath(path, ROOT))
    if not pkgs:
        print("COULD_NOT_LOOK: no sv.package files found", file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory() as tmp:
        old_v = os.path.join(tmp, "verify_package_old.py")
        open(old_v, "w", encoding="utf-8").write(src)
        new_v = os.path.join(ROOT, "tools", "verify_package.py")
        tally, changed = {}, []
        for pkg in pkgs:
            (ea, va), (eb, vb) = verdict(old_v, pkg), verdict(new_v, pkg)
            tally[f"{ea}->{eb}"] = tally.get(f"{ea}->{eb}", 0) + 1
            if ea != eb or va != vb:
                changed.append(f"CHANGED  {pkg}\n  {old}: exit {ea}  {va}\n  new:    exit {eb}  {vb}")
    print(f"packages compared: {len(pkgs)} (old = {old}, new = working tree, both with --legacy)")
    for k in sorted(tally):
        print(f"  exit {k}: {tally[k]}")
    print(f"verdict changed: {len(changed)}")
    for c in changed:
        print(c)
    return 0


if __name__ == "__main__":
    sys.exit(main())
