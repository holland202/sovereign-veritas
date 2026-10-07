"""contract/gate_vectors_supplement.jsonl: in-contract cases the frozen vectors miss (docs/DIFFERENTIAL_RESULTS.md)."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_kernel_and_verifier_conform_to_the_supplement():
    p = subprocess.run([sys.executable, str(ROOT / "tools" / "gate_supplement.py")], capture_output=True, text=True)
    assert p.returncode == 0, p.stdout
    assert "VERDICT  CONFORMS" in p.stdout


def test_supplement_kills_a_vocabulary_mutant_the_frozen_vectors_miss(tmp_path):
    # Anti-vacuity: drop "high" from the verifier's thermal vocabulary. The 4690 frozen vectors still conform (shown in
    # docs/DIFFERENTIAL_RESULTS.md); the supplement must not.
    src = (ROOT / "tools" / "verify_package.py").read_text(encoding="utf-8")
    assert src.count('"warning", "high", "hot"') == 1
    mutant = tmp_path / "vp_mutant.py"
    mutant.write_text(src.replace('"warning", "high", "hot"', '"warning", "hot"'), encoding="utf-8")
    import importlib.util
    spec = importlib.util.spec_from_file_location("vp_mutant", mutant)
    vp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vp)
    cases = [json.loads(l) for l in (ROOT / "contract" / "gate_vectors_supplement.jsonl").read_text().splitlines() if l]
    wrong = [c["id"] for c in cases
             if list(vp.replay_gate(c["input"]["record"], c["input"]["capability"], c["input"]["capability_registry"],
                                    c["input"]["runtime"], c["input"]["policy"])) != [c["expect"]["decision"],
                                                                                    c["expect"]["reasons"]]]
    assert wrong == ["S:thermal_status=high"]
