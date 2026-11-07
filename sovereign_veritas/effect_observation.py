"""Observed-effect check (EO-2, docs/EO2_PREREG.md). Opt-in; nothing in the workflow or package calls it.

EO-1 showed that the evidence record reports the workflow's account of calling the executor, not an effect.
This module compares a decision record with an observation of the target's state taken before and after the
run by an observer that does not go through the executor. It trusts the observer's wiring: an observer the
executor can write to defeats it (EO-2 P5). Binding is integrity, not authenticity: nothing here is signed.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

OK = "OK"
UNOBSERVABLE = "UNOBSERVABLE"
NO_OBSERVATION = "NO_OBSERVATION"
BINDING_MISMATCH = "BINDING_MISMATCH"
UNAUTHORIZED_EFFECT = "UNAUTHORIZED_EFFECT"
NO_EFFECT = "NO_EFFECT"
WRONG_EFFECT = "WRONG_EFFECT"
EFFECT_DESPITE_FAILURE = "EFFECT_DESPITE_FAILURE"


def action_digest(action: Mapping[str, Any] | None) -> str:
    """sha256 of the record's action in canonical JSON (sorted keys, no spaces)."""
    canon = json.dumps(action, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(canon.encode("utf-8")).hexdigest()


def make_observation(record_id: str, action: Mapping[str, Any] | None,
                     before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, Any]:
    return {"record_id": record_id, "action_digest": action_digest(action),
            "before": dict(before), "after": dict(after)}


def changed_keys(before: Mapping[str, Any], after: Mapping[str, Any]) -> set:
    missing = object()
    return {k for k in set(before) | set(after) if before.get(k, missing) != after.get(k, missing)}


def check_observed_effect(record: Mapping[str, Any], observation: Mapping[str, Any] | None,
                          expected: Mapping[str, Any] | None, *, bind: bool = True) -> str:
    """Verdict for one record. `record` is EvidenceRecord.to_dict(); `expected` is the state the recorded
    action should produce (key -> value), or None when the action is unknown to the effect spec."""
    if observation is None:
        return NO_OBSERVATION
    if bind and (observation.get("record_id") != record.get("record_id")
                 or observation.get("action_digest") != action_digest(record.get("action"))):
        return BINDING_MISMATCH
    before, after = observation.get("before") or {}, observation.get("after") or {}
    changed = changed_keys(before, after)
    if record.get("decision") != "ALLOW":
        return OK if not changed else UNAUTHORIZED_EFFECT
    status = (record.get("metadata") or {}).get("execution_status")
    if status != "SUCCEEDED":
        return OK if not changed else EFFECT_DESPITE_FAILURE
    if not expected:
        return WRONG_EFFECT if changed else NO_EFFECT
    if all(before.get(k) == v for k, v in expected.items()) and all(k in before for k in expected):
        # As registered: expected state already present -> UNOBSERVABLE, even if other keys changed.
        # (Reporting WRONG_EFFECT when other keys changed would be stricter; it is a door, not this rule.)
        return UNOBSERVABLE
    if not changed:
        return NO_EFFECT
    if all(after.get(k) == v and k in after for k, v in expected.items()) and changed <= set(expected):
        return OK
    return WRONG_EFFECT
