"""The Gate commands a vehicle (tools/vehicle_action.py). Registered in docs/VEHICLE_ACTION.md.

These tests use the "fake" backend, a canned stand-in that is NOT a vehicle; the ArduPilot SITL
runs are recorded in the doc. The check itself is tested directly as well.
"""
import json
import os
import pathlib
import subprocess
import sys

import pytest

from test_thermal_policy import ROOT, failed, reseal, tree, vp

TOOL = ROOT / "tools" / "vehicle_action.py"


def run(tmp_path, scenario, *flags):
    zones = tmp_path / "cool"
    if not zones.exists():
        tree(zones)
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    p = subprocess.run([sys.executable, str(TOOL), "--link", f"fake:{scenario}", *flags, "--thermal-root", str(zones)],
                       capture_output=True, text=True, env=dict(os.environ, HOME=str(home)), timeout=120)
    if p.returncode != 0:
        return None, p
    path = next(line.split()[1] for line in p.stdout.splitlines() if line.startswith("package "))
    pkg = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    os.remove(path)
    return pkg, p


CASES = [  # scenario, flags, decision, reasons, commands sent?
    ("healthy_ground", ["--action", "takeoff", "--alt", "10"], "ALLOW", [], True),                         # V1
    ("healthy_air", ["--action", "goto", "--north", "100", "--alt", "20"], "ALLOW", [], True),            # V2
    ("healthy_air", ["--action", "goto", "--north", "600", "--alt", "20"], "REFUSE", ["verification_not_passed"], False),  # V3
    ("healthy_air", ["--action", "goto", "--north", "50", "--alt", "150"], "REFUSE", ["verification_not_passed"], False),  # V4
    ("healthy_air", ["--action", "disarm"], "REFUSE", ["action_not_permitted_by_policy"], False),        # V5
    ("gps_off", ["--action", "goto", "--north", "50", "--alt", "20"], "REFUSE", ["verification_not_passed"], False),      # V6
    ("gps_off", ["--action", "land"], "ALLOW", [], True),                                                  # V7
    ("gps_off", ["--action", "rtl"], "REFUSE", ["verification_not_passed"], False),
    ("battery_low", ["--action", "goto", "--north", "50", "--alt", "20"], "REFUSE", ["verification_not_passed"], False),
    ("battery_low", ["--action", "land"], "ALLOW", [], True),
    ("outside_fence", ["--action", "goto", "--north", "0", "--alt", "20"], "REFUSE", ["verification_not_passed"], False),
    ("outside_fence", ["--action", "rtl"], "ALLOW", [], True),
]


@pytest.mark.parametrize("scenario,flags,decision,reasons,sent", CASES)
def test_decisions_commands_and_verification(tmp_path, scenario, flags, decision, reasons, sent):
    pkg, p = run(tmp_path, scenario, *flags)
    assert pkg is not None, p.stdout + p.stderr
    m = pkg["measurement"]
    assert [pkg["decision"]["decision"], pkg["decision"]["reasons"]] == [decision, reasons]
    assert bool(m["commands_sent"]) is sent and (m["outcome"] is not None) is sent
    results = {n: ok for n, ok, _ in vp.verify(pkg)}
    assert all(results.values()), results
    assert results["vehicle_check_bound"] is True and m["backend"] == "fake"


# ---- the check, directly ------------------------------------------------------------------------
spec = __import__("importlib.util").util.spec_from_file_location("vehicle_action", TOOL)
va = __import__("importlib.util").util.module_from_spec(spec)
spec.loader.exec_module(va)
FENCE = {"lat_e7": 353632000, "lon_e7": -969270000, "radius_m": 300.0, "max_alt_m": 120.0}
LIMITS = {"min_fix_type": 3, "min_sats": 6, "min_battery_pct": 30}
GOOD = dict(va.FakeVehicle.SCENARIOS["healthy_air"], lat_e7=FENCE["lat_e7"], lon_e7=FENCE["lon_e7"])


def req(action, **params):
    return {"schema": va.REQUEST_SCHEMA, "action": action, "params": params, "fence": FENCE, "limits": LIMITS}


def test_land_is_never_refused_for_navigation_or_battery():
    bad = dict(GOOD, gps_fix_type=0, gps_sats=0, ekf_flags=1024, battery_pct=-1, lat_e7=0, lon_e7=0)
    assert va.vehicle_check(req("land"), bad)["verdict"] == "PASS"


def test_the_gps_glitch_flag_alone_fails_movement():
    assert va.vehicle_check(req("goto", alt_m=20, lat_e7=FENCE["lat_e7"], lon_e7=FENCE["lon_e7"]),
                            dict(GOOD, ekf_flags=GOOD["ekf_flags"] | 32768))["why"].startswith("ekf reports a gps glitch")


