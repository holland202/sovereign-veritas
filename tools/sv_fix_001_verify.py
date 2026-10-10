#!/usr/bin/env python3
"""SV-FIX-001 verification driver: R1-R6, R8, R9 of docs/SV_FIX_001_PREREG.md (R7 is CI, recorded separately).

Written by Claude (Opus 5.5) at Chad Holland's direction; committed before it was run. Not reviewed line
by line by Chad. One execution unless the owner states otherwise. Everything is in memory, on FakeVehicle,
or offline package verification; nothing touches a real file named in a case, a vehicle or a network.

  python -I tools/sv_fix_001_verify.py            # writes results/sv_fix_001/ (refuses to overwrite)

R1-R3  tools/sv_fix_001_probe.py (SV-ATTACK-001's probe with only the two changed target hashes updated)
R4     fixed verify_package.py on SV-ATTACK-001 run1's divergent B1.json        -> must exit 1
R5     fixed verify_package.py on run1's honest B0.json                          -> must exit 0
R6     unfixed (438e6d5) and fixed verify_package.py on the 24 committed vehicle packages -> same exit codes
R8     mutant workflow.py (executes the caller's object again) in a temporary copy -> probe Q1 must FAIL
R9     mutant verify_package.py (F2 call removed) on R4's package                 -> must exit 0
Mutants live only in a temporary directory; their diffs are recorded, never committed as code.
"""
import difflib, hashlib, json, os, platform, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "results", "sv_fix_001")
RUN1 = os.path.join(ROOT, "results", "sv_attack_001", "run1", "packages")
BASE_COMMIT = "438e6d54e51fec8ad0a8e60664747e7402a45321"
LOG = []


def say(s=""):
    print(s)
    LOG.append(s)


def sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def run(cmd, cwd=ROOT):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=600)
    return {"cmd": [os.path.relpath(c, ROOT) if os.path.isabs(c) and c.startswith(ROOT) else c for c in cmd],
            "exit": p.returncode, "stdout": p.stdout.splitlines(), "stderr": p.stderr.splitlines()[-8:]}


def verify(verifier, pkg):
    r = run([sys.executable, "-I", verifier, pkg])
    return {"exit": r["exit"], "verdict": r["stdout"][-1] if r["stdout"] else "",
            "failed": [l for l in r["stdout"] if l.startswith("FAIL")]}


def regression_set():
    files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    out = []
    for f in files:
        if f.startswith("results/") or not f.endswith(".json"):
            continue
        if not (os.path.basename(f).startswith("sv_package_") or f.startswith("evidence/attacks/issue-005/")):
            continue
        with open(os.path.join(ROOT, f), encoding="utf-8", errors="replace") as fh:
            if "vehicle_command_check" in fh.read():
                out.append(f)
    return sorted(out)


def mutate(text, old, new, what):
    if text.count(old) != 1:
        raise SystemExit(f"COULD NOT BUILD MUTANT {what}: anchor found {text.count(old)} times")
    return text.replace(old, new)


