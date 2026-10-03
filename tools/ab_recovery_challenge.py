#!/usr/bin/env python3
"""ab_recovery_challenge.py - Amos Tipton's A/B Recovery Challenge, run against unmodified code.

Registered in docs/AB_RECOVERY_PREREG.md (commit 7fb1c48) before this file existed. The challenge
was proposed by Amos Tipton; see the registration for provenance.

A = the autopilot's GNSS position. B = the independent position. For every case in the registered
matrix, the real vehicle_check and the real Gate (through EvidenceWorkflow, wired as in
tools/vehicle_action.py main()) decide goto / centre-goto / rtl / land, with the cross-check on
(max_nav_disagreement_m = 25) and off. The executor only records commands. Nothing flies.

    python tools/ab_recovery_challenge.py            # prints the table, writes results/ab_recovery/
Exit: 0 every registered prediction held | 1 at least one did not | 2 could not run
"""
import copy, hashlib, json, os, subprocess, sys, tempfile

sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

PINNED = "facadc22d5d62e8288f6a6c97c0de90ff3a0e61a"
FILES = ("tools/vehicle_action.py", "sovereign_veritas/decision.py", "sovereign_veritas/workflow.py")


def could_not_run(msg):
    print(f"COULD NOT RUN: {msg}")
    sys.exit(2)


# C2: refuse to run against modified implementation files
for f in FILES:
    p = subprocess.run(["git", "-C", ROOT, "diff", "--quiet", PINNED, "--", f])
    if p.returncode != 0:
        could_not_run(f"{f} differs from {PINNED[:7]}; this challenge tests the unmodified code")

import vehicle_action as va  # noqa: E402
from sovereign_veritas.capability import Capability  # noqa: E402
from sovereign_veritas.evidence import EvidenceRecord, Ledger, LedgerSink, canonical_json  # noqa: E402
from sovereign_veritas.interfaces.contracts import ActionProposal  # noqa: E402
from sovereign_veritas.package import sha256_hex  # noqa: E402
from sovereign_veritas.runtime import RuntimeState  # noqa: E402
from sovereign_veritas.verifier_registry import VerifierRegistry  # noqa: E402
from sovereign_veritas.workflow import EvidenceWorkflow  # noqa: E402

L = 25.0
FENCE = {"lat_e7": 353632000, "lon_e7": -969270000, "radius_m": 300.0, "max_alt_m": 120.0}


class Recorder:
    name = "ab-recovery-stand-in-not-a-vehicle"

    def __init__(self):
        self.commands = []

    def run(self, action, params):
        self.commands.append(f"{action} {canonical_json(params)}")
        return True


def request(action, cross_check):
    params = {}
    if action == "goto":
        params["alt_m"] = 20.0
        params["lat_e7"], params["lon_e7"] = va.offset(FENCE["lat_e7"], FENCE["lon_e7"], 100.0, 0.0)
    elif action == "goto_centre":
        params = {"alt_m": 20.0, "lat_e7": FENCE["lat_e7"], "lon_e7": FENCE["lon_e7"]}
    req = {"schema": va.REQUEST_SCHEMA, "action": "goto" if action == "goto_centre" else action, "params": params,
           "fence": FENCE, "limits": {"min_fix_type": 3, "min_sats": 6, "min_battery_pct": 30}}
    if cross_check:
        req["limits"]["max_nav_disagreement_m"] = L
    return req


