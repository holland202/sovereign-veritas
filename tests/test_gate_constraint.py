"""The Gate's ALLOW set must equal a fail-closed spec's, and the check must be able to fail.

Wraps tools/gate_constraint.py; method and measurements in docs/GATE_CONSTRAINT.md.
"""
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "gate_constraint.py"


def _run(*flags):
    return subprocess.run(
        [sys.executable, str(TOOL), "--target", str(ROOT), *flags],
        capture_output=True, text=True, timeout=900,
    )


def test_gate_allow_set_equals_fail_closed_spec():
    p = _run()
    assert p.returncode == 0, p.stdout + p.stderr


def test_gate_constraint_instrument_kills_its_mutants():
    p = _run("--mutants")
    assert p.returncode == 0, p.stdout + p.stderr
