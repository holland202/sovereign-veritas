#!/usr/bin/env python3
"""STD-3 (docs/STD3_PREREG.md): rerun the frozen STD-2 adapters on OASB main and judge P1-P6.

  python tools/std3_run.py /path/to/oasb              run ARP + silent/echo/flag, judge
  python tools/std3_run.py /path/to/oasb --sabotage   replace adapter results with ARP's (P2 and P3 must refute)
  --cached                                            judge the saved reports in results/std3/, run nothing
  --expect-scenarios=N                                refuse to judge unless exactly N scenario tests ran under ARP

The judge refuses (exit 2) when the four reports do not hold the same non-empty set of test keys, or a key repeats.
Report file names are keyed from their "src/" segment on, so saved reports can be judged from another checkout.

Exit codes: 0 = judged (predictions may hold or be refuted); 1 = sabotage not caught; 2 = could not run.
"""
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ADAPTERS = {"silent": "silent.cjs", "echo": "echo.cjs", "flag": "flag.cjs"}
SCENARIO = ("src/atomic/", "src/baseline/", "src/integration/", "src/e2e/")
BL001 = "src/baseline/BL-001.normal-agent-profile.test.ts"
TAGS = {}
UNDECLARED = ("connection-burst-detection", "http-response-scanning", "baseline-persistence")


def could_not_run(msg):
    print("COULD NOT RUN", msg)
    sys.exit(2)


