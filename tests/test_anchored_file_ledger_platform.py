"""Without POSIX file locking the anchored ledger must refuse to write, not write unlocked.

Runs on every platform, including Windows where the other anchored-ledger tests skip.
"""
import pytest

from sovereign_veritas import anchored_file_ledger as afl
from sovereign_veritas.evidence import EvidenceRecord


def test_refuses_to_append_without_flock(tmp_path, monkeypatch):
    monkeypatch.setattr(afl, "fcntl", None)
    ledger = afl.AnchoredFileLedger(tmp_path / "ledger.jsonl")
    with pytest.raises(RuntimeError, match="requires fcntl.flock"):
        ledger.append(EvidenceRecord(record_id="r1", input_digest="input"))
    assert not (tmp_path / "ledger.jsonl").exists() or (tmp_path / "ledger.jsonl").read_text() == ""
