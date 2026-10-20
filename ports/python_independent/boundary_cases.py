#!/usr/bin/env python3
"""Hand-derived sv.gate/0 boundary cases; no reference-kernel calls."""

import copy
import json
import subprocess
import sys


BASE = {
    "record": {"input_digest": "digest", "verification": {"status": "PASS"},
               "action": {"capability": "read", "requested": "inspect"},
               "metadata": {}, "evidence_quality": None},
    "capability": {"name": "read", "authorized": True, "required_evidence": [],
                   "parent": None, "min_evidence_quality": None, "max_steps": None},
    "capability_registry": None,
    "runtime": {"thermal_status": "normal", "compute_budget": "available", "power_status": "stable"},
    "policy": {"allow_only": ["inspect"]},
}


def case(name, edit, decision, reasons):
    item = copy.deepcopy(BASE)
    edit(item)
    return name, item, decision, reasons


CASES = [
    case("baseline", lambda x: None, "ALLOW", []),
    case("missing_authorization", lambda x: x.update(capability=None), "REFUSE", ["capability_missing"]),
    case("unauthorized", lambda x: x["capability"].update(authorized=False), "REFUSE", ["capability_not_authorized"]),
    case("numeric_authorization", lambda x: x["capability"].update(authorized=1), "REFUSE", ["capability_not_authorized"]),
    case("expired_field_ignored", lambda x: x["capability"].update(expires_at="2000-01-01T00:00:00Z"), "ALLOW", []),
    case("revoked_field_ignored", lambda x: x["capability"].update(revoked=True), "ALLOW", []),
    case("revoked_authorized_false", lambda x: x["capability"].update(revoked=True, authorized=False), "REFUSE", ["capability_not_authorized"]),
    case("missing_parent", lambda x: x["capability"].update(parent="root"), "REFUSE", ["capability_parent_requires_registry"]),
    case("parent_not_authorized", lambda x: (x["capability"].update(parent="root"), x.update(capability_registry={"root": {"authorized": False}})), "REFUSE", ["capability_parent_not_authorized:root"]),
    case("quality_exact_floor", lambda x: (x["capability"].update(min_evidence_quality=0.5), x["record"].update(evidence_quality=0.5)), "ALLOW", []),
    case("quality_below_floor", lambda x: (x["capability"].update(min_evidence_quality=0.5), x["record"].update(evidence_quality=0.49999)), "DEFER", ["evidence_quality_below_threshold:0.5000<0.5000"]),
    case("quality_string_overrides_metadata", lambda x: (x["capability"].update(min_evidence_quality=0.5), x["record"].update(evidence_quality="0.9"), x["record"]["metadata"].update(evidence_quality=0.9)), "DEFER", ["evidence_quality_below_threshold:0.0000<0.5000"]),
    case("steps_at_max", lambda x: (x["capability"].update(max_steps=3), x["record"]["metadata"].update(step_count=3)), "ALLOW", []),
    case("steps_over_max_discards_defer", lambda x: (x["capability"].update(max_steps=3, required_evidence=["proof"]), x["record"]["metadata"].update(step_count=4)), "REFUSE", ["capability_max_steps_exceeded:4>3"]),
    case("boolean_step_invalid", lambda x: (x["capability"].update(max_steps=3), x["record"]["metadata"].update(step_count=True)), "DEFER", ["invalid_step_count_metadata"]),
    case("missing_runtime", lambda x: x["runtime"].pop("power_status"), "REFUSE", ["runtime_state_unavailable"]),
    case("degraded_and_missing_evidence", lambda x: (x["runtime"].update(power_status="unsafe"), x["capability"].update(required_evidence=["proof"])), "DEFER", ["runtime_not_healthy", "missing_required_evidence:proof"]),
    case("invalid_allow_only", lambda x: x["policy"].update(allow_only="inspect"), "REFUSE", ["policy_invalid:allow_only_must_be_a_collection"]),
    case("requested_not_permitted", lambda x: x["record"]["action"].update(requested="write"), "REFUSE", ["action_not_permitted_by_policy"]),
    case("false_requested_not_checked", lambda x: x["record"]["action"].update(requested=""), "ALLOW", []),
    case("verification_refuted", lambda x: x["record"]["verification"].update(status="REFUTED"), "REFUSE", ["verification_refuted"]),
    case("unrecognized_status", lambda x: x["record"]["verification"].update(status="PASS "), "REFUSE", ["verification_not_passed"]),
]


def run():
    program = sys.argv[1:]
    if not program:
        raise SystemExit("usage: boundary_cases.py PROGRAM [ARGS...]")
    payload = "".join(json.dumps({"id": name, "input": item}, separators=(",", ":")) + "\n" for name, item, _, _ in CASES)
    result = subprocess.run(program, input=payload, text=True, capture_output=True)
    print(f"boundary command: {program!r}")
    print(f"boundary process exit: {result.returncode}")
    print(f"boundary stderr: {result.stderr!r}")
    lines = result.stdout.splitlines()
    print(f"boundary count: {len(lines)}")
    failed = 0
    for index, (name, _, expected_decision, expected_reasons) in enumerate(CASES):
        actual = json.loads(lines[index]) if index < len(lines) else None
        wanted = {"id": name, "decision": expected_decision, "reasons": expected_reasons}
        ok = actual == wanted
        failed += not ok
        print(f"{'PASS' if ok else 'FAIL'} {name}: expected={wanted!r} observed={actual!r}")
    malformed = subprocess.run(program, input='{"id":"malformed","input":{"record":[],"runtime":{}}}\n', text=True, capture_output=True)
    print(f"unsupported_container_exit: {malformed.returncode}")
    print(f"unsupported_container_stderr: {malformed.stderr.strip()}")
    invalid_json = subprocess.run(program, input='not-json\n', text=True, capture_output=True)
    print(f"invalid_json_exit: {invalid_json.returncode}")
    print(f"invalid_json_stderr: {invalid_json.stderr.strip()}")
    nonstandard_json = subprocess.run(program, input='{"id":"nan","input":{"record":{"evidence_quality":NaN},"runtime":{}}}\n', text=True, capture_output=True)
    print(f"nonstandard_json_exit: {nonstandard_json.returncode}")
    print(f"nonstandard_json_stderr: {nonstandard_json.stderr.strip()}")
    if result.returncode or failed or malformed.returncode != 2 or invalid_json.returncode != 2 or nonstandard_json.returncode != 2:
        return 1
    print(f"VERDICT: {len(CASES)} hand-derived decision cases PASS; 3 malformed inputs rejected with exit 2")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
