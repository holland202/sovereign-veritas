from __future__ import annotations

from sovereign_veritas.durability import DurabilityProbe


def test_clean_stop_recovers_full_chain(tmp_path):
    probe = DurabilityProbe(tmp_path / "d")
    report = probe.run(target_records=40, mode="clean")
    assert report.reload_ok is True
    assert report.recovered_count == 40
    assert report.to_dict()["claim_level"] == "durability_characterization"
    assert "NOT a physical power-cycle" in report.to_dict()["claim_text"]


def test_torn_last_line_fail_closed(tmp_path):
    probe = DurabilityProbe(tmp_path / "t")
    report = probe.run(target_records=20, stop_after=20, mode="torn_last_line")
    assert report.reload_ok is False
    assert report.reload_error is not None
    assert report.records_written_before_stop == 20


def test_early_clean_stop(tmp_path):
    probe = DurabilityProbe(tmp_path / "e")
    report = probe.run(target_records=100, stop_after=15, mode="clean")
    assert report.reload_ok is True
    assert report.recovered_count == 15
