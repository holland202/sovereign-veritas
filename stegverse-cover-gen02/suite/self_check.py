#!/usr/bin/env python3
"""Derived-suite self-check. Template layer carried verbatim from SUITE__TEMPLATE GEN 01;
GEN 02 adds the vacancy layer at the end (see the marked block).
Two layers: (1) every manifest member verifies (size + SHA-256), no unlisted
files; (2) the conformance checklist derived from the REFERENCE suites —
a suite cannot pass without its cost-tracking spine, whatever its content."""
import hashlib, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
manifest = json.load(open(os.path.join(HERE, "PACKAGE__MANIFEST__01.json")))
fails, passes = [], 0

def check(name, ok, detail=""):
    global passes
    if ok: passes += 1
    else: fails.append(f"{name}: {detail}")

members = {m["file"]: m for m in manifest["members"]}
for name, m in members.items():
    p = os.path.join(HERE, name)
    if not os.path.exists(p):
        check(name, False, "missing"); continue
    data = open(p, "rb").read()
    check(name, len(data) == m["bytes"] and hashlib.sha256(data).hexdigest() == m["sha256"],
          f"size/hash mismatch ({len(data)}B)")

for name in os.listdir(HERE):
    if name == "PACKAGE__MANIFEST__01.json" or name.startswith("."): continue
    if os.path.isfile(os.path.join(HERE, name)):
        check("listed:" + name, name in members, "file present but not in manifest")

def body(n): return open(os.path.join(HERE, n), encoding="utf-8").read()

# --- conformance checklist: from the reference suites, not from this suite ---
check("ref:manifest-project", bool(manifest.get("project_id")), "manifest carries no project_id")
check("ref:manifest-funding", bool(manifest.get("funding")), "manifest carries no funding field")
readme = body("README.md") if "README.md" in members else ""
check("ref:projectid-in-readme", "ProjectID:" in readme, "README carries no ProjectID")
check("ref:funding-in-readme", "Funding:" in readme, "README carries no Funding line")
check("ref:funding-member", "FUNDING__STATEMENT__01.md" in members, "no FUNDING__STATEMENT member")
if "FUNDING__STATEMENT__01.md" in members:
    fs = body("FUNDING__STATEMENT__01.md")
    check("ref:funding-statement-content",
          "ProjectID:" in fs and "Funding:" in fs and "commercial arrangement" in fs.lower(),
          "funding statement lacks ProjectID / Funding / arrangement lines")
check("ref:proof-in-suite", "CONFORMANCE__PROOF__01.json" in members,
      "no in-suite conformance proof member")
derived = manifest.get("derived_from") or {}
check("ref:derived-from-template", bool(derived.get("template_manifest_sha256")),
      "no template derivation recorded in manifest")
sc = os.path.join(HERE, "self_check.py")
actual = hashlib.sha256(open(sc, "rb").read()).hexdigest() if os.path.exists(sc) else ""
check("ref:self-check-is-templates", derived.get("self_check_sha256") == actual,
      "self_check.py differs from the template's checker")


# --- GEN 02 vacancy layer -------------------------------------------------
# Extension beyond the template checker; every template check above is
# retained verbatim. GEN 01 of the first derived suite line shipped three
# prose members as unfilled template placeholders and every check above
# passed: the gate verified bytes and the funding spine, but nothing
# verified that the prose members SAY anything. These checks make the
# gate fail on vacancy. They are named with the "vacancy:" prefix so a
# failure is attributable to this layer, and test_non_vacuity.py proves
# they can fail. The extension is recorded in the manifest's derivation.
import re as _re
_md = {}
for _n in members:
    if _n.endswith(".md") and os.path.exists(os.path.join(HERE, _n)):
        _md[_n] = body(_n)
_ph = [n for n, t in _md.items() if ("TODO \u2014" in t or "{{" in t)]
check("vacancy:no-template-placeholders", not _ph,
      "placeholder text in: " + ", ".join(_ph))
def _section(t, head):
    m = _re.search(r"(?ms)^## " + _re.escape(head) + r"\s*$(.*?)(?=^## |\Z)", t)
    return m.group(1).strip() if m else ""
_ch = _md.get("SUITE__CHARTER__01.md", "")
check("vacancy:charter-purpose-substance", len(_section(_ch, "Purpose")) >= 200,
      "charter Purpose section missing or under 200 characters")
_sp = _md.get("SPEC__MEMBER__01.md", "")
check("vacancy:spec-substance", len(_sp) >= 1000,
      f"spec member is {len(_sp)} chars (< 1000)")
_rf = _md.get("REFERENCES__01.md", "")
check("vacancy:references-pointers", len(_rf) >= 500 and _rf.count("http") >= 3,
      "references member lacks substance or carries fewer than 3 concrete pointers")
_stub = [n for n, t in _md.items() if len(t.encode("utf-8")) < 150]
check("vacancy:no-stub-members", not _stub,
      "stub members (<150B): " + ", ".join(_stub))

print(f"SELF-CHECK: {passes} PASS / {len(fails)} FAIL")
for f in fails: print("  FAIL", f)
sys.exit(1 if fails else 0)