def test_fence_edge_and_unknown_battery():
    lat, _ = va.offset(FENCE["lat_e7"], FENCE["lon_e7"], 299, 0)
    assert va.vehicle_check(req("goto", alt_m=20, lat_e7=lat, lon_e7=FENCE["lon_e7"]), GOOD)["verdict"] == "PASS"
    lat, _ = va.offset(FENCE["lat_e7"], FENCE["lon_e7"], 301, 0)
    assert va.vehicle_check(req("goto", alt_m=20, lat_e7=lat, lon_e7=FENCE["lon_e7"]), GOOD)["verdict"] == "FAIL"
    assert "battery remaining unknown" in va.vehicle_check(req("takeoff", alt_m=10), dict(GOOD, battery_pct=-1))["why"]


def test_nonfinite_safety_inputs_fail_closed():
    cases = [
        (dict(GOOD, battery_pct=float("nan")), "battery"),
        (dict(GOOD, battery_pct=float("inf")), "battery"),
        (dict(GOOD, battery_pct=float("-inf")), "battery"),
        (dict(GOOD, gps_fix_type=float("nan")), "gps fix"),
        (dict(GOOD, gps_fix_type=float("inf")), "gps fix"),
        (dict(GOOD, gps_sats=float("nan")), "satellites"),
        (dict(GOOD, gps_sats=float("inf")), "satellites"),
    ]

    for snap, expected in cases:
        result = va.vehicle_check(req("takeoff", alt_m=10), snap)
        assert result["verdict"] == "FAIL"
        assert expected in result["why"]
        assert "non-finite" in result["why"]


def test_nonfinite_altitude_fails_closed():
    for alt in (float("nan"), float("inf"), float("-inf")):
        result = va.vehicle_check(req("takeoff", alt_m=alt), GOOD)
        assert result["verdict"] == "FAIL"
        assert "altitude" in result["why"]


def test_nonfinite_distance_fails_closed():
    for value in (float("nan"), float("inf"), float("-inf")):
        snap = dict(GOOD, lat_e7=value)
        result = va.vehicle_check(req("takeoff", alt_m=10), snap)
        assert result["verdict"] == "FAIL"
        assert "distance is non-finite" in result["why"]


def test_nonfinite_verifier_matches_producer():
    cases = [
        dict(GOOD, battery_pct=float("nan")),
        dict(GOOD, battery_pct=float("inf")),
        dict(GOOD, battery_pct=float("-inf")),
        dict(GOOD, gps_fix_type=float("nan")),
        dict(GOOD, gps_fix_type=float("inf")),
        dict(GOOD, gps_sats=float("nan")),
        dict(GOOD, gps_sats=float("inf")),
        dict(GOOD, lat_e7=float("nan")),
        dict(GOOD, lat_e7=float("inf")),
    ]

    for snap in cases:
        r = req("takeoff", alt_m=10)
        assert va.vehicle_check(r, snap) == vp.vehicle_check(r, snap), snap


def test_the_verifier_reimplementation_agrees_with_the_tool():
    snaps = [GOOD, dict(GOOD, gps_fix_type=2), dict(GOOD, battery_pct=10), dict(GOOD, ekf_flags=167),
             dict(GOOD, lat_e7=GOOD["lat_e7"] + 40000)]
    reqs = [req("takeoff", alt_m=10), req("takeoff", alt_m=500), req("goto", alt_m=20, lat_e7=353650000, lon_e7=-969270000),
            req("goto", alt_m=20, lat_e7=1, lon_e7=True), req("rtl"), req("land"), req("disarm")]
    for r in reqs:
        for s in snaps:
            assert va.vehicle_check(r, s) == vp.vehicle_check(r, s), (r, s)


# ---- V8: a resealing attacker ---------------------------------------------------------------------
def test_v8_snapshot_edited_fails_recompute(tmp_path):
    pkg, _ = run(tmp_path, "gps_off", "--action", "goto", "--north", "50", "--alt", "20")
    pkg["measurement"]["telemetry_before"]["gps_fix_type"] = 6
    assert "measurement_recomputed" in failed(reseal(pkg))


def test_v8_commands_recorded_under_refuse_fail_the_binding(tmp_path):
    pkg, _ = run(tmp_path, "healthy_air", "--action", "goto", "--north", "600", "--alt", "20")
    pkg["measurement"]["commands_sent"] = ["SET_MODE GUIDED"]
    assert failed(reseal(pkg)) == ["vehicle_check_bound"]


def test_v8_refused_record_flipped_to_allow_fails_the_binding(tmp_path):
    pkg, _ = run(tmp_path, "healthy_air", "--action", "goto", "--north", "600", "--alt", "20")
    pkg["decision"] = {"decision": "ALLOW", "reasons": []}
    rec = pkg["provenance"]["chain"][-1]["record"]
    rec["decision"], rec["reasons"], rec["verification"]["status"] = "ALLOW", [], "PASS"
    assert failed(reseal(pkg)) == ["vehicle_check_bound"]


