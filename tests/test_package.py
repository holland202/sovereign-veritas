"""sv.package/0: reconstruct and challenge a gated run from the package alone.

Registered before this code ran: docs/EVIDENCE_PACKAGE.md (P0-P4). The verifier is
tools/verify_package.py, which imports nothing from sovereign_veritas.
"""
import base64
import copy
import hashlib
import importlib.util
import itertools
import json
import pathlib
import subprocess
import sys

from sovereign_veritas.capability import Capability, CapabilityRegistry
from sovereign_veritas.decision import Gate
from sovereign_veritas.evidence import EvidenceRecord, Ledger, canonical_json
from sovereign_veritas.package import build_package
from sovereign_veritas.runtime import RuntimeState
from sovereign_veritas.thermal import read_zones
from sovereign_veritas.verifier_registry import VerifierRegistry

ROOT = pathlib.Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("verify_package", ROOT / "tools" / "verify_package.py")
vp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vp)

ARTIFACT = b"sovereign-veritas package fixture" * 8
ROUNDS = 64
MISSING = object()


def chain_hex(data, rounds=ROUNDS):
    h = data
    for _ in range(rounds):
        h = hashlib.sha256(h).digest()
    return h.hex()


def cap_registry():
    reg = CapabilityRegistry()
    reg.register(Capability("root-on", authorized=True))
    reg.register(Capability("root-off", authorized=False))
    return reg


def validation(status="VALIDATED"):
    reg = VerifierRegistry(min_coverage=0.5)
    reg.register("v-recompute", object())
    if status != "UNTESTED":
        reg.record_probe("v-recompute", passed=status == "VALIDATED")
    return reg.validation("v-recompute")


BASE = dict(status="PASS", authorized=True, parent=None, binding="read_sensor", thermal="normal",
            compute="available", evidence=True, quality=0.9, steps=1, policy=["read_sensor"])


def make(cfg=None, thermal=None, val_status="VALIDATED"):
    c = dict(BASE, **(cfg or {}))
    sha = hashlib.sha256(ARTIFACT).hexdigest()
    out = chain_hex(ARTIFACT)
    meta = {"step_count": c["steps"], "evidence_quality": c["quality"]}
    if c["evidence"] is not MISSING:
        meta["calibration"] = c["evidence"]
    ledger = Ledger()
    ledger.append(EvidenceRecord(record_id="genesis", input_digest="session",
                                 timestamp="2026-01-01T00:00:00+00:00"))
    record = EvidenceRecord(record_id="run", input_digest=sha, capability="read_sensor",
                            prediction={"value": {"output_sha256": out}},
                            verification={"status": c["status"], "verifier_id": "v-recompute"},
                            action={"capability": c["binding"], "requested": "read_sensor"},
                            metadata=meta, timestamp="2026-01-01T00:00:01+00:00")
    cap = Capability("read_sensor", authorized=c["authorized"], required_evidence=("calibration",),
                     parent=c["parent"], min_evidence_quality=0.5, max_steps=3)
    runtime = RuntimeState("fixture", "n/a", thermal_status=c["thermal"], compute_budget=c["compute"])
    policy = {"allow_only": c["policy"]}
    creg = cap_registry()
    d = Gate().evaluate(record, cap, runtime, policy=policy, registry=creg)
    ledger.append(record.with_updates(decision=d.decision, reasons=d.reasons))
    return build_package(artifact=ARTIFACT, artifact_name="fixture",
                         measurement={"kind": "sha256_chain", "rounds": ROUNDS, "artifact_sha256": sha,
                                      "output_sha256": out, "elapsed_ms": 1.0},
                         chain=ledger.all(), capability=cap, runtime=runtime, policy=policy,
                         capability_registry=creg, registry_names=("root-on", "root-off"),
                         verifier_id="v-recompute", validation=validation(val_status),
                         thermal=thermal)


def roundtrip(pkg):
    return json.loads(canonical_json(pkg))


