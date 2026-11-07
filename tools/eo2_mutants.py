#!/usr/bin/env python3
"""EO-2 P9: hand-made mutants of sovereign_veritas/effect_observation.py. Each runs on a temporary copy and the
property tests must fail on it.  python tools/eo2_mutants.py   (exit 0 only if every mutant is killed)"""
import pathlib, shutil, subprocess, sys, tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
MUTANTS = [
    ("M1 binding ignored", 'if bind and (observation.get("record_id")', 'if False and (observation.get("record_id")'),
    ("M2 REFUSE/DEFER change accepted", "return OK if not changed else UNAUTHORIZED_EFFECT", "return OK"),
    ("M3 status not checked", 'if status != "SUCCEEDED":', 'if False:'),
    ("M4 strict rule dropped", "        if strict and changed:\n            return WRONG_EFFECT\n", ""),
    ("M5 extra changed keys allowed", " and changed <= set(expected):", ":"),
    ("M6 no-change reported OK", "    if not changed:\n        return NO_EFFECT\n", "    if not changed:\n        return OK\n"),
    ("M7 digest ignores the requested action", "hashlib.sha256(canonical_json(action)",
     "hashlib.sha256(canonical_json({k: v for k, v in (action or {}).items() if k != 'requested'})"),
]


def main():
    src = (ROOT / "sovereign_veritas" / "effect_observation.py").read_text(encoding="utf-8")
    killed = 0
    for name, old, new in MUTANTS:
        if src.count(old) != 1:
            print(f"COULD NOT APPLY {name}")
            return 2
        d = pathlib.Path(tempfile.mkdtemp(prefix="eo2mut_")) / "sv"
        shutil.copytree(ROOT, d, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache", "*.egg-info"))
        (d / "sovereign_veritas" / "effect_observation.py").write_text(src.replace(old, new), encoding="utf-8")
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                            "tests/test_effect_observation.py"], cwd=d, capture_output=True, text=True)
        ok = r.returncode != 0
        killed += ok
        print(f"{'KILLED  ' if ok else 'SURVIVED'} {name}")
    print(f"mutants killed: {killed}/{len(MUTANTS)}")
    return 0 if killed == len(MUTANTS) else 1


if __name__ == "__main__":
    sys.exit(main())
