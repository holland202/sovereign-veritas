"""Non-vacuity tests for this suite's conformance gate (StegVerse Build Lane).

The subject's second finding on GEN 01: three members shipped as unfilled
template placeholders and the conformance checker passed anyway — the gate
verified bytes and the funding spine, but nothing verified that the prose
members say anything, so it could not fail on vacancy. GEN 02's self-check
carries a vacancy layer (checks named "vacancy:..." in self_check.py).
This test proves the layer can fail, which is the only way its passing
means anything:

    T0  control: a pristine copy of this suite passes its own self-check.
    T1  the charter replaced by the template placeholder text (the exact
        form GEN 01 shipped), manifest re-bound so ONLY content checks can
        fail -> the self-check FAILS, and every failure is a vacancy one.
    T2  same for the spec member.
    T3  same for the references member.

Stdlib only; runs anywhere:

    python3 test_non_vacuity.py
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent

CHARTER_PLACEHOLDER = """# SOVEREIGN VERITAS COVERING SUITE \u2014 Charter \u2014 01

Status: FILED AS GEN 01 MEMBER (template instantiation).
ProjectID: LINKEDIN-SOVEREIGN-VERITAS-EVAL
Funding: UNFUNDED

## Purpose

TODO \u2014 the suite's purpose, stated by its author.

## Level discipline

TODO \u2014 the levels this suite holds apart.
"""

SPEC_PLACEHOLDER = """# Spec Member \u2014 01

Status: FILED AS GEN 01 MEMBER (template instantiation).
Source: placeholder

TODO \u2014 member content.
"""

REFERENCES_PLACEHOLDER = """# References \u2014 The Surrounding Record \u2014 01

Status: POINTERS ONLY. Each entry names where the underlying record lives;
this file carries no content of theirs.

TODO \u2014 pointers to the surrounding record.
"""

RESULTS: list[tuple[str, bool, str]] = []


def case(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))
    print(f"{'ok  ' if ok else 'FAIL'} {name}  {detail}")


def copy_suite(dst: Path) -> None:
    for p in HERE.iterdir():
        if p.is_file() and p.name != "__pycache__":
            shutil.copy(p, dst / p.name)


def rebind(suite: Path, changed: str) -> None:
    """Re-bind the copy's manifest to `changed`'s new bytes, so the manifest
    layer passes and only content (vacancy) checks can fail."""
    man_path = suite / "PACKAGE__MANIFEST__01.json"
    man = json.loads(man_path.read_text(encoding="utf-8"))
    data = (suite / changed).read_bytes()
    for m in man["members"]:
        if m["file"] == changed:
            m["bytes"] = len(data)
            m["sha256"] = hashlib.sha256(data).hexdigest()
    man_path.write_text(json.dumps(man, indent=2), encoding="utf-8")


def run_checker(suite: Path) -> tuple[int, str]:
    r = subprocess.run([sys.executable, str(suite / "self_check.py")],
                       capture_output=True, text=True, cwd=suite, timeout=120)
    return r.returncode, r.stdout


def vacancy_only_failures(out: str) -> bool:
    fails = [ln.strip() for ln in out.splitlines() if ln.strip().startswith("FAIL")]
    return bool(fails) and all(ln.startswith("FAIL vacancy:") for ln in fails)


def vacated_case(name: str, member: str, placeholder: str) -> None:
    tmp = Path(tempfile.mkdtemp(prefix="sv-vacancy-"))
    copy_suite(tmp)
    (tmp / member).write_text(placeholder, encoding="utf-8")
    rebind(tmp, member)
    rc, out = run_checker(tmp)
    case(name, rc != 0 and vacancy_only_failures(out),
         f"rc={rc}; failures attributable to the vacancy layer only: {vacancy_only_failures(out)}")


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="sv-vacancy-control-"))
    copy_suite(tmp)
    rc, out = run_checker(tmp)
    case("T0 control: pristine copy passes its self-check", rc == 0,
         f"rc={rc}; last line: {(out.strip().splitlines() or [''])[0]}")

    vacated_case("T1 charter as template placeholder: gate fails on vacancy",
                 "SUITE__CHARTER__01.md", CHARTER_PLACEHOLDER)
    vacated_case("T2 spec as template placeholder: gate fails on vacancy",
                 "SPEC__MEMBER__01.md", SPEC_PLACEHOLDER)
    vacated_case("T3 references as template placeholder: gate fails on vacancy",
                 "REFERENCES__01.md", REFERENCES_PLACEHOLDER)

    bad = [n for n, ok, _ in RESULTS if not ok]
    print(f"NON-VACUITY VERDICT  {'PASS' if not bad else 'FAIL'} - {len(RESULTS) - len(bad)}/{len(RESULTS)} as registered")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
