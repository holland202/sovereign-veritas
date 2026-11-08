"""The 18 research skills are built from tools/skills/ (one source). A hand edit to any copy fails here."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_built_skills_match_their_single_source():
    p = subprocess.run([sys.executable, str(ROOT / "tools/skills/build.py"), "--check"],
                       capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stdout + p.stderr