def decide(req, snap):
    """vehicle_action.py main(), minus telemetry reads and package writing; thermal declared normal."""
    artifact = canonical_json(req).encode("utf-8")
    vehicle = Recorder()
    predictor = va.RecordedSnapshot(snap, vehicle.name)
    verifier = va.Check(req, snap, predictor.digest)
    registry = VerifierRegistry(min_coverage=0.5)
    registry.register(va.VERIFIER_ID, verifier)
    probe_req = dict(req, action="goto", params={"alt_m": 20, "lat_e7": FENCE["lat_e7"], "lon_e7": FENCE["lon_e7"]})
    good = va.FakeVehicle.SCENARIOS["healthy_air"] | {"lat_e7": FENCE["lat_e7"], "lon_e7": FENCE["lon_e7"],
                                                      "xpos_lat_e7": FENCE["lat_e7"], "xpos_lon_e7": FENCE["lon_e7"]}
    for s, want in ((good, "PASS"), (dict(good, gps_fix_type=0), "FAIL")):
        registry.record_probe(va.VERIFIER_ID, passed=va.vehicle_check(probe_req, s)["verdict"] == want)
    ledger = Ledger()
    ledger.append(EvidenceRecord(record_id="session-start", input_digest=sha256_hex(b"session"), metadata={}))
    capability = Capability("vehicle_command", authorized=True, required_evidence=("verifier_probed",))
    runtime = RuntimeState(platform="ab-recovery", python_version=sys.version.split()[0], thermal_status="normal",
                           metadata={"thermal_status_source": "declared"})
    policy = {"allow_only": ["takeoff", "goto", "land", "rtl"]}
    action = va.ActionProposal("vehicle_command", req["action"], req["params"]) if hasattr(va, "ActionProposal") \
        else ActionProposal("vehicle_command", req["action"], req["params"])
    wf = EvidenceWorkflow(sensor=va.Question(artifact), predictor=predictor, verifier=verifier,
                          executor=va.Execute(vehicle), evidence_sink=LedgerSink(ledger), verifier_registry=registry)
    result = wf.run(record_id="ab-1", input_digest=sha256_hex(artifact), capability=capability, runtime=runtime,
                    action=action, policy=policy, metadata={"verifier_probed": True}, verifier_id=va.VERIFIER_ID)
    chk = va.vehicle_check(req, snap)
    return {"decision": result.decision.decision, "reasons": list(result.decision.reasons),
            "check": chk["verdict"], "why": chk["why"], "sent": vehicle.commands}


# ---- snapshots ----------------------------------------------------------------------------------------
BASE = dict(va.FakeVehicle.SCENARIOS["healthy_air"], lat_e7=FENCE["lat_e7"], lon_e7=FENCE["lon_e7"], rel_alt_mm=20000)
NORTH_111 = 10000          # 1e-3 degree of latitude, about 111 m: the spoofed vehicle's true offset


def b_at(snap, dlat_e7, source, **extra):
    s = dict(snap, xpos_lat_e7=snap["lat_e7"] + dlat_e7, xpos_lon_e7=snap["lon_e7"], xpos_source=source)
    s.update(extra)
    return s


S1 = b_at(BASE, 270, "fresh independent fix (stand-in)")                            # B 3 m from A
S2 = va.FakeVehicle("spoofed", FENCE, xpos=True).snapshot()                         # A at centre, truly 111 m N
S2G = dict(S1, ekf_flags=S1["ekf_flags"] | va.EKF_GPS_GLITCH)
S3 = dict(BASE)                                                                    # no B at all
S4 = b_at(BASE, 0, "STALE: last independent fix 600 s ago, before drift began", xpos_age_s=600)
S7 = b_at(BASE, 180, "derived from autopilot GNSS (same root as A)")              # B 2 m from A
S8 = copy.deepcopy(S1)     # the case-1 snapshot, recorded before the spoof, replayed as current

CASES = [  # id, A, B, prior approval, snapshot
    ("1", "trusted", "fresh, agrees", "valid", S1),
    ("2", "spoofed (truly 111 m N)", "fresh, true position", "valid", S2),
    ("2g", "EKF GPS-glitch flag", "fresh, agrees", "valid", S2G),
    ("3", "spoofed, no flag", "unavailable", "valid", S3),
    ("4", "spoofed, no flag", "stale (600 s, labelled)", "valid", S4),
    ("5", "spoofed, no flag", "unavailable", "invalidated (no input exists)", S3),
    ("6", "spoofed, no flag", "stale (600 s, labelled)", "invalidated (no input exists)", S4),
    ("7", "spoofed, no flag", "derived from A", "invalidated (no input exists)", S7),
    ("8", "spoofed, no flag", "cached case-1 snapshot", "invalidated (no input exists)", S8),
]
ACTIONS = ("goto", "goto_centre", "rtl", "land")


def run_matrix():
    out = {}
    for cid, a, b, prior, snap in CASES:
        for cc in (True, False):
            for act in ACTIONS:
                out[(cid, cc, act)] = decide(request(act, cc), snap)
    return out


def control_c0():
    """main() on fake:spoofed must reach the harness's decision for case 2, goto, cross-check on."""
    home = tempfile.mkdtemp(prefix="ab_c0_")
    p = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "vehicle_action.py"), "--link", "fake:spoofed",
                        "--action", "goto", "--north", "100", "--alt", "20", "--max-disagreement", str(L),
                        "--xpos-sigma", "0", "--thermal-status", "normal"],
                       capture_output=True, text=True, env=dict(os.environ, HOME=home))
    line = next((l for l in p.stdout.splitlines() if l.startswith("decision ")), None)
    if p.returncode != 0 or line is None:
        could_not_run(f"vehicle_action.py main() did not run: {p.stdout[-300:]} {p.stderr[-300:]}")
    return line.split()[1]