def failed(pkg):
    return sorted(name for name, ok, _ in vp.verify(roundtrip(pkg)) if not ok)


def reseal(pkg):
    """The adversary's best move: recompute every digest it can after a rewrite."""
    prev = None
    for entry in pkg["provenance"]["chain"]:
        entry["record"]["previous_digest"] = prev
        entry["record_digest"] = prev = vp.sha(vp.canon(entry["record"]))
    pkg["package_sha256"] = vp.sha(vp.canon({k: v for k, v in pkg.items() if k != "package_sha256"}))
    return pkg


def thermal_fixture(tmp_path):
    for i, (t, v) in enumerate([("cpu-0-0-0", 99600), ("battery", 32100), ("mmw0", -273000),
                                ("pm8550-bcl-lvl0", 0), ("ac", 34200)]):
        d = tmp_path / f"thermal_zone{i}"
        d.mkdir()
        (d / "type").write_text(t + "\n")
        (d / "temp").write_text(f"{v}\n")
    return read_zones(str(tmp_path))


def test_p0_untouched_verifies_and_resealed_decision_flip_fails(tmp_path):
    pkg = make(thermal=thermal_fixture(tmp_path))
    assert failed(pkg) == []
    flip = roundtrip(pkg)
    flip["decision"]["decision"] = "DEFER"
    flip["provenance"]["chain"][-1]["record"]["decision"] = "DEFER"
    assert "gate_replay" in failed(reseal(flip))


AXES = [
    ("status", ["PASS", "INSUFFICIENT_EVIDENCE", "FAIL"]), ("authorized", [True, False]),
    ("parent", [None, "root-off"]), ("binding", ["read_sensor", "write_actuator"]),
    ("thermal", ["normal", "hot", "unknown"]), ("compute", ["available", "exhausted"]),
    ("evidence", [True, MISSING]), ("quality", [0.9, 0.2]), ("steps", [1, 5]),
    ("policy", [["read_sensor"], ["other"]]),
]


def test_p1_every_lattice_decision_replays_exactly():
    names = [a for a, _ in AXES]
    bad = []
    points = list(itertools.product(*[v for _, v in AXES]))
    for values in points:
        pkg = make(dict(zip(names, values)))
        if failed(pkg):
            bad.append((values, failed(pkg)))
    assert len(points) == 2304 and bad == []


def _downgrade(p):
    """K3: relabel the measurement kind so the verifier cannot recompute it, then forge the output."""
    p["measurement"]["kind"] = "remote"
    p["measurement"]["output_sha256"] = "f" * 64
    p["provenance"]["chain"][-1]["record"]["prediction"]["value"]["output_sha256"] = "f" * 64


