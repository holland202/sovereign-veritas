from __future__ import annotations

import json

import pytest

from sovereign_veritas.capability import Capability
from sovereign_veritas.decision import Gate
from sovereign_veritas.evidence import EvidenceRecord
from sovereign_veritas.file_ledger import FileLedger
from sovereign_veritas.runtime import RuntimeState


def record(record_id: str) -> EvidenceRecord:
    return EvidenceRecord(
        record_id=record_id,
        input_digest="abc",
        verification={"status": "PASS"},
    )


def test_clean_reload_passes(tmp_path):
    path = tmp_path / "ledger.jsonl"

    first = FileLedger(path)
    first.append(record("a"))
    first.append(record("b"))

    second = FileLedger(path)

    assert len(second.all()) == 2
    assert second.verify()


def test_content_tamper_is_detected_on_load(tmp_path):
    path = tmp_path / "ledger.jsonl"

    ledger = FileLedger(path)
    ledger.append(record("a"))

    raw = path.read_text(encoding="utf-8").replace('"abc"', '"xyz"')
    path.write_text(raw, encoding="utf-8")

    with pytest.raises(ValueError, match="tampered"):
        FileLedger(path)


def test_missing_middle_record_breaks_chain_on_load(tmp_path):
    path = tmp_path / "ledger.jsonl"

    ledger = FileLedger(path)
    ledger.append(record("a"))
    ledger.append(record("b"))
    ledger.append(record("c"))

    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text(
        "\n".join(lines[:1] + lines[2:]) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="chain broken"):
        FileLedger(path)


def test_truncated_json_line_is_rejected(tmp_path):
    path = tmp_path / "ledger.jsonl"

    ledger = FileLedger(path)
    ledger.append(record("a"))
    ledger.append(record("b"))

    with path.open("r+b") as handle:
        handle.seek(0, 2)
        handle.truncate(handle.tell() - 10)

    with pytest.raises(ValueError, match="invalid JSON"):
        FileLedger(path)


def test_malformed_json_is_rejected(tmp_path):
    path = tmp_path / "ledger.jsonl"

    path.write_text("{not-json}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="invalid JSON"):
        FileLedger(path)


def test_duplicate_id_across_restarts_is_rejected(tmp_path):
    path = tmp_path / "ledger.jsonl"

    ledger = FileLedger(path)
    ledger.append(record("a"))

    with pytest.raises(ValueError, match="duplicate"):
        ledger.append(record("a"))


def test_gate_runs_against_reloaded_ledger(tmp_path):
    path = tmp_path / "ledger.jsonl"

    FileLedger(path).append(record("a"))

    reloaded = FileLedger(path)
    fresh = reloaded.append(record("b"))

    decision = Gate().evaluate(
        fresh,
        Capability("read_only", True),
        RuntimeState(
            platform="android",
            python_version="3.14",
        ),
    )

    assert decision.decision == "ALLOW"
    assert len(reloaded.all()) == 2


def test_persisted_digest_matches_after_reload(tmp_path):
    path = tmp_path / "ledger.jsonl"

    first = FileLedger(path)
    appended = first.append(record("a"))

    second = FileLedger(path)

    assert second.all()[0].record_digest == appended.record_digest
    assert second.as_dicts()[0]["record_digest"] == appended.record_digest


def test_empty_ledger_is_valid(tmp_path):
    path = tmp_path / "ledger.jsonl"

    ledger = FileLedger(path)

    assert ledger.all() == []
    assert ledger.verify()
