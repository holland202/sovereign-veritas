"""Measured thermal_status: derived from recorded zones, recomputed by the verifier.

Registered before this code ran: docs/EVIDENCE_PACKAGE.md, "Measured thermal status" (T0-T7).
T5 and T6 need the S25 and are not here.
"""
import copy
import importlib.util
import json
import os
import pathlib
import shutil
import subprocess
import sys

import pytest

from sovereign_veritas.thermal import read_zones
from sovereign_veritas.thermal_policy import LIMITS_MDEG, derive_thermal_status

ROOT = pathlib.Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("verify_package", ROOT / "tools" / "verify_package.py")
vp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vp)

# A minimal S25-shaped tree: every limited domain present and cool, plus zones that must never decide.
COOL = {"cpu-0-0-0": 41000, "cpuss-0-0": 43000, "gpuss-0": 40000, "nsphvx-0": 39000,
        "battery": 33000, "sys-therm-0": 36000, "mmw0": -273000, "sdr0": 47000, "ac": 34000,
        "pm8550-bcl-lvl0": 0}


def tree(path, overrides=None, drop=()):
    zones = dict(COOL, **(overrides or {}))
    for i, (ztype, value) in enumerate(z for z in zones.items() if z[0] not in drop):
        d = path / f"thermal_zone{i}"
        d.mkdir(parents=True)
        (d / "type").write_text(ztype + "\n")
        (d / "temp").write_text(f"{value}\n")
    return path


def both(path):
    """The kernel's derivation and the verifier's re-implementation, on the same zones."""
    zones = [z.to_dict() for z in read_zones(str(path))]
    return derive_thermal_status(zones, LIMITS_MDEG)[0], vp.derive_thermal(zones, vp.THERMAL_POLICIES["s25-uncalibrated-v0"])


# ---- T1: derivation --------------------------------------------------------------------------
@pytest.mark.parametrize("overrides,drop,expected", [
    ({}, (), "normal"),
    ({"cpu-0-0-0": 95000}, (), "hot"),                  # exactly at the limit
    ({"cpu-0-0-0": 94999}, (), "normal"),
    ({"battery": 45000}, (), "hot"),
    ({"sys-therm-0": 50000}, (), "hot"),
    ({"gpuss-0": 104200}, (), "hot"),
    ({}, ("nsphvx-0",), "unknown"),                     # a limited domain with no zone
    ({"nsphvx-0": "garbage"}, (), "unknown"),           # unreadable
    ({"cpu-0-0-0": 200000}, (), "unknown"),             # out_of_range
    ({"battery": -273000}, (), "unknown"),              # only zone offline -> no ok zone
    ({"cpu-0-1-0": 200000}, (), "unknown"),             # out_of_range beside an ok zone still decides
    ({"nsphmx-0": "garbage"}, (), "unknown"),           # unreadable beside an ok zone still decides
    ({"sdr0": 140000, "ac": 140000, "mmw0": 140000}, (), "normal"),  # unlimited domains never decide
    ({"cpu-0-1-0": -273000}, (), "normal"),             # an offline zone beside an ok one is skipped
])
def test_t1_derivation(tmp_path, overrides, drop, expected):
    assert both(tree(tmp_path / "z", overrides, drop)) == (expected, expected)


def test_t1_offline_zones_skipped_not_counted_as_cold(tmp_path):
    hot = both(tree(tmp_path / "z", {"cpu-0-0-0": 99000, "cpu-0-1-0": -273000}))
    assert hot == ("hot", "hot")


# ---- T2/T4: the real tool, end to end --------------------------------------------------------
def make(tmp_path, root, *extra):
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    env = dict(os.environ, HOME=str(home))
    out = subprocess.run([sys.executable, str(ROOT / "tools" / "make_package.py"), "--rounds", "10",
                          "--thermal-status", "measured", "--thermal-root", str(root), *extra],
                         capture_output=True, text=True, env=env, check=True).stdout
    path = next(line.split()[1] for line in out.splitlines() if line.startswith("package "))
    ver = subprocess.run([sys.executable, str(ROOT / "tools" / "verify_package.py"), path],
                         capture_output=True, text=True)
    with open(path, encoding="utf-8") as fh:
        pkg = json.load(fh)
    os.remove(path)
    return pkg, ver


