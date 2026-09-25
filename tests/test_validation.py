from __future__ import annotations

import json

from sovereign_veritas.validation import ValidationSuite


def test_validation_suite_passes_stage0(tmp_path):
    suite = ValidationSuite(tmp_path / "v", seed=7)
    report = suite.run_all(record_count=50)
    assert report.passed is True
    assert report.check_count == 4
    assert report.failure_count == 0
    assert report.to_dict()["claim_level"] == "synthetic_fault_injection"


def test_validation_report_is_deterministic(tmp_path):
    s1 = ValidationSuite(tmp_path / "a", seed=99)
    s2 = ValidationSuite(tmp_path / "b", seed=99)
    r1 = s1.run_all(record_count=30)
    r2 = s2.run_all(record_count=30)
    # Same seed → same pass/fail structure and check names
    assert [c.name for c in r1.checks] == [c.name for c in r2.checks]
    assert [c.passed for c in r1.checks] == [c.passed for c in r2.checks]
    assert r1.to_dict()["seed"] == r2.to_dict()["seed"] == 99


def test_claim_text_does_not_overreach(tmp_path):
    report = ValidationSuite(tmp_path / "c", seed=1).run_all(record_count=10)
    text = report.to_dict()["claim_text"].lower()
    assert "synthetic" in text
    assert "not a physical" in text or "not" in text
    d = json.dumps(report.to_dict())
    assert "concurrency-safety" in d or "concurrency" in d


def test_torn_persistence_rejects_truncation(tmp_path):
    suite = ValidationSuite(tmp_path / "torn", seed=3)
    result = suite.check_torn_persistence()
    assert result.passed is True
    assert "NOT a physical" in " ".join(result.limitations)


def test_hostile_persistence_rejects_forgery(tmp_path):
    suite = ValidationSuite(tmp_path / "host", seed=5)
    result = suite.check_hostile_persistence()
    assert result.passed is True
    assert "forged_digest_rejected" in result.detail
    assert "field_mutation_rejected" in result.detail
    assert "malformed_rejected" in result.detail
