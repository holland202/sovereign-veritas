#!/usr/bin/env python3
"""STD-2 (docs/STD2_PREREG.md): run OASB under its default adapter (ARP) and three non-product adapters, then
judge P2-P5 from vitest's JSON reports.

  python tools/std2_run.py /path/to/oasb            run all four, judge
  python tools/std2_run.py /path/to/oasb --sabotage   pretend every adapter result equals ARP's (P3/P5 must refute)

Exit codes: 0 = judged (predictions may hold or be refuted); 1 = a sabotage run was not caught; 2 = could not run.
"""
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ADAPTERS = {"silent": "silent.cjs", "echo": "echo.cjs", "flag": "flag.cjs"}


def could_not_run(msg):
    print("COULD NOT RUN", msg)
    sys.exit(2)


def vitest(root, adapter_path, out):
    env = dict(os.environ)
    if adapter_path:
        env["OASB_ADAPTER"] = adapter_path
    else:
        env.pop("OASB_ADAPTER", None)
    subprocess.run(["npx", "vitest", "run", "--reporter=json", f"--outputFile={out}"], cwd=root, env=env,
                   capture_output=True, text=True, timeout=1800)
    if not os.path.isfile(out):
        could_not_run(f"vitest wrote no report for {adapter_path or 'arp'}")
    d = json.load(open(out))
    tests, file_errors = {}, {}
    for f in d["testResults"]:
        rel = os.path.relpath(f["name"], root).replace(os.sep, "/")
        if not f["assertionResults"]:
            file_errors[rel] = (f.get("message") or "")[:200]
        for a in f["assertionResults"]:
            tests[(rel, a["fullName"])] = a["status"]
    return d, tests, file_errors


def classify(root):
    created, direct = set(), set()
    for dp, _, fs in os.walk(os.path.join(root, "src")):
        for fn in fs:
            if fn.endswith(".test.ts"):
                p = os.path.join(dp, fn)
                rel = os.path.relpath(p, root).replace(os.sep, "/")
                src = open(p, encoding="utf-8").read()
                if "createAdapter" in src:
                    created.add(rel)
                elif "new ArpWrapper" in src:
                    direct.add(rel)
    return created, direct


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        could_not_run(__doc__)
    root = os.path.abspath(args[0])
    sabotage = "--sabotage" in sys.argv
    created, direct = classify(root)
    print(f"FILES    createAdapter {len(created)}, ArpWrapper-only {len(direct)}")
    outdir = os.path.join(HERE, "..", "results", "std2")
    os.makedirs(outdir, exist_ok=True)

    base_d, base, base_err = vitest(root, None, os.path.join(outdir, "arp.json"))
    print(f"ARP      total {base_d['numTotalTests']} passed {base_d['numPassedTests']} failed {base_d['numFailedTests']} "
          f"skipped {base_d['numPendingTests']}  load errors {len(base_err)}")
    runs = {}
    for name, fn in ADAPTERS.items():
        d, t, err = vitest(root, os.path.join(HERE, "std2_adapters", fn), os.path.join(outdir, f"{name}.json"))
        if sabotage:
            t = dict(base)
        runs[name] = t
        print(f"{name.upper():8s} total {d['numTotalTests']} passed {d['numPassedTests']} failed {d['numFailedTests']} "
              f"skipped {d['numPendingTests']}  load errors {len(err)} {sorted(err)[:3]}")

    # P2: ArpWrapper-only files give identical results under every adapter.
    direct_keys = [k for k in base if k[0] in direct]
    changed = sorted({(n, k[0], k[1], base[k], runs[n].get(k)) for n in runs for k in direct_keys if runs[n].get(k) != base[k]})
    p2 = not changed
    print(f"{'HELD' if p2 else 'REFUTED':8s} P2  {len(direct_keys)} tests in {len(direct)} ArpWrapper-only files; "
          f"{len(changed)} (adapter, test) results differ from ARP")
    for c in changed[:10]:
        print("           ", c)

    # P3: each createAdapter file has >= 1 failing test under silent.
    def failing_files(run, files):
        return {k[0] for k, s in run.items() if k[0] in files and s == "failed"}
    silent_fail = failing_files(runs["silent"], created)
    never = sorted(created - silent_fail)
    p3 = not never
    print(f"{'HELD' if p3 else 'REFUTED':8s} P3  createAdapter files with >=1 failure under silent: {len(silent_fail)} of {len(created)}")
    for f in never:
        st = {}
        for k, s in runs["silent"].items():
            if k[0] == f:
                st[s] = st.get(s, 0) + 1
        print(f"            no failure under silent: {f}  {st}")

    # P4: >= 1 createAdapter test passes under echo.
    echo_pass = sorted(k for k, s in runs["echo"].items() if k[0] in created and s == "passed")
    p4 = len(echo_pass) > 0
    print(f"{'HELD' if p4 else 'REFUTED':8s} P4  createAdapter tests passing under echo: {len(echo_pass)} of "
          f"{sum(1 for k in runs['echo'] if k[0] in created)}")
    silent_pass = sorted(k for k, s in runs["silent"].items() if k[0] in created and s == "passed")
    print(f"         (for comparison) createAdapter tests passing under silent: {len(silent_pass)}")

    # P5: >= 1 baseline test fails under flag.
    flag_base_fail = sorted(k for k, s in runs["flag"].items() if k[0].startswith("src/baseline/") and s == "failed")
    p5 = len(flag_base_fail) > 0
    print(f"{'HELD' if p5 else 'REFUTED':8s} P5  baseline tests failing under flag-everything: {len(flag_base_fail)}")
    for k in flag_base_fail:
        print("           ", k[0], "|", k[1])

    if sabotage:
        caught = not (p3 and p5)
        print("SABOTAGE", "caught (P3 or P5 refuted)" if caught else "NOT CAUGHT")
        sys.exit(0 if caught else 1)
    with open(os.path.join(outdir, "passing_without_detection.txt"), "w") as fh:
        for k in silent_pass:
            fh.write(f"silent\t{k[0]}\t{k[1]}\n")
        for k in echo_pass:
            fh.write(f"echo\t{k[0]}\t{k[1]}\n")


if __name__ == "__main__":
    main()
