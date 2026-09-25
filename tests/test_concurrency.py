from __future__ import annotations

from sovereign_veritas.concurrency import ConcurrencyProbe


def test_concurrency_probe_runs_and_reports(tmp_path):
    """Characterize multi-process writes; do not assert safety."""
    probe = ConcurrencyProbe(tmp_path / "c")
    report = probe.run(process_count=3, records_per_process=10)

    d = report.to_dict()
    assert d["claim_level"] == "concurrency_characterization"
    assert "NOT a concurrency-safety" in d["claim_text"]
    assert d["process_count"] == 3
    assert d["records_per_process"] == 10
    assert len(report.worker_outcomes) == 3
    # Measurement always produced; reload_ok may be True or False
    assert report.reload_ok is not None
    assert isinstance(report.total_succeeded, int)
    assert report.total_succeeded >= 0


def test_concurrency_single_process_baseline(tmp_path):
    """One process should behave like sequential FileLedger use."""
    probe = ConcurrencyProbe(tmp_path / "s")
    report = probe.run(process_count=1, records_per_process=20)
    assert report.reload_ok is True
    assert report.final_record_count == 20
    assert report.unique_ids_on_disk == 20
    assert report.total_errors == 0


def test_claim_text_never_claims_safety(tmp_path):
    report = ConcurrencyProbe(tmp_path / "x").run(
        process_count=2, records_per_process=5
    )
    text = report.to_dict()["claim_text"].lower()
    assert "not" in text
    assert "safety" in text or "locking" in text
