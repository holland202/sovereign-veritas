"""Supply-chain and SAST triage pins (docs/SUPPLY_CHAIN.md).

The kernel has no third-party runtime dependency, and the verifier is stdlib-only and imports nothing from the kernel
(its docstring says so; this checks it). Two bandit findings were real and are fixed here: an `assert` that `python -O`
would strip from the planner, and `tempfile.mktemp` in a probe's selftest.
"""
import ast
import re
import sys
from pathlib import Path

import pytest

from test_planner import _planner, _step
from sovereign_veritas.planner import BoundedPlan

ROOT = Path(__file__).resolve().parents[1]
STDLIB = set(sys.stdlib_module_names)


def top_level_imports(source):
    names = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names


def test_the_import_check_can_fire():
    assert top_level_imports("import requests\nfrom numpy import array\nimport json") - STDLIB == {"requests", "numpy"}


def test_the_kernel_imports_only_the_standard_library_and_itself():
    foreign = {}
    for path in (ROOT / "sovereign_veritas").rglob("*.py"):
        extra = top_level_imports(path.read_text(encoding="utf-8")) - STDLIB - {"sovereign_veritas", "__future__"}
        if extra:
            foreign[str(path.relative_to(ROOT))] = sorted(extra)
    assert foreign == {}


@pytest.mark.parametrize("tool", ["verify_package.py", "consumer.py"])
def test_the_verifier_and_consumer_are_stdlib_only_and_do_not_import_the_kernel(tool):
    names = top_level_imports((ROOT / "tools" / tool).read_text(encoding="utf-8"))
    assert names - STDLIB - {"__future__"} == set(), names - STDLIB


def test_no_third_party_runtime_dependency():
    # a text check, not tomllib: CI also runs Python 3.10, which has no tomllib
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert re.findall(r"^dependencies\s*=\s*(.*)$", text, re.M) == ["[]"]


def test_a_capability_removed_after_preflight_is_refused_without_assert():
    """bandit B101: the planner relied on `assert capability is not None`, which python -O removes."""
    planner, ledger, executor = _planner()
    real_get, calls = planner.registry.get, []

    def get(name):
        calls.append(name)
        return None if len(calls) > 1 else real_get(name)  # present at preflight, gone at run
    planner.registry.get = get
    with pytest.raises(ValueError, match="capability_missing_after_preflight:read"):
        planner.run(BoundedPlan(steps=(_step("a"),)))
    assert executor.calls == [] and len(ledger.all()) == 0
