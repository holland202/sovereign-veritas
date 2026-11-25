#!/usr/bin/env python3
"""Regression for tools/std3_run.py on the saved STD-3 reports (std3/chatgpt/005).

  python tools/test_std3_run.py [/path/to/oasb]

Judges the saved reports from a temporary directory that is not the OASB checkout they were made in. If an OASB
checkout at 7bf7deb is given, its src/ is copied there first (P6 reads the test sources); otherwise R3 is NOT RUN.
  R1  --sabotage --expect-scenarios=220 exits 0, judges 220 of 220 not moving, and reports the sabotage caught.
  R2  --expect-scenarios=219 exits 2 (the inventory guard can refuse).
  R3  --cached from that directory reproduces every judgment line of results/std3/run.txt.
Exit 0 if all hold, 1 otherwise.
"""
import os
import subprocess
import sys
import shutil
import tempfile

RUN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "std3_run.py")


def judge(root, *extra):
    p = subprocess.run([sys.executable, RUN, root, "--sabotage", *extra], capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


ok = True
src = [a for a in sys.argv[1:] if not a.startswith("-")]
with tempfile.TemporaryDirectory() as root:
    if src:
        shutil.copytree(os.path.join(src[0], "src"), os.path.join(root, "src"))
    rc, out = judge(root, "--expect-scenarios=220")
    r1 = rc == 0 and "not moving: 220 of 220" in out and "SABOTAGE caught" in out
    print("R1", "PASS" if r1 else "FAIL", f"rc={rc}")
    rc2, out2 = judge(root, "--expect-scenarios=219")
    r2 = rc2 == 2 and "expected 219" in out2
    print("R2", "PASS" if r2 else "FAIL", f"rc={rc2}")
    r3 = None
    if src:
        p3 = subprocess.run([sys.executable, RUN, root, "--cached"], capture_output=True, text=True)
        saved = open(os.path.join(os.path.dirname(RUN), "..", "results", "std3", "run.txt")).read().splitlines()
        keep = lambda ls: [l for l in ls if l.startswith(("HELD", "REFUTED", "ARP ", "SILENT", "ECHO", "FLAG", "           "))]
        r3 = p3.returncode == 0 and keep(p3.stdout.splitlines()) == keep(saved)
    print("R3", "NOT RUN (no OASB checkout given)" if r3 is None else ("PASS" if r3 else "FAIL"))
    ok = r1 and r2 and r3 is not False
    if not ok:
        print(out[-1500:], out2[-1500:], sep="\n----\n")
sys.exit(0 if ok else 1)
