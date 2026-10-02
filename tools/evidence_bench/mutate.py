#!/usr/bin/env python3
"""Mutation testing: does the test suite notice when the safety logic is broken?

    python mutate.py      # exit 0 = every mutant killed · 1 = a mutant survived · 2 = baseline failed

Each mutant is one small, deliberate bug in the gate, the strict gate, the veto consensus, the
parsers or the statistics. The behavioural tests run against a scratch copy of the bench with
exactly that bug in place; the real files are never touched.

  KILLED    a test failed. Good: the suite constrains that behaviour.
  ERRORED   the mutant broke loading or crashed a test instead of failing an assertion. Counted
            as caught, but reported separately because it says little about the assertions.
  SURVIVED  every test still passed. The suite does not constrain that behaviour: a finding.

The hash checks (tests/test_frozen.py) and the claims checker (tests/test_claims.py) are left
out on purpose. Any edit to gate.py breaks its registered hash, so including them would "kill"
every gate mutant for a reason that has nothing to do with behaviour. An instrument that always
fires is as uninformative as one that never does.

Writes results/mutation_report.json; STATS.md quotes it and verify_claims.py checks the quote.
"""
import json, os, re, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SUITES = ["test_gate_properties", "test_parsers", "test_oracle_and_cases", "test_stats", "test_taxonomy"]

MUTANTS = [  # (id, file, exact text, replacement, the bug in words)
    ("G1", "gate.py", 'return bool(item["verified"]) and item["date"] >= CUTOFF',
     'return bool(item["verified"]) or item["date"] >= CUTOFF', "verified OR fresh is enough to count"),
    ("G2", "gate.py", 'item["date"] >= CUTOFF', 'item["date"] > CUTOFF', "evidence dated on the cutoff day is dropped"),
    ("G3", "gate.py", "if not admissible(it):\n            continue", "if False:\n            continue",
     "inadmissible evidence counts"),
    ("G4", "gate.py", 'STANCE_MAP.get(s, "neutral")', 'STANCE_MAP.get(s, "support")', "an unreadable answer counts as support"),
    ("G5", "gate.py", 'if seen == {"support"}:', 'if "support" in seen:', "conflicting evidence is accepted"),
    ("G6", "gate.py", 'if seen == {"refute"}:', 'if "refute" in seen:', "conflicting evidence is refuted"),
    ("G7", "gate.py", 'return "SUPPORTED"', 'return "NOT_SUPPORTED"', "the gate never accepts anything"),
    ("S1", "gate_strict.py", "if gate.admissible(it) and s not in LABELS:", "if gate.admissible(it) and s is None:",
     "strict gate only catches missing answers, not unreadable ones"),
    ("S2", "gate_strict.py", '        elif "FALSE" in per_item:\n', '        elif False:\n', "strict veto ignores FALSE"),
    ("V1", "consensus_veto.py", 'if any(s == "FALSE" for s in per_item):', 'if all(s == "FALSE" for s in per_item):',
     "a veto needs every extractor to object"),
    ("V2", "consensus_veto.py", 'elif all(s == "TRUE" for s in per_item):', 'elif any(s == "TRUE" for s in per_item):',
     "one extractor's TRUE is enough"),
    ("P1", "parsing.py", 'r"(?<![A-Z_])" + re.escape(lab)', 're.escape(lab)', "no left word boundary: UNSUPPORTED reads as SUPPORTED"),
    ("P2", "parsing.py", "                return None\n            found.add(lab)", "                pass\n            found.add(lab)",
     "negation before a label is ignored"),
    ("P3", "parsing.py", "found = _labels(_norm(text), VERDICTS)\n    if not found or len(found) != 1:",
     "found = _labels(_norm(text), VERDICTS)\n    if not found:", "an answer with two labels picks one"),
    ("P4", "parsing.py", r't = re.sub(r"\bNOT[\s\-_]+SUPPORTED\b", "NOT_SUPPORTED", t)', "t = t",
     "'NOT SUPPORTED' with a space is not recognised"),
    ("T1", "stats.py", "return min(1.0, 2 * tail)", "return min(1.0, tail)", "McNemar p-value one-sided"),
    ("T2", "stats.py", "running = max(running, min(1.0, (m - rank) * pvals[i]))", "running = min(1.0, (m - rank) * pvals[i])",
     "Holm adjustment loses monotonicity"),
]


def run_suites(root):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    p = subprocess.run([sys.executable, "-B", "-m", "unittest", "-q", *SUITES], cwd=os.path.join(root, "tests"),
                       capture_output=True, text=True, timeout=900, env=env)
    return p.returncode, p.stdout + p.stderr


def classify(rc, out):
    if rc == 0:
        return "SURVIVED"
    m = re.search(r"FAILED \(([^)]*)\)", out)
    return "KILLED" if m and "failures=" in m.group(1) else "ERRORED"


def main():
    scratch = tempfile.mkdtemp(prefix="mutate_")
    root = os.path.join(scratch, "bench")
    try:
        shutil.copytree(HERE, root, ignore=shutil.ignore_patterns("__pycache__", "*.server.log", ".git"))
        rc, out = run_suites(root)
        if rc != 0:
            print(out[-3000:])
            print("baseline FAILED: fix the suite before mutating")
            return 2
        report = []
        for mid, f, old, new, what in MUTANTS:
            path = os.path.join(root, f)
            with open(path) as fh:
                original = fh.read()
            n = original.count(old)
            if n != 1:
                print(f"{mid}: target text found {n} times in {f}; mutant definition is stale")
                return 2
            with open(path, "w") as fh:
                fh.write(original.replace(old, new))
            try:
                rc, out = run_suites(root)
            finally:
                with open(path, "w") as fh:
                    fh.write(original)
            outcome = classify(rc, out)
            first_fail = next(iter(re.findall(r"^(?:FAIL|ERROR): (\w+)", out, re.M)), None)
            report.append({"id": mid, "file": f, "bug": what, "outcome": outcome, "first_failing_test": first_fail})
            print(f"{mid:3s} {outcome:9s} {f:18s} {what}" + (f"  [{first_fail}]" if first_fail else ""), flush=True)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    counts = {k: sum(r["outcome"] == k for r in report) for k in ("KILLED", "ERRORED", "SURVIVED")}
    summary = {"mutants": len(report), **counts, "suites": SUITES, "report": report}
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    with open(os.path.join(HERE, "results", "mutation_report.json"), "w") as fh:
        json.dump(summary, fh, indent=2)
    print(f"mutation: {len(report)} mutants, {counts['KILLED']} killed, {counts['ERRORED']} errored, "
          f"{counts['SURVIVED']} survived")
    return 1 if counts["SURVIVED"] else 0


if __name__ == "__main__":
    sys.exit(main())