def test_v8_requested_action_changed_fails_the_binding(tmp_path):
    pkg, _ = run(tmp_path, "healthy_air", "--action", "disarm")
    pkg["provenance"]["chain"][-1]["record"]["action"]["requested"] = "land"
    assert "vehicle_check_bound" in failed(reseal(pkg))


def test_v8_outcome_dropped_from_a_run_action_fails_the_binding(tmp_path):
    pkg, _ = run(tmp_path, "healthy_ground", "--action", "takeoff", "--alt", "10")
    pkg["measurement"]["outcome"] = None
    assert failed(reseal(pkg)) == ["vehicle_check_bound"]


def test_v8_stated_limit_a_consistent_snapshot_rewrite_verifies_unsigned(tmp_path):
    """Documented, not a pass: the snapshot is recorded data; only a signature binds it."""
    pkg, _ = run(tmp_path, "gps_off", "--action", "goto", "--north", "50", "--alt", "20")
    m = pkg["measurement"]
    m["telemetry_before"] = dict(m["telemetry_before"], gps_fix_type=6, gps_sats=10, ekf_flags=831)
    m["output_sha256"] = vp.sha(vp.canon(m["telemetry_before"]))
    m["check"] = vp.vehicle_check(json.loads(__import__("base64").b64decode(pkg["artifact"]["bytes_b64"])),
                                  m["telemetry_before"])
    rec = pkg["provenance"]["chain"][-1]["record"]
    rec["prediction"]["value"]["output_sha256"] = m["output_sha256"]
    rec["verification"]["status"] = "PASS"
    # the Gate would then ALLOW, so the decision is rewritten too; commands stay empty (nothing ran)
    pkg["decision"] = {"decision": "ALLOW", "reasons": []}
    rec["decision"], rec["reasons"] = "ALLOW", []
    assert failed(reseal(pkg)) == []


def test_no_vehicle_is_could_not_run(tmp_path):
    pytest.importorskip("pymavlink")
    home = tmp_path / "home"
    home.mkdir()
    p = subprocess.run([sys.executable, str(TOOL), "--link", "tcp:127.0.0.1:9", "--action", "land"],
                       capture_output=True, text=True, env=dict(os.environ, HOME=str(home)), timeout=120)
    assert p.returncode == 2 and "COULD NOT RUN" in p.stdout and not list(home.glob("sv_package_*"))
    # TVA-1 V5 (docs/TVA1_RESULTS.md): without this line the test also passed with pymavlink missing, through the
    # "pymavlink is not installed" COULD NOT RUN, so it could not tell an unreachable vehicle from a missing library.
    assert "no vehicle at" in p.stdout or "no heartbeat from" in p.stdout, p.stdout


# ---- V12: cross-check against an independent position (fake backend; SITL runs in the doc) ------------
XC = ["--max-disagreement", "25", "--xpos-sigma", "3"]


@pytest.mark.parametrize("scenario,flags,decision,why", [
    ("healthy_air", ["--action", "goto", "--north", "50", "--alt", "20", *XC], "ALLOW", "all goto rules hold"),
    ("spoofed", ["--action", "goto", "--north", "-250", "--alt", "20", *XC], "REFUSE", "disagree by 111"),
    ("spoofed", ["--action", "rtl", *XC], "REFUSE", "disagree by 111"),
    ("spoofed", ["--action", "land", *XC], "ALLOW", "all land rules hold"),
    ("spoofed", ["--action", "goto", "--north", "-250", "--alt", "20"], "ALLOW", "all goto rules hold"),  # V12e
    ("healthy_air", ["--action", "goto", "--north", "50", "--alt", "20", "--max-disagreement", "25"], "REFUSE",
     "no independent position"),
])
def test_v12_cross_check(tmp_path, scenario, flags, decision, why):
    pkg, p = run(tmp_path, scenario, *flags)
    assert pkg is not None, p.stdout + p.stderr
    assert pkg["decision"]["decision"] == decision and why in pkg["measurement"]["check"]["why"]
    assert all(ok for _, ok, _ in vp.verify(pkg)), [n for n, ok, _ in vp.verify(pkg) if not ok]


def test_v12_verifier_agrees_on_cross_check_snapshots():
    lim = dict(LIMITS, max_nav_disagreement_m=25)
    r = {"schema": va.REQUEST_SCHEMA, "action": "goto", "fence": FENCE, "limits": lim,
         "params": {"alt_m": 20, "lat_e7": FENCE["lat_e7"], "lon_e7": FENCE["lon_e7"]}}
    for dn in (0, 2000, 2300, 10000):
        s = dict(GOOD, xpos_lat_e7=GOOD["lat_e7"] + dn, xpos_lon_e7=GOOD["lon_e7"], xpos_source="t")
        assert va.vehicle_check(r, s) == vp.vehicle_check(r, s)
    assert va.vehicle_check(r, GOOD) == vp.vehicle_check(r, GOOD)
