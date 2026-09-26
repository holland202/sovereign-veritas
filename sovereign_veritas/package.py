"""End-to-end evidence package (schema sv.package/0).

One JSON document carrying everything a challenger needs to reconstruct a gated run without
the producing process: artifact bytes, measurement, the provenance chain up to the decision
record, verifier validation, every Gate input, resource state, freshness status, and the
decision. tools/verify_package.py checks it without importing this package.

What a valid package proves: the parts are mutually consistent and the recorded decision is the
one the documented Gate produces from the recorded inputs. What it does not prove: that this is
the package that was produced (no signature), that it is the newest (freshness), or that the
recorded verifier object is the one that ran. Those limits are written into every package.
"""
from __future__ import annotations

import base64
import hashlib
import os
from typing import Any, Iterable

from .capability import Capability, CapabilityRegistry
from .evidence import EvidenceRecord, canonical_json
from .evidence_states import FIELDS as EVIDENCE_FIELDS, problems as evidence_state_problems, resource_statement
from .runtime import RuntimeState
from .thermal import ZoneReading, summarize
from .thermal_policy import POLICIES, derive_thermal_status, policy_dict
from .verifier_registry import VerifierValidation

SCHEMA = "sv.package/0"
KNOWN_LIMITATIONS = (
    "freshness: NOT_PROVEN - no external witness; an older valid package is indistinguishable",
    "authenticity: none - no signature; a fully consistent rewrite verifies",
    "verifier identity: the verifier_id is declared by the caller, not bound to the verifier object",
    "resource state: runtime fields are declared by the caller, not derived from thermal zones",
)
# A package whose runtime says thermal_status_source == "measured" states this instead of the fourth
# line. The verifier recomputes the status; it does not take this sentence on trust.
MEASURED_RESOURCE_STATEMENT = (
    "resource state: thermal_status derived from measurement.thermal_before under the uncalibrated "
    "per-domain limits named in resource_state.thermal_policy; compute_budget and power_status "
    "declared by the caller")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def package_digest(package: dict[str, Any]) -> str:
    body = {k: v for k, v in package.items() if k != "package_sha256"}
    return sha256_hex(canonical_json(body).encode("utf-8"))


def _validation_dict(validation: VerifierValidation | None) -> dict[str, Any] | None:
    if validation is None:
        return None
    return {
        "verifier_id": validation.verifier_id,
        "status": validation.status.value,
        "total_probes": validation.total_probes,
        "meaningful_probes": validation.meaningful_probes,
        "meaningful_passes": validation.meaningful_passes,
        "failed_probes": validation.failed_probes,
        "min_coverage": validation.min_coverage,
    }


def build_package(
    *,
    artifact: bytes,
    artifact_name: str,
    measurement: dict[str, Any],
    chain: Iterable[EvidenceRecord],
    capability: Capability | None,
    runtime: RuntimeState,
    policy: dict[str, Any] | None = None,
    capability_registry: CapabilityRegistry | None = None,
    registry_names: Iterable[str] = (),
    verifier_id: str | None = None,
    validation: VerifierValidation | None = None,
    thermal: tuple[ZoneReading, ...] | None = None,
    evidence_states: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Package one gated run. The last record of `chain` must be the decision record.

    evidence_states (optional): one evidence-ledger state per runtime field (evidence_states.py).
    When given, the package carries them and its fourth known limitation is generated from them."""
    records = list(chain)
    if not records:
        raise ValueError("chain is empty")
    decision_record = records[-1]
    if decision_record.decision is None:
        raise ValueError("last chain record carries no decision")
    art_sha = sha256_hex(artifact)
    if decision_record.input_digest != art_sha:
        raise ValueError("decision record input_digest is not the artifact's sha256")
    if measurement.get("artifact_sha256") != art_sha:
        raise ValueError("measurement does not name this artifact")
    limitations = list(KNOWN_LIMITATIONS)
    thermal_policy = None
    if runtime.metadata.get("thermal_status_source") == "measured":
        policy_id = runtime.metadata.get("thermal_policy")
        before = measurement.get("thermal_before")
        if policy_id not in POLICIES or not isinstance(before, list):
            raise ValueError("measured thermal_status needs a known thermal_policy and thermal_before")
        thermal_policy = policy_dict(policy_id)
        derived, _ = derive_thermal_status(before, thermal_policy["limits_mdeg"])
        if derived != runtime.thermal_status:
            raise ValueError(f"thermal_status {runtime.thermal_status!r} is not the derived {derived!r}")
        limitations[3] = MEASURED_RESOURCE_STATEMENT
    if evidence_states is not None:
        broken = evidence_state_problems(evidence_states, runtime.to_dict())
        if broken:
            raise ValueError("evidence states: " + "; ".join(broken))
        evidence_states = {f: evidence_states[f] for f in EVIDENCE_FIELDS}
        limitations[3] = resource_statement(evidence_states)
    snapshot = None
    if capability_registry is not None:
        snapshot = {}
        for name in registry_names:
            cap = capability_registry.get(name)
            snapshot[name] = None if cap is None else cap.to_dict()
    package: dict[str, Any] = {
        "schema": SCHEMA,
        "artifact": {"name": artifact_name, "sha256": art_sha,
                     "bytes_b64": base64.b64encode(artifact).decode("ascii")},
        "measurement": dict(measurement),
        "provenance": {"chain": [{"record": r.to_dict(), "record_digest": r.record_digest}
                                 for r in records]},
        "verifier": {"verifier_id": verifier_id, "validation": _validation_dict(validation),
                     "identity_bound": False},
        "gate_inputs": {"capability": None if capability is None else capability.to_dict(),
                        "capability_registry": snapshot, "policy": policy},
        "resource_state": {
            "runtime": runtime.to_dict(),
            "thermal": None if thermal is None else {
                "zones": [z.to_dict() for z in thermal], "summary": summarize(thermal)},
            **({} if thermal_policy is None else {"thermal_policy": thermal_policy}),
            **({} if evidence_states is None else {"evidence_states": evidence_states}),
        },
        "freshness": {"status": "NOT_PROVEN", "witness": None},
        "decision": {"decision": decision_record.decision,
                     "reasons": list(decision_record.reasons)},
        "known_limitations": limitations,
    }
    canonical_json(package)  # fail here, not in the verifier, if anything is not JSON
    package["package_sha256"] = package_digest(package)
    return package


def write_package(package: dict[str, Any], directory: str, *, _after_first_half=None) -> str:
    """Write atomically: temp file, fsync, rename. A crash leaves nothing at the final path.

    The name carries the content's md5, so a file under that name is either complete or absent.
    `_after_first_half` is a test seam: called after half the bytes are written, so a test can
    kill the process mid-write.
    """
    data = canonical_json(package).encode("utf-8")
    final = os.path.join(directory, f"sv_package_{hashlib.md5(data).hexdigest()[:12]}.json")
    tmp = f"{final}.tmp-{os.getpid()}"
    half = len(data) // 2
    with open(tmp, "wb") as fh:
        fh.write(data[:half])
        fh.flush()
        if _after_first_half is not None:
            _after_first_half()
        fh.write(data[half:])
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, final)
    try:  # make the rename itself durable where the platform allows it
        dfd = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    except OSError:
        pass
    return final