def vitest(root, adapter_path, out, cached):
    if not (cached and os.path.isfile(out)):
        env = dict(os.environ)
        if adapter_path:
            env["OASB_ADAPTER"] = adapter_path
        else:
            env.pop("OASB_ADAPTER", None)
        if os.path.exists(out):
            os.remove(out)
        subprocess.run(["npx", "vitest", "run", "--reporter=json", f"--outputFile={out}"], cwd=root, env=env,
                       capture_output=True, text=True, timeout=3600)
    if not os.path.isfile(out):
        could_not_run(f"vitest wrote no report for {adapter_path or 'arp'}")
    d = json.load(open(out))
    tests, msgs, file_errors, dups = {}, {}, {}, []
    for f in d["testResults"]:
        name = f["name"].replace(os.sep, "/")
        m = re.search(r"(?:^|/)(src/.*)$", name)
        rel = m.group(1) if m else os.path.relpath(f["name"], root).replace(os.sep, "/")
        if not f["assertionResults"]:
            file_errors[rel] = (f.get("message") or "")[:200]
        for a in f["assertionResults"]:
            # describeWithCapability / requireCapability append " [requires: ...]" to a skipped block's title;
            # strip it so a test keeps one key across adapters, and remember the tag.
            full = a["fullName"]
            tag = re.findall(r" \[requires: ([^\]]*)\]", full)
            k = (rel, re.sub(r" \[requires: [^\]]*\]", "", full))
            if tag:
                TAGS.setdefault(adapter_path or "arp", {})[k] = ", ".join(tag)
            if k in tests:
                dups.append(k)
            tests[k] = a["status"]
            msgs[k] = " ".join(a.get("failureMessages") or [])[:400]
    if dups:
        could_not_run(f"{len(dups)} repeated test keys in {out}, e.g. {dups[0]}")
    return d, tests, msgs, file_errors


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        could_not_run(__doc__)
    root = os.path.abspath(args[0])
    sabotage = "--sabotage" in sys.argv
    cached = sabotage or "--cached" in sys.argv  # --cached: judge the saved reports, run nothing
    outdir = os.path.join(HERE, "..", "results", "std3")
    os.makedirs(outdir, exist_ok=True)
    head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=root, capture_output=True, text=True).stdout.strip()
    print(f"OASB     {head}")

    bd, base, base_msg, berr = vitest(root, None, os.path.join(outdir, "arp.json"), cached)
    print(f"ARP      total {bd['numTotalTests']} passed {bd['numPassedTests']} failed {bd['numFailedTests']} "
          f"skipped {bd['numPendingTests']}  load errors {len(berr)} {sorted(berr)[:3]}")
    runs, run_msg = {}, {}
    for name, fn in ADAPTERS.items():
        d, t, m, err = vitest(root, os.path.join(HERE, "std2_adapters", fn), os.path.join(outdir, f"{name}.json"), cached)
        if set(t) != set(base):
            could_not_run(f"{name} report and ARP report hold different test keys "
                          f"({len(set(t) - set(base))} only in {name}, {len(set(base) - set(t))} only in ARP)")
        if sabotage:
            t, m = dict(base), dict(base_msg)
        runs[name], run_msg[name] = t, m
        nf = sum(1 for k, s in t.items() if s == "failed" and "is not a function" in m.get(k, ""))
        print(f"{name.upper():8s} total {d['numTotalTests']} passed {d['numPassedTests']} failed {d['numFailedTests']} "
              f"skipped {d['numPendingTests']}  load errors {len(err)} {sorted(err)[:3]}  M1 not-a-function {nf}")

    # P1: under ARP, no failure outside src/e2e/.
    arp_fail = sorted(k for k, s in base.items() if s == "failed")
    p1 = not [k for k in arp_fail if not k[0].startswith("src/e2e/")]
    print(f"{'HELD' if p1 else 'REFUTED':8s} P1  ARP failures outside e2e: "
          f"{sum(1 for k in arp_fail if not k[0].startswith('src/e2e/'))}; e2e failures: "
          f"{sum(1 for k in arp_fail if k[0].startswith('src/e2e/'))}")
    for k in arp_fail:
        print("           ARP failed:", k[0], "|", k[1])

    # P2: at most 5% of scenario tests (not skipped under ARP) do not move.
    denom = [k for k, s in base.items() if k[0].startswith(SCENARIO) and s != "skipped"]
    if not denom:
        could_not_run("no scenario tests found in the ARP report")
    expect = [a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--expect-scenarios=")]
    if expect and len(denom) != int(expect[0]):
        could_not_run(f"{len(denom)} scenario tests ran under ARP, expected {expect[0]}")
    print(f"INVENTORY {len(base)} test keys, identical in all four reports; {len(denom)} scenario tests ran under ARP")
    still = sorted(k for k in denom if all(runs[n].get(k) == base[k] for n in runs))
    share = len(still) / len(denom) if denom else 1.0
    p2 = bool(denom) and share <= 0.05
    print(f"{'HELD' if p2 else 'REFUTED':8s} P2  scenario tests not moving: {len(still)} of {len(denom)} ({100 * share:.1f}%)")
    for k in still:
        print("           not moving:", base[k], "|", k[0], "|", k[1])

    # P3-P5: BL-001.
    def bl(name):
        return [runs[name][k] for k in sorted(runs[name]) if k[0] == BL001]
    blf, bls, ble = bl("flag"), bl("silent"), bl("echo")
    p3 = "failed" in blf
    p4 = "failed" in bls
    p5 = len(ble) == 3 and all(s == "passed" for s in ble)
    print(f"{'HELD' if p3 else 'REFUTED':8s} P3  BL-001 under flag   {blf}")
    print(f"{'HELD' if p4 else 'REFUTED':8s} P4  BL-001 under silent {bls}")
    print(f"{'HELD' if p5 else 'REFUTED':8s} P5  BL-001 under echo   {ble}")
    print(f"         (for comparison) BL-001 under ARP {[base[k] for k in sorted(base) if k[0] == BL001]}")

    # P6: tests in blocks gated on an undeclared capability are skipped under all three, not under ARP.
    gated_files = set()
    for dp, _, fs in os.walk(os.path.join(root, "src")):
        for fn in fs:
            if fn.endswith(".test.ts"):
                p = os.path.join(dp, fn)
                src = open(p, encoding="utf-8").read()
                if any(f"'{c}'" in src for c in UNDECLARED):
                    gated_files.add(os.path.relpath(p, root).replace(os.sep, "/"))
    named = [k for ap, tg in TAGS.items() if ap != "arp" for k, t in tg.items() if any(c in t for c in UNDECLARED)]
    cand = sorted({k for k in base if k[0] in gated_files and k[0].startswith(SCENARIO)})
    skipped_all = [k for k in cand if all(runs[n].get(k) == "skipped" for n in runs)]
    bad = [k for k in skipped_all if base.get(k) == "skipped"]
    p6 = bool(named) and not bad
    print(f"{'HELD' if p6 else 'REFUTED':8s} P6  tests carrying a [requires: <undeclared>] tag under the adapters: "
          f"{len(set(named))}; in gated files, skipped under all three: {len(skipped_all)} of {len(cand)}; "
          f"of those also skipped under ARP: {len(bad)}")
    for k in sorted(set(named))[:10]:
        print("           gated:", k[0], "|", k[1])

    if cached and not sabotage:
        return
    if sabotage:
        caught = not (p2 and p3)
        print("SABOTAGE", "caught (P2 or P3 refuted)" if caught else "NOT CAUGHT")
        sys.exit(0 if caught else 1)
    with open(os.path.join(outdir, "not_moving.tsv"), "w") as fh:
        for k in still:
            fh.write(f"{base[k]}\t{k[0]}\t{k[1]}\n")


if __name__ == "__main__":
    main()
