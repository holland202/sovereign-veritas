"""Pins Amos Tipton's A/B Recovery Challenge (docs/AB_RECOVERY_PREREG.md) to its recorded outcome."""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_ab_recovery_outcome_as_recorded():
    p = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "ab_recovery_challenge.py")],
                       capture_output=True, text=True, cwd=ROOT)
    assert p.returncode == 0, p.stdout[-2000:] + p.stderr[-2000:]
    assert "VERDICT  12 of 12 as registered" in p.stdout
    assert "DIGEST   a06a43c285be84d87504fba8552489ec1956510f79954f7069fdd28752ca9d47" in p.stdout
