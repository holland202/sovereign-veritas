"""SEC-005 (docs/SEC005_PREREG.md): the registered probe reproduces its recorded outcome, and sabotage changes it."""
import subprocess
import sys
from pathlib import Path

PROBE = Path(__file__).resolve().parents[1] / "tools" / "sec005_lock_probe.py"


def _run(*args):
    return subprocess.run([sys.executable, "-I", str(PROBE), *args], capture_output=True, text=True, timeout=300)


def test_sec005_recorded_outcome():
    p = _run()
    assert p.returncode == 0, p.stdout + p.stderr
    assert "VERDICT FIXED_IN_TESTED_SCHEDULES: 6 of 6 as registered" in p.stdout
    assert "RECORDED MATCH" in p.stdout


def test_sec005_sabotage_restores_sec004():
    p = _run("--sabotage")
    assert p.returncode == 1, p.stdout + p.stderr
    assert "VERDICT NOT_FIXED" in p.stdout
    assert "P2 REFUTED" in p.stdout and "P6 HELD" in p.stdout
