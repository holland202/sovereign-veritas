"""OVF-1: an integer quality floor too large for a double must not crash K or V (docs/OVF1_PREREG.md)."""
import copy
import importlib.util
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("gate_contract", ROOT / "tools" / "gate_contract.py")
gct = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gct)


def base_allow_input():
    for v in gct.read_vectors():
        if v["expect"]["decision"] == "ALLOW":
            inp = copy.deepcopy(v["input"])
            inp["record"]["evidence_quality"] = 0.2
            return inp
    raise AssertionError("no ALLOW vector")


IMPLEMENTATIONS = {"kernel": gct.kernel_gate, "verifier": gct.verifier_gate}


@pytest.mark.parametrize("impl", sorted(IMPLEMENTATIONS))
def test_huge_floor_defers_with_inf_instead_of_crashing(impl):
    inp = base_allow_input()
    inp["capability"]["min_evidence_quality"] = 10 ** 400
    decision, reasons = IMPLEMENTATIONS[impl]()(inp)
    assert (decision, list(reasons)) == ("DEFER", ["evidence_quality_below_threshold:0.2000<inf"])


@pytest.mark.parametrize("impl", sorted(IMPLEMENTATIONS))
def test_huge_negative_floor_adds_no_reason(impl):
    inp = base_allow_input()
    inp["capability"]["min_evidence_quality"] = -(10 ** 400)
    decision, reasons = IMPLEMENTATIONS[impl]()(inp)
    assert not any(r.startswith("evidence_quality") for r in reasons)
