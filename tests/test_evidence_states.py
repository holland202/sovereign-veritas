"""Evidence states on the runtime fields (I2 in docs/INTEGRATION.md).

Vocabulary and the no-implicit-promotion rule from evidence-ledger SPEC.md section 2
(github.com/holland202/evidence-ledger @ ccf9144). The E2 cases follow its
adversarial/evidence_state_laundering.py: relabel where a value came from, keep everything else
consistent, and see whether the verifier notices.
"""
import copy
import json
import os
import subprocess
import sys

import pytest

from sovereign_veritas.capability import Capability
from sovereign_veritas.evidence import EvidenceRecord
from sovereign_veritas.package import build_package
from sovereign_veritas.runtime import RuntimeState
from test_package import make as make_fixture
from test_thermal_policy import ROOT, failed, reseal, tree, vp


def made(tmp_path, *flags):
    """A real package from tools/make_package.py, with a cool fake zone tree."""
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    zones = tmp_path / "z"
    if not zones.exists():
        tree(zones)
    out = subprocess.run([sys.executable, str(ROOT / "tools" / "make_package.py"), "--rounds", "10",
                          "--thermal-root", str(zones), *flags], capture_output=True, text=True,
                         env=dict(os.environ, HOME=str(home)), check=True).stdout
    path = next(line.split()[1] for line in out.splitlines() if line.startswith("package "))
    with open(path, encoding="utf-8") as fh:
        pkg = json.load(fh)
    os.remove(path)
    return pkg


# ---- E1: what make_package.py records --------------------------------------------------------
@pytest.mark.parametrize("flags,states,decision", [
    (("--thermal-status", "normal"), ("OPERATOR", "DEFAULTED", "DEFAULTED"), "ALLOW"),
    (("--thermal-status", "measured"), ("DERIVED", "DEFAULTED", "DEFAULTED"), "ALLOW"),
    ((), ("ABSENT", "DEFAULTED", "DEFAULTED"), "REFUSE"),
    (("--thermal-status", "normal", "--compute-budget", "available", "--power-status", "stable"),
     ("OPERATOR", "OPERATOR", "OPERATOR"), "ALLOW"),
    (("--thermal-status", "normal", "--compute-budget", "exhausted"),
     ("OPERATOR", "OPERATOR", "DEFAULTED"), "DEFER"),
])
def test_e1_make_package_records_where_each_value_came_from(tmp_path, flags, states, decision):
    pkg = made(tmp_path, *flags)
    rs = pkg["resource_state"]
    assert tuple(rs["evidence_states"][f] for f in vp.EV_FIELDS) == states
    assert pkg["decision"]["decision"] == decision
    checks = {n: ok for n, ok, _ in vp.verify(pkg)}
    assert checks.get("evidence_states") is True and all(checks.values())
    assert pkg["known_limitations"][3] == vp.evidence_statement(rs["evidence_states"])


# ---- E2: laundering. The attacker rewrites the tags AND regenerates the limitation line, then
# recomputes every digest, so evidence_states is the only check left that can object.
def launder(p, **tags):
    p["resource_state"]["evidence_states"].update(tags)
    p["known_limitations"][3] = vp.evidence_statement(p["resource_state"]["evidence_states"])
    return reseal(p)


def test_e2_defaulted_compute_budget_relabelled_measured(tmp_path):
    p = made(tmp_path, "--thermal-status", "normal")
    assert failed(launder(p, compute_budget="MEASURED")) == ["evidence_states"]


def test_e2_declared_thermal_relabelled_derived(tmp_path):
    p = made(tmp_path, "--thermal-status", "normal")
    assert failed(launder(p, thermal_status="DERIVED")) == ["evidence_states"]


def test_e2_measured_thermal_relabelled_operator(tmp_path):
    p = made(tmp_path, "--thermal-status", "measured")
    assert failed(launder(p, thermal_status="OPERATOR")) == ["evidence_states"]


def test_e2_absent_thermal_given_a_healthy_value_and_the_allow(tmp_path):
    p = made(tmp_path)  # ABSENT, 'unknown', REFUSE
    p["resource_state"]["runtime"]["thermal_status"] = "normal"
    p["decision"] = {"decision": "ALLOW", "reasons": []}
    rec = p["provenance"]["chain"][-1]["record"]
    rec["decision"], rec["reasons"] = "ALLOW", []
    assert failed(launder(p)) == ["evidence_states"]


def test_e2_defaulted_value_that_is_not_the_default(tmp_path):
    p = made(tmp_path, "--thermal-status", "normal")
    p["resource_state"]["runtime"]["compute_budget"] = "constrained"  # still healthy: decision stays ALLOW
    assert failed(launder(p)) == ["evidence_states"]


def test_e2_a_state_evidence_ledger_does_not_define(tmp_path):
    p = made(tmp_path, "--thermal-status", "normal")
    assert failed(launder(p, power_status="VERIFIED")) == ["evidence_states"]


# ---- E3: the fourth limitation line is generated from the tags ---------------------------------
def test_e3_tags_changed_without_the_line(tmp_path):
    p = made(tmp_path, "--thermal-status", "normal")
    p["resource_state"]["evidence_states"]["compute_budget"] = "OPERATOR"  # a valid tag, a stale line
    assert failed(reseal(p)) == ["limitations_declared"]


def test_e3_line_changed_without_the_tags(tmp_path):
    p = made(tmp_path, "--thermal-status", "normal")
    p["known_limitations"][3] = p["known_limitations"][3].replace("compute_budget DEFAULTED",
                                                                  "compute_budget OPERATOR")
    assert failed(reseal(p)) == ["limitations_declared"]


# ---- E4: untagged packages are judged as before -------------------------------------------------
def test_e4_untagged_fixture_verifies_without_the_check():
    pkg = json.loads(vp.canon(make_fixture()))
    names = [n for n, ok, _ in vp.verify(pkg)]
    assert "evidence_states" not in names and failed(pkg) == []


# ---- E5: stated limit - deleting the tags and restoring the old line is a consistent rewrite ----
def test_e5_stated_limit_untagging_verifies_unsigned(tmp_path):
    p = made(tmp_path, "--thermal-status", "normal")
    del p["resource_state"]["evidence_states"]
    p["known_limitations"] = list(vp.V0_LIMITATIONS)
    assert failed(reseal(p)) == []


# ---- the producer refuses to write a promotion ----------------------------------------------------
def test_build_package_refuses_promoted_tags():
    fixture = make_fixture()
    record = EvidenceRecord(record_id="x", input_digest=fixture["artifact"]["sha256"], decision="ALLOW")
    with pytest.raises(ValueError, match="no implicit promotion"):
        build_package(artifact=b"sovereign-veritas package fixture" * 8, artifact_name="x",
                      measurement={"kind": "sha256_chain", "rounds": 1,
                                   "artifact_sha256": fixture["artifact"]["sha256"], "output_sha256": "0"},
                      chain=[record], capability=Capability("c", authorized=True),
                      runtime=RuntimeState("p", "v"),
                      evidence_states={"thermal_status": "OPERATOR", "compute_budget": "MEASURED",
                                       "power_status": "DEFAULTED"})