def main():
    if os.path.exists(OUT):
        print(f"REFUSED: {OUT} exists; every run's evidence is kept")
        return 3
    os.makedirs(OUT)
    fixed_vp = os.path.join(ROOT, "tools", "verify_package.py")
    rec = {"python": platform.python_version(), "platform": platform.platform(),
           "driver_sha256": sha(os.path.abspath(__file__)),
           "probe_sha256": sha(os.path.join(ROOT, "tools", "sv_fix_001_probe.py")),
           "workflow_sha256": sha(os.path.join(ROOT, "sovereign_veritas", "workflow.py")),
           "verify_package_sha256": sha(fixed_vp)}
    say(f"SV-FIX-001 verification  python={rec['python']}  platform={rec['platform']}")
    for k in ("driver_sha256", "probe_sha256", "workflow_sha256", "verify_package_sha256"):
        say(f"{k:22s} {rec[k]}")

    # R1-R3: the probe on the fixed code
    r1 = run([sys.executable, "-I", os.path.join(ROOT, "tools", "sv_fix_001_probe.py"), "--label", "run1", "--out", OUT])
    rec["R1_R3_probe"] = r1
    say("\n== R1-R3 probe (verbatim)")
    for l in r1["stdout"]:
        say("  " + l)
    probe = {}
    rj = os.path.join(OUT, "run1", "run.json")
    if os.path.exists(rj):
        with open(rj, encoding="utf-8") as fh:
            probe = json.load(fh)
    pv = probe.get("verdicts", {})

    # R4, R5
    r4 = verify(fixed_vp, os.path.join(RUN1, "B1.json"))
    r5 = verify(fixed_vp, os.path.join(RUN1, "B0.json"))
    rec["R4"], rec["R5"] = r4, r5
    say(f"\n== R4 fixed verifier on run1 B1.json (divergent): exit {r4['exit']}  {r4['verdict']}")
    for l in r4["failed"]:
        say("  " + l)
    say(f"== R5 fixed verifier on run1 B0.json (honest):    exit {r5['exit']}  {r5['verdict']}")

    tmp = tempfile.mkdtemp(prefix="sv_fix_001_")
    try:
        # R6: unfixed verifier from the base commit, as a standalone copy
        old_vp = os.path.join(tmp, "verify_package_438e6d5.py")
        with open(old_vp, "w", encoding="utf-8") as fh:
            fh.write(subprocess.run(["git", "show", f"{BASE_COMMIT}:tools/verify_package.py"], cwd=ROOT,
                                    capture_output=True, text=True, check=True).stdout)
        pkgs = regression_set()
        rows, changed = [], []
        for p in pkgs:
            a = verify(old_vp, os.path.join(ROOT, p))["exit"]
            b = verify(fixed_vp, os.path.join(ROOT, p))["exit"]
            rows.append({"package": p, "unfixed_exit": a, "fixed_exit": b})
            if a != b:
                changed.append(p)
        rec["R6"] = {"n": len(pkgs), "rows": rows, "changed": changed}
        say(f"\n== R6 regression: {len(pkgs)} packages, exit codes changed: {len(changed)}")
        for r in rows:
            say(f"  {r['unfixed_exit']} -> {r['fixed_exit']}  {r['package']}")

        # R8: mutant workflow (executes the caller's object again), in a temporary copy of the needed tree
        tree = os.path.join(tmp, "r8_tree")
        shutil.copytree(os.path.join(ROOT, "sovereign_veritas"), os.path.join(tree, "sovereign_veritas"),
                        ignore=shutil.ignore_patterns("__pycache__"))
        os.makedirs(os.path.join(tree, "tools"))
        for t in ("vehicle_action.py", "verify_package.py", "sv_fix_001_probe.py"):
            shutil.copy(os.path.join(ROOT, "tools", t), os.path.join(tree, "tools", t))
        wf = os.path.join(tree, "sovereign_veritas", "workflow.py")
        with open(wf, encoding="utf-8") as fh:
            orig = fh.read()
        mut = mutate(orig, "self.executor.execute(decided_action)", "self.executor.execute(action)", "R8")
        with open(wf, "w", encoding="utf-8") as fh:
            fh.write(mut)
        mut_sha = sha(wf)
        pr = os.path.join(tree, "tools", "sv_fix_001_probe.py")
        with open(pr, encoding="utf-8") as fh:
            ptxt = fh.read()
        with open(pr, "w", encoding="utf-8") as fh:
            fh.write(mutate(ptxt, rec["workflow_sha256"], mut_sha, "R8 probe hash"))
        r8 = run([sys.executable, "-I", pr, "--label", "R8", "--out", os.path.join(tmp, "r8_out")], cwd=tree)
        r8v = {}
        r8j = os.path.join(tmp, "r8_out", "R8", "run.json")
        if os.path.exists(r8j):
            with open(r8j, encoding="utf-8") as fh:
                r8v = json.load(fh).get("verdicts", {})
        rec["R8"] = {"mutant_workflow_sha256": mut_sha, "diff": list(difflib.unified_diff(
            orig.splitlines(), mut.splitlines(), "workflow.py", "workflow.py (R8 mutant)", lineterm="")),
            "probe_stdout": r8["stdout"], "verdicts": r8v}
        say(f"\n== R8 mutant workflow (sha256 {mut_sha}): probe Q1 {r8v.get('Q1')}")
        for l in r8["stdout"]:
            if l.startswith(("A1", "B1", "VERDICT", "controls")):
                say("  " + l)

        # R9: mutant verifier without the F2 call
        with open(fixed_vp, encoding="utf-8") as fh:
            vtxt = fh.read()
        anchor = ("broken += sent_command_problems(m.get(\"backend\"), act.get(\"requested\"), "
                  "act.get(\"parameters\") or {}, sent)")
        mvp = os.path.join(tmp, "verify_package_R9.py")
        mv = mutate(vtxt, anchor, "pass  # R9 mutant: F2 removed", "R9")
        with open(mvp, "w", encoding="utf-8") as fh:
            fh.write(mv)
        r9 = verify(mvp, os.path.join(RUN1, "B1.json"))
        rec["R9"] = dict(r9, diff=list(difflib.unified_diff(vtxt.splitlines(), mv.splitlines(), "verify_package.py",
                                                             "verify_package.py (R9 mutant)", lineterm="")))
        say(f"\n== R9 mutant verifier (F2 removed) on run1 B1.json: exit {r9['exit']}  {r9['verdict']}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # verdicts (R7 is CI plus the local test comparison, recorded in the results document)
    controls = all(str(pv.get(c)) == "True" for c in ("C1", "C2", "C4")) and str(probe.get("C3")) == "True"
    f1 = ("PASS" if pv.get("Q1") == "PASS" and controls and rec["R8"]["verdicts"].get("Q1") == "FAIL"
          else "FAIL" if pv.get("Q1") == "FAIL" else "INCONCLUSIVE")
    f2 = ("PASS" if r4["exit"] == 1 and r5["exit"] == 0 and not changed and r9["exit"] == 0
          else "FAIL" if r4["exit"] == 0 or r5["exit"] != 0 or changed else "INCONCLUSIVE")
    rec["verdicts"] = {"probe": pv, "F1_excluding_R7": f1, "F2": f2}
    say(f"\nVERDICT  F1 {f1} (R7 = CI, judged separately)  |  F2 {f2}  |  probe Q2 {pv.get('Q2')}  Q3(B1) {pv.get('Q3')}")
    say("R3: B1's package now verifies because nothing diverges; that is not evidence for F2 (R4 is).")

    with open(os.path.join(OUT, "verify.json"), "w", encoding="utf-8") as fh:
        json.dump(rec, fh, indent=1, sort_keys=True)
    with open(os.path.join(OUT, "verify.log"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(LOG) + "\n")
    sums = []
    for base, _, files in sorted(os.walk(OUT)):
        for f in sorted(files):
            if f != "SHA256SUMS":
                p = os.path.join(base, f)
                sums.append(f"{sha(p)}  {os.path.relpath(p, OUT)}")
    with open(os.path.join(OUT, "SHA256SUMS"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(sums) + "\n")
    print(f"evidence: {OUT}  SHA256SUMS sha256 {sha(os.path.join(OUT, 'SHA256SUMS'))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
