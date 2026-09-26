"""The Gate contract (CONTRACT.md) held to its vectors. Registered in docs/GATE_CONTRACT.md (C1-C5)."""
import hashlib
import importlib.util
import json
import pathlib
import re
import sys
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "gate_contract.py"
_spec = importlib.util.spec_from_file_location("gate_contract", TOOL)
gct = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gct)


def vectors():
    return gct.read_vectors()


def expected_digest(vs):
    return gct.conformance_digest([(v["id"], v["expect"]["decision"], v["expect"]["reasons"]) for v in vs])


# ---- C1 / C2: generated from the kernel, agreed by the verifier, frozen --------------------------
def test_c1_c2_regenerating_reproduces_the_frozen_file_and_both_implementations_agree():
    lines, excluded, disagree = gct.generate()
    assert disagree == []
    assert excluded == ["S:quality=nan", "S:quality=inf"]
    assert "".join(line + "\n" for line in lines) == pathlib.Path(gct.VECTORS).read_text(encoding="utf-8")


def test_c2_contract_md_states_the_current_digests():
    text = (ROOT / "CONTRACT.md").read_text(encoding="utf-8")
    data = pathlib.Path(gct.VECTORS).read_bytes()
    vs = vectors()
    assert f"`{hashlib.sha256(data).hexdigest()}`" in text
    assert f"`{expected_digest(vs)}`" in text
    assert re.search(rf"\b{len(vs)} vectors\b", text)


@pytest.mark.parametrize("which", ["kernel", "verifier"])
def test_c1_each_implementation_conforms(which):
    vs = vectors()
    decide = gct.kernel_gate() if which == "kernel" else gct.verifier_gate()
    rows = gct.run(decide, vs)
    assert gct.conformance_digest(rows) == expected_digest(vs)


# ---- C3: every reachable rule is pinned --------------------------------------------------------------
def test_c3_every_rule_of_the_verifiers_gate_is_pinned_or_listed_unreachable(capsys):
    assert gct.mutants(vectors()) == 0
    assert "0 SURVIVED" in capsys.readouterr().out


# ---- C4: the language-neutral protocol -------------------------------------------------------------
def check_command(tmp_path, program):
    script = tmp_path / "impl.py"
    script.write_text(program, encoding="utf-8")
    p = subprocess.run([sys.executable, str(TOOL), "--check-command", sys.executable, str(script)],
                       capture_output=True, text=True, timeout=600)
    return p.returncode, p.stdout


def test_c4_a_correct_program_conforms():
    p = subprocess.run([sys.executable, str(TOOL), "--check-command", sys.executable, str(TOOL),
                        "--serve", "verifier"], capture_output=True, text=True, timeout=600)
    assert p.returncode == 0 and "VERDICT  CONFORMS" in p.stdout


def test_c4_a_wrong_program_fails_with_a_count(tmp_path):
    rc, out = check_command(tmp_path, (
        "import json, sys\n"
        "for line in sys.stdin:\n"
        "    c = json.loads(line)\n"
        "    print(json.dumps({'id': c['id'], 'decision': 'ALLOW', 'reasons': []}))\n"))
    wrong = sum(v["expect"]["decision"] != "ALLOW" for v in vectors())
    assert rc == 1 and f"VERDICT  {wrong} of {len(vectors())} vectors differ" in out


@pytest.mark.parametrize("program", [
    "import sys\nsys.exit(3)\n",                                             # crashes
    "import sys\nfor line in sys.stdin:\n    print('ALLOW')\n",              # not JSON
    "import sys, json\nfor line in list(sys.stdin)[:-1]:\n"                  # one line short
    "    c = json.loads(line); print(json.dumps({'id': c['id'], 'decision': 'ALLOW', 'reasons': []}))\n",
    "import sys, json\nfor line in sys.stdin:\n"                             # ids out of order
    "    c = json.loads(line); print(json.dumps({'id': 'x', 'decision': 'ALLOW', 'reasons': []}))\n",
])
def test_c4_a_broken_program_could_not_run_never_passes(tmp_path, program):
    rc, out = check_command(tmp_path, program)
    assert rc == 2 and "COULD NOT RUN" in out


# ---- the F2-F4 pins are in the vectors ------------------------------------------------------------
@pytest.mark.parametrize("vid,decision,reasons", [
    ("X:quality=true (not 1.0)", "DEFER", ["evidence_quality_below_threshold:0.0000<0.5000"]),
    ("X:quality='0.9' (a string is not a number)", "DEFER", ["evidence_quality_below_threshold:0.0000<0.5000"]),
    ("X:quality=0.49999 (reason rounds to 0.5000)", "DEFER", ["evidence_quality_below_threshold:0.5000<0.5000"]),
    ("X:quality=0.03125 (tie: half-to-even gives 0.0312)", "DEFER", ["evidence_quality_below_threshold:0.0312<0.5000"]),
    ("X:quality=10**400 (beyond float range)", "DEFER", ["evidence_quality_invalid:inf"]),
    ("S:quality=2.0", "DEFER", ["evidence_quality_invalid:2.0"]),
    ("X:top-level quality 'high', metadata 0.9 (top level wins)", "DEFER", ["evidence_quality_below_threshold:0.0000<0.5000"]),
])
def test_quality_pins(vid, decision, reasons):
    v = {x["id"]: x for x in vectors()}[vid]
    assert v["expect"] == {"decision": decision, "reasons": reasons}


def test_the_vectors_are_not_git_ignored():
    """A *.jsonl rule in .gitignore hid this file once; verifier_mutants' null mutant caught it."""
    if not (ROOT / ".git").exists():
        pytest.skip("not a git checkout")
    p = subprocess.run(["git", "check-ignore", "-q", "contract/gate_vectors.jsonl"], cwd=ROOT)
    assert p.returncode == 1  # 1 = not ignored