def _mutations():
    def set_path(*path_and_value):
        *path, value = path_and_value

        def m(p):
            node = p
            for k in path[:-1]:
                node = node[k]
            node[path[-1]] = value
        return m

    def rec(key, value):
        return lambda p: p["provenance"]["chain"][-1]["record"].__setitem__(key, value)

    def swap_artifact(p):
        new = b"forged artifact bytes"
        sha = hashlib.sha256(new).hexdigest()
        p["artifact"].update(bytes_b64=base64.b64encode(new).decode(), sha256=sha)
        p["measurement"]["artifact_sha256"] = sha
        p["provenance"]["chain"][-1]["record"]["input_digest"] = sha

    def forge_output(p):
        p["measurement"]["output_sha256"] = "f" * 64
        p["provenance"]["chain"][-1]["record"]["prediction"]["value"]["output_sha256"] = "f" * 64

    def decision_to(value, reasons):
        def m(p):
            p["decision"].update(decision=value, reasons=reasons)
            rec("decision", value)(p)
            rec("reasons", reasons)(p)
        return m

    def zone(i, **kv):
        return lambda p: p["resource_state"]["thermal"]["zones"][i].update(kv)

    return {
        "decision ALLOW->REFUSE": decision_to("REFUSE", ["capability_not_authorized"]),
        "reasons appended": decision_to("ALLOW", ["runtime_not_healthy"]),
        "runtime thermal -> hot": set_path("resource_state", "runtime", "thermal_status", "hot"),
        "policy excludes action": set_path("gate_inputs", "policy", "allow_only", ["other"]),
        "capability unauthorized": set_path("gate_inputs", "capability", "authorized", False),
        "capability demands more evidence":
            set_path("gate_inputs", "capability", "required_evidence", ["calibration", "extra"]),
        "capability renamed": set_path("gate_inputs", "capability", "name", "other"),
        "artifact swapped (digests updated)": swap_artifact,
        "measurement output forged": forge_output,
        "validation VALIDATED with a failed probe":
            set_path("verifier", "validation", "failed_probes", 1),
        "validation relabelled UNTESTED": set_path("verifier", "validation", "status", "UNTESTED"),
        "verifier id swapped": set_path("verifier", "verifier_id", "v-other"),
        "identity claimed bound": set_path("verifier", "identity_bound", True),
        "thermal zone raw edited": zone(0, raw=45000),
        "offline zone relabelled ok": zone(2, status="ok"),
        "thermal summary max edited":
            set_path("resource_state", "thermal", "summary", "domains", "cpu_core", "max_c", 40.0),
        "freshness claimed PROVEN": set_path("freshness", "status", "PROVEN"),
        "limitation deleted": lambda p: p["known_limitations"].pop(1),
        "contradicting limitation appended":
            lambda p: p["known_limitations"].append("authenticity: signed by device hardware"),
        "measurement kind downgraded, output forged": _downgrade,
    }


def test_p2_every_inconsistent_rewrite_is_caught_after_full_reseal(tmp_path):
    base = make(thermal=thermal_fixture(tmp_path))
    survivors = []
    for name, mutate in _mutations().items():
        p = roundtrip(base)
        mutate(p)
        if not failed(reseal(p)):
            survivors.append(name)
    assert survivors == []


def test_recorded_only_kind_needs_explicit_opt_in():
    p = roundtrip(make())
    p["measurement"]["kind"] = "remote"
    reseal(p)
    assert failed(p) == ["measurement_recomputed"]
    assert all(ok for _, ok, _ in vp.verify(roundtrip(p), allow_recorded_only=True))


def test_producer_and_verifier_agree_on_limitations():
    from sovereign_veritas.package import KNOWN_LIMITATIONS
    assert tuple(KNOWN_LIMITATIONS) == vp.V0_LIMITATIONS


def test_p3_freshness_is_never_proven_by_default():
    pkg = make()
    assert pkg["freshness"] == {"status": "NOT_PROVEN", "witness": None}


def test_p4_boundary_a_consistent_rewrite_verifies():
    """Registered as UNDETECTED by design: self-consistency is not authenticity."""
    p = roundtrip(make())
    p["resource_state"]["runtime"]["thermal_status"] = "hot"
    p["decision"].update(decision="DEFER", reasons=["runtime_not_healthy"])
    p["provenance"]["chain"][-1]["record"].update(decision="DEFER", reasons=["runtime_not_healthy"])
    assert failed(reseal(p)) == []


def test_cli_exit_codes(tmp_path):
    good = tmp_path / "good.json"
    good.write_text(canonical_json(make()))
    bad_pkg = roundtrip(make())
    bad_pkg["gate_inputs"]["capability"]["authorized"] = False
    bad = tmp_path / "bad.json"
    bad.write_text(canonical_json(reseal(bad_pkg)))
    run = lambda f: subprocess.run([sys.executable, str(ROOT / "tools" / "verify_package.py"), str(f)],
                                   capture_output=True, text=True).returncode
    assert (run(good), run(bad), run(tmp_path / "absent.json")) == (0, 1, 2)
