#!/usr/bin/env python3
"""claims_matrix.py - check docs/claims.json and render docs/CLAIMS_MATRIX.md (claim -> test -> evidence -> independence).

  python tools/claims_matrix.py           # check, then write docs/CLAIMS_MATRIX.md; exit 0 iff the matrix is valid
  python tools/claims_matrix.py --check   # check, and also exit 1 if docs/CLAIMS_MATRIX.md is not what this would write

Checks:
- a closed field set per claim, and unique ids;
- status and oracle drawn from the directive's vocabulary;
- every evidence path exists;
- every test reference names an existing file and a `def test_...` in it;
- a claim at MEASURED or stronger names evidence, a test or result, and how it was shown able to fail;
- a REFUTED or NOT_SUPPORTED claim names its evidence.

The checker does not judge whether a claim is true. It keeps the matrix from pointing at things that do not exist.
Stdlib only.
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE, OUT = os.path.join(ROOT, "docs", "claims.json"), os.path.join(ROOT, "docs", "CLAIMS_MATRIX.md")
STATUSES = ("OBSERVED", "MEASURED", "REPRODUCED", "INDEPENDENTLY_REPRODUCED", "MODEL_DEPENDENT", "NOT_TESTED",
            "NOT_SUPPORTED", "REFUTED", "SPECULATIVE", "NOT_ESTABLISHED")
STRONG = {"MEASURED", "REPRODUCED", "INDEPENDENTLY_REPRODUCED"}
ORACLES = ("INDEPENDENT ORACLE", "PARTIALLY INDEPENDENT", "DERIVED ORACLE", "CIRCULAR ORACLE", "NOT ESTABLISHED")
FIELDS = {"id", "claim", "source", "status", "tests", "evidence", "oracle", "independence", "can_fail", "gap"}


def problems(doc, root=ROOT):
    """Every problem found in a claims document (a list of strings; empty means valid)."""
    found, seen = [], set()
    if doc.get("schema") != "sv.claims/1":
        found.append(f"schema {doc.get('schema')!r}")
    for c in doc.get("claims", []):
        cid = c.get("id", "?")
        if set(c) != FIELDS:
            found.append(f"{cid}: fields missing {sorted(FIELDS - set(c))}, unknown {sorted(set(c) - FIELDS)}")
            continue
        if cid in seen:
            found.append(f"{cid}: duplicate id")
        seen.add(cid)
        if c["status"] not in STATUSES:
            found.append(f"{cid}: status {c['status']!r} is not one of {STATUSES}")
        if c["oracle"] not in ORACLES:
            found.append(f"{cid}: oracle {c['oracle']!r} is not one of {ORACLES}")
        for path in c["evidence"]:
            if not os.path.exists(os.path.join(root, path)):
                found.append(f"{cid}: evidence {path} does not exist")
        for ref in c["tests"]:
            path, _, name = ref.partition("::")
            full = os.path.join(root, path)
            if not os.path.isfile(full):
                found.append(f"{cid}: test file {path} does not exist")
            elif name and not re.search(rf"^def {re.escape(name)}\(", open(full, encoding="utf-8").read(), re.M):
                found.append(f"{cid}: {path} has no test {name}")
        if c["status"] in STRONG and not (c["evidence"] and (c["tests"] or c["evidence"]) and c["can_fail"].strip("—- ")):
            found.append(f"{cid}: {c['status']} needs evidence and a stated way it was shown able to fail")
        if c["status"] in ("REFUTED", "NOT_SUPPORTED") and not c["evidence"]:
            found.append(f"{cid}: {c['status']} needs the evidence that refutes it")
    return found


def render(doc):
    claims = doc["claims"]
    count = lambda key, values: " · ".join(f"{v} {sum(c[key] == v for c in claims)}" for v in values  # noqa: E731
                                           if any(c[key] == v for c in claims))
    cell = lambda xs: "<br>".join(f"`{x}`" for x in xs) or "—"  # noqa: E731
    lines = [
        "# Claims matrix (generated: do not edit; edit docs/claims.json and run tools/claims_matrix.py)",
        "",
        f"As of `{doc['as_of']}`. {len(claims)} claims. {doc['note']}",
        "",
        f"**By status:** {count('status', STATUSES)}",
        "",
        f"**By oracle:** {count('oracle', ORACLES)}",
        "",
        "| ID | Claim | Status | Oracle | Tests | Evidence | Independence | Shown able to fail | Gap |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for c in claims:
        lines.append(f"| {c['id']} | {c['claim']} | **{c['status']}** | {c['oracle']} | {cell(c['tests'])} | "
                     f"{cell(c['evidence'])} | {c['independence']} | {c['can_fail']} | {c['gap']} |")
    return "\n".join(lines) + "\n"


def main(argv):
    with open(SOURCE, encoding="utf-8") as fh:
        doc = json.load(fh)
    found = problems(doc)
    for p in found:
        print(f"PROBLEM  {p}")
    if found:
        print(f"VERDICT  {len(found)} problem(s)")
        return 1
    text = render(doc)
    if "--check" in argv:
        current = open(OUT, encoding="utf-8").read() if os.path.exists(OUT) else ""
        if current != text:
            print("VERDICT  docs/CLAIMS_MATRIX.md is stale: run python tools/claims_matrix.py")
            return 1
    else:
        with open(OUT, "w", encoding="utf-8") as fh:
            fh.write(text)
    print(f"VERDICT  valid: {len(doc['claims'])} claims")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