@pytest.mark.parametrize("overrides,status,decision,reasons", [
    ({}, "normal", "ALLOW", []),
    ({"cpu-0-0-0": 99600}, "hot", "DEFER", ["runtime_not_healthy"]),
    ({"battery": "garbage"}, "unknown", "REFUSE", ["runtime_state_unavailable"]),
])
def test_t2_gate_consequence_and_verifies(tmp_path, overrides, status, decision, reasons):
    pkg, ver = make(tmp_path, tree(tmp_path / "z", overrides))
    assert pkg["resource_state"]["runtime"]["thermal_status"] == status
    assert [pkg["decision"]["decision"], pkg["decision"]["reasons"]] == [decision, reasons]
    executed = pkg["provenance"]["chain"][-1]["record"]["metadata"].get("execution_status")
    assert (executed is not None) == (decision == "ALLOW")
    assert ver.returncode == 0, ver.stdout
    assert f"PASS  thermal_status_derived" in ver.stdout and f"recomputed {status}" in ver.stdout
    assert "the four statements, resource state measured" in ver.stdout


def test_t4_no_zones_refuses_and_verifies(tmp_path):
    pkg, ver = make(tmp_path, tmp_path / "absent")
    assert pkg["resource_state"]["runtime"]["thermal_status"] == "unknown"
    assert pkg["decision"] == {"decision": "REFUSE", "reasons": ["runtime_state_unavailable"]}
    assert ver.returncode == 0, ver.stdout


def test_declared_mode_has_no_thermal_policy(tmp_path):
    """Was test_declared_mode_is_unchanged. Since I2 (docs/INTEGRATION.md) a declared package also
    carries evidence states, so its fourth limitation is generated from them, not the v0 line."""
    home = tmp_path / "home"
    home.mkdir()
    out = subprocess.run([sys.executable, str(ROOT / "tools" / "make_package.py"), "--rounds", "10",
                          "--thermal-status", "normal", "--thermal-root", str(tree(tmp_path / "z"))],
                         capture_output=True, text=True, env=dict(os.environ, HOME=str(home)),
                         check=True).stdout
    path = next(line.split()[1] for line in out.splitlines() if line.startswith("package "))
    pkg = json.loads(pathlib.Path(path).read_text())
    assert "thermal_policy" not in pkg["resource_state"]
    assert pkg["known_limitations"][:3] == list(vp.V0_LIMITATIONS)[:3]
    assert pkg["known_limitations"][3] == vp.evidence_statement(pkg["resource_state"]["evidence_states"])
    assert not [n for n, ok, _ in vp.verify(pkg) if n == "thermal_status_derived"]


# ---- T3: binding against a resealing attacker ------------------------------------------------
def reseal(pkg):
    prev = None
    for entry in pkg["provenance"]["chain"]:
        entry["record"]["previous_digest"] = prev
        entry["record_digest"] = prev = vp.sha(vp.canon(entry["record"]))
    pkg["package_sha256"] = vp.sha(vp.canon({k: v for k, v in pkg.items() if k != "package_sha256"}))
    return pkg


def failed(pkg):
    return sorted(n for n, ok, _ in vp.verify(json.loads(vp.canon(pkg))) if not ok)


@pytest.fixture
def hot_pkg(tmp_path):
    pkg, ver = make(tmp_path, tree(tmp_path / "z", {"cpu-0-0-0": 99600}))
    assert ver.returncode == 0 and failed(pkg) == []
    return pkg


