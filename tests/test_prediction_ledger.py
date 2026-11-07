import os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_selftest_passes():
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "prediction_ledger.py"), "--selftest"],
                       capture_output=True, text=True)
    assert r.returncode == 0 and "PASS" in r.stdout
