"""docs/claims.json is valid and docs/CLAIMS_MATRIX.md is current; the checker reports each kind of planted error."""
import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("claims_matrix", ROOT / "tools" / "claims_matrix.py")
cm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cm)
DOC = json.loads((ROOT / "docs" / "claims.json").read_text(encoding="utf-8"))


def test_the_matrix_is_valid_and_the_rendered_table_is_current():
    p = subprocess.run([sys.executable, str(ROOT / "tools" / "claims_matrix.py"), "--check"], capture_output=True, text=True)
    assert p.returncode == 0, p.stdout


def _planted(change):
    doc = copy.deepcopy(DOC)
    change(doc["claims"])
    return cm.problems(doc)


@pytest.mark.parametrize("name,change,expect", [
    ("status", lambda cs: cs[0].update(status="PROVEN"), "status 'PROVEN'"),
    ("oracle", lambda cs: cs[0].update(oracle="MODEL_DEPENDENT"), "oracle 'MODEL_DEPENDENT'"),
    ("evidence", lambda cs: cs[0]["evidence"].append("results/does_not_exist.txt"), "does not exist"),
    ("test_file", lambda cs: cs[0]["tests"].append("tests/test_nope.py::test_x"), "test file tests/test_nope.py"),
    ("test_name", lambda cs: cs[0]["tests"].append("tests/test_execution.py::test_that_was_never_written"), "has no test"),
    ("duplicate", lambda cs: cs.append(copy.deepcopy(cs[0])), "duplicate id"),
    ("can_fail", lambda cs: cs[0].update(can_fail="—"), "shown able to fail"),
    ("refuted", lambda cs: cs.append(dict(copy.deepcopy(cs[0]), id="CX", status="REFUTED", evidence=[])), "refutes it"),
    ("field", lambda cs: cs[0].update(confidence="high"), "unknown ['confidence']"),
])
def test_the_checker_reports_planted_errors(name, change, expect):
    assert cm.problems(DOC) == []
    found = _planted(change)
    assert any(expect in p for p in found), (name, found)