def main():
    m = run_matrix()
    d = lambda c, cc, a: m[(c, cc, a)]["decision"]
    preds = {}
    allow = lambda c, cc, acts=ACTIONS: all(d(c, cc, a) == "ALLOW" for a in acts)
    preds["C0 wiring = main()"] = control_c0() == d("2", True, "goto")
    preds["C1 anti-vacuity: case 2 goto REFUSE"] = d("2", True, "goto") == "REFUSE"
    preds["AB-P1"] = allow("1", True) and allow("1", False)
    preds["AB-P2"] = (all(d("2", True, a) == "REFUSE" for a in ("goto", "goto_centre", "rtl"))
                      and "disagree" in m[("2", True, "goto")]["why"] and d("2", True, "land") == "ALLOW"
                      and d("2", False, "goto") == "ALLOW" and d("2", False, "rtl") == "ALLOW")
    preds["AB-P3"] = all(d("2g", cc, a) == "REFUSE" for cc in (True, False) for a in ("goto", "rtl")) \
        and all(d("2g", cc, "land") == "ALLOW" for cc in (True, False))
    preds["AB-P4"] = (all(d("3", True, a) == "REFUSE" for a in ("goto", "rtl"))
                      and "no independent position" in m[("3", True, "goto")]["why"]
                      and d("3", True, "land") == "ALLOW" and allow("3", False))
    preds["AB-P5"] = all(d("4", True, a) == "ALLOW" for a in ("goto", "goto_centre", "rtl"))
    preds["AB-P6"] = all(m[("5", cc, a)] == m[("3", cc, a)] and m[("6", cc, a)] == m[("4", cc, a)]
                         for cc in (True, False) for a in ACTIONS)
    preds["AB-P7"] = all(d("7", True, a) == "ALLOW" for a in ("goto", "rtl"))
    preds["AB-P8"] = allow("8", True)
    preds["AB-P9"] = all(not (d(c, cc, a) == "ALLOW" and d("1", cc, a) != "ALLOW")
                         for c, *_ in CASES for cc in (True, False) for a in ("goto", "goto_centre", "rtl")) \
        and all(d(c, cc, "land") == "ALLOW" for c, *_ in CASES for cc in (True, False))
    preds["AB-P10"] = all(d(c, True, "goto") == "REFUSE" and d(c, False, "goto") == "ALLOW" for c in ("2", "3")) \
        and d("4", True, "goto") == d("4", False, "goto") == "ALLOW"

    print("Amos Tipton's A/B Recovery Challenge | unmodified code at", PINNED[:7], "| L =", L, "m")
    print(f"{'case':4} {'A':24} {'B':24} {'prior':12} {'xcheck':6} " + " ".join(f"{a:11}" for a in ACTIONS))
    for cid, a, b, prior, _ in CASES:
        for cc in (True, False):
            print(f"{cid:4} {a[:24]:24} {b[:24]:24} {prior[:12]:12} {'on' if cc else 'off':6} "
                  + " ".join(f"{d(cid, cc, x):11}" for x in ACTIONS))
    print()
    for cid, *_ in CASES:
        print(f"why case {cid} goto (on): {m[(cid, True, 'goto')]['check']} - {m[(cid, True, 'goto')]['why']}"
              f" -> {m[(cid, True, 'goto')]['decision']} {m[(cid, True, 'goto')]['reasons']}")
    print()
    for k, v in preds.items():
        print(f"{k:40} {'held' if v else 'DID NOT HOLD'}")
    held = sum(preds.values())
    rows = [{"case": c, "A": a, "B": b, "prior_approval": pr, "cross_check": cc, "action": act,
             "snapshot_sha256": sha256_hex(canonical_json(s).encode()), **m[(c, cc, act)]}
            for c, a, b, pr, s in CASES for cc in (True, False) for act in ACTIONS]
    digest = hashlib.sha256(canonical_json([[r["case"], r["cross_check"], r["action"], r["decision"], r["reasons"]]
                                            for r in rows]).encode()).hexdigest()
    print(f"VERDICT  {held} of {len(preds)} as registered")
    print(f"DIGEST   {digest}")
    out = os.path.join(ROOT, "results", "ab_recovery")
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "results.json"), "w") as fh:
        json.dump({"pinned_commit": PINNED, "limit_m": L, "rows": rows, "predictions": preds, "digest": digest},
                  fh, indent=1, sort_keys=True)
    return 0 if held == len(preds) else 1


if __name__ == "__main__":
    sys.exit(main())
