"""tools/test_vacuity_audit.py on a throwaway repository with one of each defect (TVA-1, docs/TVA1_PREREG.md)."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "test_vacuity_audit.py"
TESTS = '''import os, unittest
HAS_LIB = False


class NeedsLib(unittest.TestCase):
    def setUp(self):
        if not HAS_LIB:
            self.skipTest("lib missing")

    def test_really_needs_the_lib(self):
        import a_library_that_does_not_exist_tva1  # noqa: F401

    def test_does_not_need_the_lib(self):
        self.assertEqual(sum([1, 2]), 3)


def test_reads_an_untracked_file():
    with open(os.path.join(os.path.dirname(__file__), "data.txt")) as fh:
        assert fh.read() == "x"
'''


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_the_audit_flags_a_collateral_skip_and_an_untracked_dependency_and_nothing_else(tmp_path):
    repo = tmp_path / "repo"
    (repo / "tests").mkdir(parents=True)
    (repo / "tests" / "test_x.py").write_text(TESTS)
    (repo / ".gitignore").write_text("data.txt\n")
    (repo / "tests" / "data.txt").write_text("x")
    git = ["git", "-C", str(repo), "-c", "user.email=t@example.invalid", "-c", "user.name=t"]
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(git + ["add", "."], check=True)
    subprocess.run(git + ["commit", "-q", "-m", "fixture"], check=True)
    p = subprocess.run([sys.executable, str(TOOL), str(repo)], capture_output=True, text=True)
    out = p.stdout
    assert p.returncode == 1, out
    assert "FLAG  collateral skip: tests.test_x.NeedsLib::test_does_not_need_the_lib" in out
    assert "justified skip:  tests.test_x.NeedsLib::test_really_needs_the_lib" in out
    assert "FLAG  untracked dependency: tests.test_x::test_reads_an_untracked_file" in out
    assert "VERDICT  2 flagged (1 collateral skip(s), 1 untracked dependenc(ies))" in out


def test_the_audit_flags_nothing_on_a_clean_repository(tmp_path):
    repo = tmp_path / "repo"
    (repo / "tests").mkdir(parents=True)
    (repo / "tests" / "test_y.py").write_text("def test_ok():\n    assert 1 + 1 == 2\n")
    p = subprocess.run([sys.executable, str(TOOL), str(repo), "--no-clean-checkout"], capture_output=True, text=True)
    assert p.returncode == 0 and "VERDICT  0 flagged" in p.stdout, p.stdout


def test_a_suite_that_cannot_be_collected_is_not_established(tmp_path):
    """SK-1's skill arm found that a collection error aborted the run and the audit still printed '0 flagged', exit 0."""
    repo = tmp_path / "repo"
    (repo / "tests").mkdir(parents=True)
    (repo / "tests" / "test_z.py").write_text("import a_module_that_is_absent_tva1  # noqa: F401\n\n\n"
                                             "def test_z():\n    assert 1 + 1 == 2\n")
    (repo / "tests" / "test_ok.py").write_text("def test_ok():\n    assert 2 + 2 == 4\n")
    p = subprocess.run([sys.executable, str(TOOL), str(repo), "--no-clean-checkout"], capture_output=True, text=True)
    assert p.returncode == 2, p.stdout
    assert "VERDICT  NOT ESTABLISHED" in p.stdout and "tests.test_z" in p.stdout, p.stdout
    assert "VERDICT  0 flagged" not in p.stdout


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_a_module_that_imports_an_untracked_file_is_flagged(tmp_path):
    """In the clean checkout the module cannot be collected; its tests must not read as 'not in HEAD'."""
    repo = tmp_path / "repo"
    (repo / "tests").mkdir(parents=True)
    (repo / "tests" / "test_w.py").write_text("from helper_untracked_tva1 import VALUE\n\n\n"
                                             "def test_uses_the_helper():\n    assert VALUE == 3\n")
    (repo / "tests" / "test_v.py").write_text("def test_plain():\n    assert 3 * 3 == 9\n")
    (repo / "tests" / "helper_untracked_tva1.py").write_text("VALUE = 3\n")
    (repo / ".gitignore").write_text("helper_untracked_tva1.py\n")
    git = ["git", "-C", str(repo), "-c", "user.email=t@example.invalid", "-c", "user.name=t"]
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(git + ["add", "."], check=True)
    subprocess.run(git + ["commit", "-q", "-m", "fixture"], check=True)
    p = subprocess.run([sys.executable, str(TOOL), str(repo)], capture_output=True, text=True)
    assert p.returncode == 1, p.stdout
    assert "FLAG  untracked dependency: tests.test_w::test_uses_the_helper" in p.stdout, p.stdout
    assert "test_v::test_plain" not in p.stdout.split("VERDICT")[0].split("clean checkout")[-1].replace(
        "review", ""), p.stdout
