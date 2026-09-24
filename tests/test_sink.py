from __future__ import annotations

import pytest

from sovereign_veritas.capability import Capability
from sovereign_veritas.decision import Gate
from sovereign_veritas.evidence import EvidenceRecord, Ledger, LedgerSink
from sovereign_veritas.runtime import RuntimeState


def record(record_id: str, decision: str | None = None) -> EvidenceRecord:
    return EvidenceRecord(
        record_id=record_id,
        input_digest="abc",
        verification={"status": "PASS"},
        decision=decision,
    )


def test_sink_appends_to_chain():
    ledger = Ledger()
    sink = LedgerSink(ledger)

    sink.record(record("r1"))
    sink.record(record("r2"))

    assert len(ledger.all()) == 2
    assert ledger.all()[1].previous_digest == ledger.all()[0].record_digest
    assert ledger.verify()


def test_refusals_become_permanent_evidence():
    ledger = Ledger()
    sink = LedgerSink(ledger)

    refused = record("r3", decision="REFUSE")
    sink.record(refused)

    assert ledger.verify()
    assert ledger.all()[0].decision == "REFUSE"


def test_sink_is_fail_closed_on_duplicate_ids():
    sink = LedgerSink(Ledger())
    sink.record(record("r4"))

    with pytest.raises(ValueError, match="duplicate"):
        sink.record(record("r4"))


def test_sink_survives_tamper_detection():
    ledger = Ledger()
    sink = LedgerSink(ledger)
    sink.record(record("r5"))

    ledger._records[0] = EvidenceRecord(
        record_id="r5",
        input_digest="tampered",
        verification={"status": "PASS"},
    )

    with pytest.raises(ValueError, match="tampered"):
        sink.record(record("r6"))


def test_gate_decision_flows_into_custody():
    ledger = Ledger()
    sink = LedgerSink(ledger)

    candidate = record("r7")
    decision = Gate().evaluate(
        candidate,
        Capability("read_only", True),
        RuntimeState(
            platform="android",
            python_version="3.14",
        ),
    )

    sink.record(
        EvidenceRecord(
            record_id=candidate.record_id,
            input_digest=candidate.input_digest,
            verification={"status": "PASS"},
            decision=decision.decision,
            reasons=decision.reasons,
        )
    )

    assert ledger.verify()
    assert ledger.all()[0].decision == "ALLOW"
