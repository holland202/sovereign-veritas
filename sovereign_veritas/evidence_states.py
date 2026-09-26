"""Evidence states for the runtime fields the Gate reads: where each value came from.

Vocabulary from evidence-ledger SPEC.md section 2 (github.com/holland202/evidence-ledger @ ccf9144).
Its rule, kept here: no implicit promotion - a default, an operator's word or an inference is never
reported as a measurement. Registered in docs/INTEGRATION.md (I2); tools/verify_package.py
re-implements these rules without importing this module.

sv.package/0 uses four of the eight states on runtime fields:
  DERIVED    thermal_status computed from measured zones (thermal_status_source "measured")
  OPERATOR   a person or calling program supplied the value explicitly
  DEFAULTED  nobody supplied it; RuntimeState's default was used
  ABSENT     nobody supplied it and no default was substituted; the Gate treats it as unavailable
MEASURED, INFERRED, NEVER_WIRED and UNVERIFIED are refused on runtime fields: no runtime field is
read directly from a sensor in this format, so claiming MEASURED would be promotion.

The Gate does not read these tags. It counts a DEFAULTED value exactly like a declared one
(finding F1 in docs/INTEGRATION.md). The tags make that visible; they do not change it.
"""
from __future__ import annotations

from typing import Any, Mapping

STATES = ("MEASURED", "OPERATOR", "DERIVED", "INFERRED", "ABSENT", "DEFAULTED", "NEVER_WIRED",
          "UNVERIFIED")
FIELDS = ("thermal_status", "compute_budget", "power_status")
DEFAULTS = {"thermal_status": "normal", "compute_budget": "available", "power_status": "stable"}
ALLOWED = {"thermal_status": ("DERIVED", "OPERATOR", "DEFAULTED", "ABSENT"),
           "compute_budget": ("OPERATOR", "DEFAULTED", "ABSENT"),
           "power_status": ("OPERATOR", "DEFAULTED", "ABSENT")}
KNOWN_VALUES = {  # the Gate's runtime vocabulary (runtime.py): anything else is unavailable
    "thermal_status": ("normal", "cool", "warning", "high", "hot", "critical", "unsafe"),
    "compute_budget": ("available", "constrained", "low", "exhausted"),
    "power_status": ("stable", "unsafe"),
}


def problems(states: Any, runtime: Mapping[str, Any]) -> list[str]:
    """Every rule the tags break. runtime is RuntimeState.to_dict(). Empty list: the tags hold."""
    if not isinstance(states, dict) or sorted(states) != sorted(FIELDS):
        return [f"expected exactly the fields {', '.join(FIELDS)}"]
    found = []
    measured = (runtime.get("metadata") or {}).get("thermal_status_source") == "measured"
    for field in FIELDS:
        state, value = states[field], runtime.get(field)
        if state not in ALLOWED[field]:  # also every string evidence-ledger does not define
            found.append(f"{field}: {state!r} is not a state this field can carry (no implicit promotion)")
        elif state == "ABSENT" and value in KNOWN_VALUES[field]:
            found.append(f"{field}: ABSENT but carries the usable value {value!r}")
        elif state == "DEFAULTED" and value != DEFAULTS[field]:
            found.append(f"{field}: DEFAULTED but {value!r} is not the default {DEFAULTS[field]!r}")
    if states["thermal_status"] == "DERIVED" and not measured:
        found.append("thermal_status: DERIVED but thermal_status_source is not 'measured'")
    if measured and states["thermal_status"] != "DERIVED":
        found.append(f"thermal_status: source 'measured' but tagged {states['thermal_status']}")
    return found


def resource_statement(states: Mapping[str, str]) -> str:
    """The fourth known limitation of a tagged package, generated from its tags."""
    parts = []
    for field in FIELDS:
        if field == "thermal_status" and states[field] == "DERIVED":
            parts.append("thermal_status DERIVED from measurement.thermal_before under "
                         "resource_state.thermal_policy")
        else:
            parts.append(f"{field} {states[field]}")
    return ("resource state: " + "; ".join(parts) + " (evidence states as in evidence-ledger SPEC "
            "section 2; the verifier recomputes only DERIVED, and the Gate counts a DEFAULTED value "
            "as if it had been declared)")
