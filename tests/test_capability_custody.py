"""Capability custody (docs/CUSTODY_RESULTS.md): a revocation recorded in the registry must reach the decision.

R1: before this fix, CapabilityGovernor.revoke() ledgered the revocation and changed the registry, but
EvidenceWorkflow decided on whatever Capability object the caller passed, so a pre-revocation object still ALLOWed and
executed. R2: EvidenceWorkflow never passed a registry to the Gate, so every capability with a parent was REFUSED.
R3: build_package wrote, and verify_package accepted as CONSISTENT, a package whose registry snapshot revoked the very
capability its gate_inputs called authorized."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from sovereign_veritas.capability import Capability, CapabilityRegistry
from sovereign_veritas.evidence import Ledger, LedgerSink
from sovereign_veritas.governance import CapabilityGovernor
from sovereign_veritas.interfaces.contracts import ActionProposal, Prediction
from sovereign_veritas.package import build_package, package_digest, write_package
from sovereign_veritas.runtime import RuntimeState
from sovereign_veritas.workflow import EvidenceWorkflow

ROOT = Path(__file__).resolve().parents[1]
ART = b"art"
SHA = hashlib.sha256(ART).hexdigest()


class _S:
    def observe(self):
        return "o"

    def predict(self, o):
        return Prediction(value={"output_sha256": "x"}, uncertainty=0.0, model_id="m")

    def verify(self, o, p):
        return {"status": "PASS"}


class _Ex:
    def __init__(self):
        self.effects = 0

    def execute(self, action):
        self.effects += 1
        return "done"


def _governed():
    reg, ledger = CapabilityRegistry(), Ledger()
    reg.register(Capability("act"))
    gov = CapabilityGovernor(reg, LedgerSink(ledger))
    held, _ = gov.authorize("act", record_id="auth-1", input_digest="d1", reason="grant")
    return reg, gov, held


def _run(capability, *, registry=None, name="act", record_id="w1"):
    ex = _Ex()
    wf = EvidenceWorkflow(sensor=_S(), predictor=_S(), verifier=_S(), executor=ex,
                          evidence_sink=LedgerSink(Ledger()), capability_registry=registry)
    r = wf.run(record_id=record_id, input_digest=SHA, capability=capability, runtime=RuntimeState("x", "3"),
               action=ActionProposal(capability=name, requested="act", parameters={}))
    return r, ex.effects


def test_r1_revocation_reaches_the_decision_when_a_registry_is_configured():
    reg, gov, held = _governed()
    gov.revoke("act", record_id="revoke-1", input_digest="d2", reason="compromised")
    r, effects = _run(held, registry=reg)
    assert (r.decision.decision, r.decision.reasons, effects) == ("REFUSE", ("capability_not_authorized",), 0)
    assert r.evidence.metadata["capability_source"] == "registry"
    assert r.evidence.metadata["caller_capability_differs_from_registry"] is True


def test_r1_unrevoked_capability_still_allows_through_the_registry():
    reg, gov, held = _governed()
    r, effects = _run(held, registry=reg)
    assert (r.decision.decision, effects) == ("ALLOW", 1)
    assert r.evidence.metadata["caller_capability_differs_from_registry"] is False


def test_r1_unknown_capability_name_refuses_when_a_registry_is_configured():
    reg, gov, held = _governed()
    r, effects = _run(Capability("ghost", authorized=True), registry=reg, name="ghost")
    assert (r.decision.decision, r.decision.reasons, effects) == ("REFUSE", ("capability_missing",), 0)


def test_r1_without_a_registry_the_caller_supplied_object_still_decides_documented_limit():
    # Kept visible on purpose: with no registry configured, authorization is a label the caller writes (issue #4, B2).
    reg, gov, held = _governed()
    gov.revoke("act", record_id="revoke-1", input_digest="d2", reason="compromised")
    r, effects = _run(held, registry=None)
    assert (r.decision.decision, effects) == ("ALLOW", 1)
    assert r.evidence.metadata["capability_source"] == "caller"


def test_r2_hierarchical_capability_works_through_the_workflow_and_parent_revocation_refuses():
    reg = CapabilityRegistry()
    reg.register(Capability("root", authorized=True))
    reg.register(Capability("child", authorized=True, parent="root"))
    r, effects = _run(reg.get("child"), registry=reg, name="child")
    assert (r.decision.decision, effects) == ("ALLOW", 1)
    reg.revoke("root")
    r, effects = _run(reg.get("child"), registry=reg, name="child", record_id="w2")
    assert (r.decision.decision, r.decision.reasons, effects) == ("REFUSE", ("capability_parent_not_authorized:root",), 0)


def _contradictory_package(reg, held):
    reg.revoke("act")
    r, _ = _run(held)  # no registry: decides on the held object
    return dict(artifact=ART, artifact_name="a", chain=[r.evidence], capability=held, runtime=RuntimeState("x", "3"),
                capability_registry=reg, registry_names=["act"],
                measurement={"artifact_sha256": SHA, "kind": "x", "output_sha256": "x"})


def test_r3_build_package_refuses_a_capability_its_registry_snapshot_contradicts():
    reg, gov, held = _governed()
    with pytest.raises(ValueError, match="registry"):
        build_package(**_contradictory_package(reg, held))


def test_r3_verifier_fails_a_resealed_contradictory_package(tmp_path):
    reg, gov, held = _governed()
    kw = _contradictory_package(reg, held)
    kw["capability_registry"] = None  # build a clean package, then plant the contradiction and reseal
    pkg = build_package(**kw)
    pkg["gate_inputs"]["capability_registry"] = {"act": dict(held.to_dict(), authorized=False)}
    pkg["package_sha256"] = package_digest(pkg)
    path = write_package(pkg, str(tmp_path))
    v = subprocess.run([sys.executable, str(ROOT / "tools" / "verify_package.py"), path, "--allow-recorded-only"],
                       capture_output=True, text=True)
    assert v.returncode == 1, v.stdout
    assert "FAIL  capability_matches_registry" in v.stdout
