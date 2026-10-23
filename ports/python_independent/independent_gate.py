#!/usr/bin/env python3
"""Standalone implementation of the documented sv.gate/0 decision contract.

Authoring source: CONTRACT.md at d3a9a881c92413cb63a279434405e0412ef443f6.
No Sovereign Veritas package or reference decision function is imported.
"""

import json
import math
import sys


VERIFICATION_VALUES = {
    "PASS", "FAIL", "REFUTED", "INSUFFICIENT_EVIDENCE", "NOT_VERIFIED", "UNKNOWN"
}
RUNTIME_VALUES = {
    "thermal_status": {"normal", "cool", "warning", "high", "hot", "critical", "unsafe"},
    "compute_budget": {"available", "constrained", "low", "exhausted"},
    "power_status": {"stable", "unsafe"},
}
DEGRADED = {
    "thermal_status": {"warning", "high", "hot", "critical", "unsafe"},
    "compute_budget": {"exhausted"},
    "power_status": {"unsafe"},
}


def truthy(value):
    return bool(value)


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def double(value):
    if not number(value):
        return 0.0
    try:
        return float(value)
    except OverflowError:
        return math.inf if value > 0 else -math.inf


def refuse(reason):
    return "REFUSE", [reason]


def decide(case):
    # CONTRACT.md declares these container types. Unsupported types are rejected
    # by the line-protocol runner rather than silently coerced into a decision.
    record = case["record"]
    capability = case.get("capability")
    registry = case.get("capability_registry")
    runtime = case["runtime"]
    policy = case.get("policy")
    if not isinstance(record, dict) or not isinstance(runtime, dict):
        raise ValueError("record and runtime must be objects")
    if capability is not None and not isinstance(capability, dict):
        raise ValueError("capability must be an object or null")
    if registry is not None and not isinstance(registry, dict):
        raise ValueError("capability_registry must be an object or null")
    if policy is not None and not isinstance(policy, dict):
        raise ValueError("policy must be an object or null")
    action = record.get("action")
    metadata = record.get("metadata")
    verification = record.get("verification")
    if action is not None and not isinstance(action, dict):
        raise ValueError("action must be an object or null")
    if not isinstance(metadata, dict):
        raise ValueError("metadata must be an object")
    if verification is not None and not isinstance(verification, dict):
        raise ValueError("verification must be an object or null")
    action = action or {}
    policy = policy or {}

    if not truthy(record.get("input_digest")):
        return refuse("evidence_invalid:missing_input_digest")

    raw_status = None if verification is None else verification.get("status")
    if raw_status is None:
        status = "NOT_VERIFIED"
    elif isinstance(raw_status, str) and raw_status in VERIFICATION_VALUES:
        status = raw_status
    else:
        status = "UNKNOWN"
    if status in {"FAIL", "NOT_VERIFIED", "UNKNOWN"}:
        return refuse("verification_not_passed")
    if status == "REFUTED":
        return refuse("verification_refuted")
    reasons = []
    if status == "INSUFFICIENT_EVIDENCE":
        reasons.append("verification_insufficient_evidence")
    elif status != "PASS":
        return refuse("verification_not_passed")

    if capability is None:
        return refuse("capability_missing")
    if capability.get("authorized") is not True:
        return refuse("capability_not_authorized")
    parent = capability.get("parent")
    if truthy(parent):
        if registry is None:
            return refuse("capability_parent_requires_registry")
        if not isinstance(parent, str):
            raise ValueError("capability.parent must be a string")
        parent_capability = registry.get(parent)
        if parent_capability is None:
            return refuse(f"capability_parent_missing:{parent}")
        if not isinstance(parent_capability, dict):
            raise ValueError("capability_registry entries must be objects or null")
        if parent_capability.get("authorized") is not True:
            return refuse(f"capability_parent_not_authorized:{parent}")

    action_capability = action.get("capability")
    if truthy(action_capability) and action_capability != capability.get("name"):
        return refuse("action_capability_mismatch")

    for field, vocabulary in RUNTIME_VALUES.items():
        value = runtime.get(field)
        if not isinstance(value, str) or value not in vocabulary:
            return refuse("runtime_state_unavailable")
    if any(runtime[field] in degraded for field, degraded in DEGRADED.items()):
        reasons.append("runtime_not_healthy")

    required = capability.get("required_evidence", [])
    if not isinstance(required, list) or any(not isinstance(n, str) for n in required):
        raise ValueError("required_evidence must be an array of strings")
    for name in required:
        if metadata.get(name) is not True:
            reasons.append(f"missing_required_evidence:{name}")

    floor = capability.get("min_evidence_quality")
    if floor is not None:
        if not number(floor):
            raise ValueError("min_evidence_quality must be a number or null")
        top_quality = record.get("evidence_quality")
        q = double(top_quality if top_quality is not None else metadata.get("evidence_quality"))
        if not math.isfinite(q) or not 0.0 <= q <= 1.0:
            reasons.append(f"evidence_quality_invalid:{repr(q)}")
        elif q < floor:
            reasons.append(f"evidence_quality_below_threshold:{q:.4f}<{double(floor):.4f}")

    maximum = capability.get("max_steps")
    steps = metadata.get("step_count")
    if maximum is not None and steps is not None:
        if not isinstance(maximum, int) or isinstance(maximum, bool):
            raise ValueError("max_steps must be an integer or null")
        if not isinstance(steps, int) or isinstance(steps, bool) or steps < 1:
            reasons.append("invalid_step_count_metadata")
        elif steps > maximum:
            return refuse(f"capability_max_steps_exceeded:{steps}>{maximum}")

    allowed = policy.get("allow_only")
    if allowed is not None and not isinstance(allowed, list):
        return refuse("policy_invalid:allow_only_must_be_a_collection")
    requested = action.get("requested")
    if truthy(requested) and allowed is not None and requested not in allowed:
        return refuse("action_not_permitted_by_policy")

    return ("DEFER", reasons) if reasons else ("ALLOW", [])


def main():
    for line_number, line in enumerate(sys.stdin, 1):
        try:
            envelope = json.loads(line, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f"non-standard JSON constant {value}")))
            if not isinstance(envelope, dict) or "id" not in envelope or not isinstance(envelope.get("input"), dict):
                raise ValueError("expected object with id and input object")
            decision, reasons = decide(envelope["input"])
            print(json.dumps({"id": envelope["id"], "decision": decision, "reasons": reasons}, ensure_ascii=False))
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            print(f"input line {line_number}: unsupported or malformed input: {exc}", file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
