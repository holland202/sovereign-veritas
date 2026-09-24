from __future__ import annotations

from sovereign_veritas.capability import Capability, CapabilityRegistry
from sovereign_veritas.evidence import Ledger, LedgerSink
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
