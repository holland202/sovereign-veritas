from __future__ import annotations

import pytest

from sovereign_veritas.capability import Capability, CapabilityRegistry
from sovereign_veritas.evidence import EvidenceRecord, Ledger, LedgerSink
from sovereign_veritas.governance import CapabilityGovernor
from sovereign_veritas.uncertainty import normalize_uncertainty


def test_authorize_is_ledgered_before_registry_change():
    registry = CapabilityRegistry()
    registry.register(Capability("write", False))
    ledger = Ledger()
    sink = LedgerSink(ledger)
    gov = CapabilityGovernor(registry, sink)

    updated, evidence = gov.authorize(
        "write",
        record_id="gov-auth-1",
        input_digest="digest-1",
        reason="operator_grant",
        actor="human",
    )

    assert updated is not None and updated.authorized is True
    assert registry.get("write").authorized is True
    assert len(ledger.all()) == 1
    assert ledger.all()[0].metadata["governance_action"] == "authorize"
    assert ledger.all()[0].decision == "ALLOW"
    assert ledger.verify()


def test_revoke_is_ledgered():
    registry = CapabilityRegistry()
    registry.register(Capability("write", True))
    ledger = Ledger()
    sink = LedgerSink(ledger)
    gov = CapabilityGovernor(registry, sink)

    updated, evidence = gov.revoke(
        "write",
        record_id="gov-rev-1",
        input_digest="digest-2",
        reason="session_end",
    )

    assert updated is not None and updated.authorized is False
    assert registry.get("write").authorized is False
    assert ledger.all()[0].metadata["governance_action"] == "revoke"
    assert ledger.all()[0].decision == "REFUSE"
    assert ledger.verify()


class _FailingSink:
    """EvidenceSink that always fails — used to prove fail-closed authorization."""

    def record(self, record: EvidenceRecord) -> EvidenceRecord:
        raise RuntimeError("custody_failed: simulated ledger write failure")


def test_failed_custody_does_not_change_registry():
    """If the ledger write fails, authorization must not take effect."""
    registry = CapabilityRegistry()
    registry.register(Capability("write", False))
    assert registry.get("write").authorized is False

    gov = CapabilityGovernor(registry, _FailingSink())

    with pytest.raises(RuntimeError, match="custody_failed"):
        gov.authorize(
            "write",
            record_id="gov-fail-1",
            input_digest="digest-fail",
            reason="should_not_apply",
        )

    # Registry must remain unchanged.
    assert registry.get("write").authorized is False


def test_failed_custody_on_revoke_does_not_change_registry():
    registry = CapabilityRegistry()
    registry.register(Capability("write", True))
    assert registry.get("write").authorized is True

    gov = CapabilityGovernor(registry, _FailingSink())

    with pytest.raises(RuntimeError, match="custody_failed"):
        gov.revoke(
            "write",
            record_id="gov-fail-2",
            input_digest="digest-fail-2",
            reason="should_not_apply",
        )

    assert registry.get("write").authorized is True


def test_normalize_uncertainty_produces_quality():
    unc, quality = normalize_uncertainty(
        prediction_value=42,
        interval=(1.0, 5.0),
        method="conformal",
        coverage_target=0.9,
        nonconformity=0.12,
    )
    assert unc["method"] == "conformal"
    assert unc["interval"] == [1.0, 5.0]
    assert 0.9 <= quality <= 1.0


def test_normalize_uncertainty_minimal():
    unc, quality = normalize_uncertainty(method="none")
    assert unc["method"] == "none"
    assert quality == 0.5
