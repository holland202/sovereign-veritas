import json

import pytest

from sovereign_veritas.anchored_file_ledger import AnchoredFileLedger
from sovereign_veritas import anchored_file_ledger as _afl
from sovereign_veritas.evidence import EvidenceRecord

pytestmark = pytest.mark.skipif(
    _afl.fcntl is None,
    reason="AnchoredFileLedger needs POSIX fcntl.flock (absent on Windows); it fails closed there - see test_anchored_file_ledger_platform.py",
)


def record(record_id, value):
    return EvidenceRecord(
        record_id=record_id,
        input_digest="input",
        prediction={"value": value},
        verification={"status": "PASS"},
        metadata={},
    )


def test_append_creates_ledger_and_anchor(tmp_path):
    path = tmp_path / "ledger.jsonl"
    ledger = AnchoredFileLedger(path)

    ledger.append(record("r1", 1))

    assert path.exists()
    assert (tmp_path / "ledger.jsonl.anchor").exists()
    assert (tmp_path / "ledger.jsonl.lock").exists()


def test_reload_accepts_matching_anchor(tmp_path):
    path = tmp_path / "ledger.jsonl"

    ledger = AnchoredFileLedger(path)
    ledger.append(record("r1", 1))
    ledger.append(record("r2", 2))

    reloaded = AnchoredFileLedger(path)

    assert [r.record_id for r in reloaded.all()] == ["r1", "r2"]


def test_append_updates_anchor_head_and_count(tmp_path):
    path = tmp_path / "ledger.jsonl"
    ledger = AnchoredFileLedger(path)

    first = ledger.append(record("r1", 1))
    second = ledger.append(record("r2", 2))

    anchor = json.loads(
        (tmp_path / "ledger.jsonl.anchor").read_text()
    )

    assert anchor["count"] == 2
    assert anchor["head_digest"] == second.record_digest
    assert anchor["history"] == [
        first.record_digest,
        second.record_digest,
    ]


def test_anchor_detects_ledger_rollback(tmp_path):
    path = tmp_path / "ledger.jsonl"
    ledger = AnchoredFileLedger(path)
    ledger.append(record("r1", 1))
    ledger.append(record("r2", 2))

    lines = path.read_text().splitlines()
    path.write_text(lines[0] + "\n")

    with pytest.raises(ValueError, match="truncated"):
        AnchoredFileLedger(path)


def test_anchor_detects_history_rewrite(tmp_path):
    path = tmp_path / "ledger.jsonl"
    ledger = AnchoredFileLedger(path)
    ledger.append(record("r1", 1))
    ledger.append(record("r2", 2))

    lines = path.read_text().splitlines()
    entry = json.loads(lines[0])
    entry["record"]["prediction"]["value"] = 999
    lines[0] = json.dumps(entry)
    path.write_text("\\n".join(lines) + "\\n")

    with pytest.raises(ValueError):
        AnchoredFileLedger(path)


def test_anchor_rejects_count_history_mismatch(tmp_path):
    path = tmp_path / "ledger.jsonl"
    ledger = AnchoredFileLedger(path)
    ledger.append(record("r1", 1))

    anchor_path = tmp_path / "ledger.jsonl.anchor"
    anchor = json.loads(anchor_path.read_text())
    anchor["count"] = 2
    anchor_path.write_text(json.dumps(anchor))

    with pytest.raises(ValueError, match="count"):
        AnchoredFileLedger(path)


def test_anchor_accepts_valid_suffix_after_anchor(tmp_path):
    path = tmp_path / "ledger.jsonl"
    ledger = AnchoredFileLedger(path)
    ledger.append(record("r1", 1))

    anchor = json.loads(
        (tmp_path / "ledger.jsonl.anchor").read_text()
    )

    # Simulate a crash after the ledger append but before anchor update.
    second = record("r2", 2)
    ledger.append(second)

    # Restore the old anchor deliberately.
    (tmp_path / "ledger.jsonl.anchor").write_text(
        json.dumps(anchor)
    )

    recovered = AnchoredFileLedger(path)

    assert [r.record_id for r in recovered.all()] == ["r1", "r2"]


def test_invalid_anchor_schema_fails_closed(tmp_path):
    path = tmp_path / "ledger.jsonl"
    ledger = AnchoredFileLedger(path)
    ledger.append(record("r1", 1))

    anchor_path = tmp_path / "ledger.jsonl.anchor"
    anchor = json.loads(anchor_path.read_text())
    anchor["schema"] = 999
    anchor_path.write_text(json.dumps(anchor))

    with pytest.raises(ValueError, match="schema"):
        AnchoredFileLedger(path)
