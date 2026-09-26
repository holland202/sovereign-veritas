"""Derive RuntimeState.thermal_status from recorded thermal zones under a named, declared policy.

Measurement stays in thermal.py; the limits live here because they are a governance choice, not a
reading. Policy s25-uncalibrated-v0 was chosen from one probe run on one S25 (docs/THERMAL_ZONES.md):
it is not calibrated and not a safety claim. Registered in docs/EVIDENCE_PACKAGE.md (T0-T7).

Derivation, per limited domain, in order:
  any zone unreadable or out_of_range -> "unknown"; no ok zone -> "unknown".
Then any domain whose hottest ok zone is at or above its limit -> "hot"; otherwise "normal".
Offline zones are skipped; domains without a limit are recorded but never decide.
The Gate is unchanged: normal is healthy, hot is degraded (DEFER), unknown is unavailable (REFUSE).
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping

POLICY_ID = "s25-uncalibrated-v0"
LIMITS_MDEG: dict[str, int] = {  # millidegrees, as the kernel reports them
    "cpu_core": 95000,
    "cpu_subsystem": 95000,
    "gpu": 95000,
    "npu": 95000,
    "battery": 45000,
    "board": 50000,
}
POLICIES: dict[str, dict[str, int]] = {POLICY_ID: LIMITS_MDEG}


def policy_dict(policy_id: str = POLICY_ID) -> dict[str, Any]:
    return {"id": policy_id, "limits_mdeg": dict(sorted(POLICIES[policy_id].items())),
            "snapshot": "measurement.thermal_before"}


def derive_thermal_status(zones: Iterable[Mapping[str, Any]],
                          limits: Mapping[str, int]) -> tuple[str, str]:
    """zones: dicts with domain, raw, status (ZoneReading.to_dict()). Returns (status, detail)."""
    zones = list(zones)
    hot = []
    for domain in sorted(limits):
        members = [z for z in zones if z["domain"] == domain]
        bad = [z for z in members if z["status"] in ("unreadable", "out_of_range")]
        if bad:
            return "unknown", f"{domain}: {bad[0]['status']} zone {bad[0].get('zone', '?')}"
        ok = [z["raw"] for z in members if z["status"] == "ok"]
        if not ok:
            return "unknown", f"{domain}: no readable zone"
        if max(ok) >= limits[domain]:
            hot.append(f"{domain} {max(ok)}>={limits[domain]}")
    return ("hot", "; ".join(hot)) if hot else ("normal", "all limited domains below limit")
