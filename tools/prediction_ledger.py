#!/usr/bin/env python3
"""Prediction ledger: every registered-prediction verdict line in results/, as one table.

  python tools/prediction_ledger.py OUT_DIR     write OUT_DIR/ledger.jsonl and OUT_DIR/summary.json
  python tools/prediction_ledger.py --selftest  exit 0 only if the parser finds what it must and nothing else

It reads the raw outputs committed under results/ and records each line that states a prediction's outcome, in either
form the harnesses print ("P3  HELD" or "HELD    P3"). It invents nothing: each row carries its file, line number,
the line itself and the commit it was read at. It does not judge whether a prediction was right, and an arm whose
file name says sabotage is expected to refute things. Files that print a VERDICT line but yield no rows are listed in
the summary, so what the parser missed is visible. Standard library only.
"""
import json, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ID = r"[A-Z]{1,4}(?:-[A-Z]{1,4})?[0-9]+[a-z]?"
LINE = re.compile(rf"^\s*(?:(?P<id>{ID})\s+(?P<o>HELD|REFUTED)\b|(?P<o2>HELD|REFUTED|NOT RUN)\s+(?P<id2>{ID})\b)")
# Arm is read from the file name only, so it is a hint, not a fact: "unclassified" means the name says nothing.
ARMS = (("sabotage", "sabotage"), ("mutant", "mutant"), ("noop", "control"), ("flip", "control"), ("pre_", "baseline"),
        ("prefix", "baseline"))


def arm_of(path):
    name = os.path.basename(path).lower()
    return next((arm for key, arm in ARMS if key in name), "unclassified")


def parse(text, path):
    rows = []
    for n, line in enumerate(text.splitlines(), 1):
        m = LINE.match(line)
        if m:
            rows.append({"id": m["id"] or m["id2"], "outcome": m["o"] or m["o2"], "line": n, "raw": line.strip()[:300],
                         "file": path, "experiment": path.split("/")[1] if path.count("/") >= 2 else path,
                         "arm": arm_of(path)})
    return rows


def selftest():
    text = ("  P1  HELD\nHELD    P2  {...}\nREFUTED P3\n  KC-P4 HELD\nNOT RUN P5  (Android)\n"
            "  E9  HELDOUT\nheld P6\nVERDICT 3 of 5 as registered\n  P7  REFUTED\n")
    got = [(r["id"], r["outcome"]) for r in parse(text, "results/x/run_sabotage.txt")]
    want = [("P1", "HELD"), ("P2", "HELD"), ("P3", "REFUTED"), ("KC-P4", "HELD"), ("P5", "NOT RUN"), ("P7", "REFUTED")]
    arm = parse("P1 HELD\n", "results/x/run_sabotage.txt")[0]["arm"]
    ok = got == want and arm == "sabotage" and parse("P1 HELD\n", "results/x/run.txt")[0]["arm"] == "unclassified"
    print(f"self-test: parsed {got}; sabotage arm detected: {arm == 'sabotage'} -> {'PASS' if ok else 'FAIL'}")
    return ok


def main(argv):
    if argv[:1] == ["--selftest"]:
        return 0 if selftest() else 1
    if len(argv) != 1:
        print(__doc__)
        return 2
    if not selftest():
        return 1
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    files = subprocess.run(["git", "ls-files", "results"], cwd=ROOT, capture_output=True, text=True).stdout.split()
    rows, missed = [], []
    for f in sorted(p for p in files if p.endswith(".txt")):
        text = open(os.path.join(ROOT, f), encoding="utf-8", errors="replace").read()
        found = parse(text, f)
        for r in found:
            r["commit"] = commit
        rows += found
        if not found and re.search(r"^VERDICT", text, re.M):
            missed.append(f)
    os.makedirs(argv[0], exist_ok=True)
    with open(os.path.join(argv[0], "ledger.jsonl"), "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, sort_keys=True, ensure_ascii=False) + "\n")
    count = lambda arm: {o: sum(r["arm"] == arm and r["outcome"] == o for r in rows) for o in ("HELD", "REFUTED", "NOT RUN")}  # noqa: E731
    summary = {"commit": commit, "rows": len(rows), "files_read": sum(p.endswith(".txt") for p in files),
               "files_with_rows": len({r["file"] for r in rows}), "experiments": len({r["experiment"] for r in rows}),
               "by_arm": {a: count(a) for a in sorted({r["arm"] for r in rows})},
               "verdict_files_without_rows": missed}
    with open(os.path.join(argv[0], "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=1, sort_keys=True)
        fh.write("\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "verdict_files_without_rows"}, sort_keys=True))
    print(f"verdict files the parser found no rows in: {len(missed)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
