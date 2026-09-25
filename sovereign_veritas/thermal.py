"""Thermal zone evidence: one reading per zone with its type and domain, never a cross-domain aggregate.

The domain map comes from the zone type names observed on the S25 (SM-S938U, 68 zones) on
2026-09-25; see docs/THERMAL_ZONES.md. An unmatched type is 'unknown' and is reported, not merged.
A zone's number is not stable identity across devices or kernels; its type is what is classified.

Readings are sensor values as the kernel reports them, not calibrated temperatures. Nothing here
decides a RuntimeState: per-domain limits are uncalibrated and belong to governance, not measurement.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

OFFLINE_SENTINEL = -273000  # absolute zero: the sensor's block is powered down
PLAUSIBLE_RAW = (-40000, 150000)  # millidegrees; outside this a reading is not trusted

DOMAIN_PREFIXES: tuple[tuple[str, str], ...] = (  # first match wins
    ("cpuss-", "cpu_subsystem"),
    ("cpu-", "cpu_core"),
    ("gpuss-", "gpu"),
    ("nsph", "npu"),
    ("ddr", "ddr"),
    ("mdmss-", "modem"),
    ("camera", "camera"),
    ("video", "video"),
    ("aoss-", "always_on"),
    ("pm8550-bcl", "bcl"),
    ("pm", "pmic"),
    ("battery", "battery"),
    ("sys-therm", "board"),
    ("sdr", "rf"),
    ("mmw", "rf"),
)
NOT_TEMPERATURE = frozenset({"bcl"})  # battery current-limit mitigation levels


def classify(zone_type: str) -> str:
    return next((d for prefix, d in DOMAIN_PREFIXES if zone_type.startswith(prefix)), "unknown")


@dataclass(frozen=True)
class ZoneReading:
    zone: str
    type: str
    domain: str
    raw: int | None
    status: str  # ok | offline | not_temperature | out_of_range | unreadable

    @property
    def celsius(self) -> float | None:
        return self.raw / 1000.0 if self.status == "ok" else None

    def to_dict(self) -> dict[str, Any]:
        return {"zone": self.zone, "type": self.type, "domain": self.domain,
                "raw": self.raw, "status": self.status}


def _read(path: str) -> str | None:
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError:
        return None


def read_zones(root: str = "/sys/class/thermal") -> tuple[ZoneReading, ...]:
    """One pass over every zone. Missing root gives an empty tuple, never an exception."""
    if not os.path.isdir(root):
        return ()
    out = []
    for name in sorted(n for n in os.listdir(root) if n.startswith("thermal_zone")):
        zone_type = _read(os.path.join(root, name, "type")) or "?"
        domain = classify(zone_type)
        text = _read(os.path.join(root, name, "temp"))
        try:
            raw = int(text) if text is not None else None
        except ValueError:
            raw = None
        if raw is None:
            status = "unreadable"
        elif raw == OFFLINE_SENTINEL:
            status = "offline"
        elif domain in NOT_TEMPERATURE:
            status = "not_temperature"
        elif not PLAUSIBLE_RAW[0] <= raw <= PLAUSIBLE_RAW[1]:
            status = "out_of_range"
        else:
            status = "ok"
        out.append(ZoneReading(name, zone_type, domain, raw, status))
    return tuple(out)


def summarize(readings: tuple[ZoneReading, ...]) -> dict[str, Any]:
    """Per-domain max and counts. Deliberately no mean and no device-wide max."""
    status_counts: dict[str, int] = {}
    domains: dict[str, dict[str, Any]] = {}
    for r in readings:
        status_counts[r.status] = status_counts.get(r.status, 0) + 1
        d = domains.setdefault(r.domain, {"max_c": None, "ok": 0, "zones": 0})
        d["zones"] += 1
        if r.status == "ok":
            d["ok"] += 1
            if d["max_c"] is None or r.celsius > d["max_c"]:
                d["max_c"] = r.celsius
    return {"zones": len(readings), "status_counts": dict(sorted(status_counts.items())),
            "domains": dict(sorted(domains.items()))}