def to_allow(pkg):
    pkg["resource_state"]["runtime"]["thermal_status"] = "normal"
    pkg["decision"] = {"decision": "ALLOW", "reasons": []}
    rec = pkg["provenance"]["chain"][-1]["record"]
    rec["decision"], rec["reasons"] = "ALLOW", []
    return pkg


def test_t3_status_rewritten_to_normal_with_matching_allow_fails(hot_pkg):
    assert failed(reseal(to_allow(copy.deepcopy(hot_pkg)))) == ["thermal_status_derived"]


def test_t3_raised_limit_fails(hot_pkg):
    p = to_allow(copy.deepcopy(hot_pkg))
    p["resource_state"]["thermal_policy"]["limits_mdeg"]["cpu_core"] = 200000
    assert "thermal_status_derived" in failed(reseal(p))


def test_t3_renamed_policy_fails(hot_pkg):
    p = to_allow(copy.deepcopy(hot_pkg))
    p["resource_state"]["runtime"]["metadata"]["thermal_policy"] = "lenient-v0"
    p["resource_state"]["thermal_policy"]["id"] = "lenient-v0"
    assert "thermal_status_derived" in failed(reseal(p))


def test_t3_deleted_snapshot_fails(hot_pkg):
    p = to_allow(copy.deepcopy(hot_pkg))
    del p["measurement"]["thermal_before"]
    assert "thermal_status_derived" in failed(reseal(p))


def test_t3_relabelled_declared_fails(hot_pkg):
    p = to_allow(copy.deepcopy(hot_pkg))
    p["resource_state"]["runtime"]["metadata"]["thermal_status_source"] = "declared"
    # Registered (T3): fails thermal_status_derived. Since I2 the DERIVED tag also fails
    # evidence_states; limitations_declared now follows the tags as written, so it passes.
    assert {"thermal_status_derived", "evidence_states"} <= set(failed(reseal(p)))


def test_t3_stated_limit_full_relabel_verifies_unsigned(hot_pkg):
    """Documented, not a pass: rewriting every trace of 'measured' is a fully consistent rewrite."""
    p = to_allow(copy.deepcopy(hot_pkg))
    p["resource_state"]["runtime"]["metadata"] = {"thermal_status_source": "declared"}
    del p["resource_state"]["thermal_policy"]
    del p["resource_state"]["evidence_states"]  # since I2, "every trace" includes the DERIVED tag
    p["known_limitations"] = list(vp.V0_LIMITATIONS)
    assert failed(reseal(p)) == []


def test_t3_stated_limit_lowered_readings_verify_unsigned(hot_pkg):
    """Documented, not a pass: raw readings are recorded data; only a signature binds them."""
    p = to_allow(copy.deepcopy(hot_pkg))
    for z in p["measurement"]["thermal_before"]:
        if z["type"] == "cpu-0-0-0":
            z["raw"] = 41000
    assert failed(reseal(p)) == []


# ---- T0: the published declared package is unchanged -----------------------------------------
def test_t0_published_package_still_verifies():
    """Consistency and signature only. Its witness status belongs to test_published_evidence.py: it
    is LATEST_WITNESSED(1) until a newer package is witnessed, then STALE - by design."""
    pkg = ROOT / "evidence" / "sv_package_5bfc70dfcfa2.json"
    args = [sys.executable, str(ROOT / "tools" / "verify_package.py"), str(pkg)]
    if shutil.which("ssh-keygen"):
        args += ["--signature", f"{pkg}.sig", "--allowed-signers", str(ROOT / "keys" / "allowed_signers"),
                 "--identity", "holland202"]
    out = subprocess.run(args, capture_output=True, text=True)
    assert out.returncode == 0, out.stdout
    lines = out.stdout.splitlines()
    assert sum(l.startswith("PASS") for l in lines) == (19 if shutil.which("ssh-keygen") else 18)
    assert not any(l.startswith("FAIL") for l in lines)
    assert "thermal_status_derived" not in out.stdout
