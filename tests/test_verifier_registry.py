import pytest

from sovereign_veritas.verifier_registry import (
    VerifierRegistry,
    VerifierValidationStatus,
)


def test_new_verifier_is_unvalidated():
    registry = VerifierRegistry()
    registry.register("v1", object())

    validation = registry.validation("v1")

    assert validation is not None
    assert validation.status is VerifierValidationStatus.UNTESTED
    assert validation.coverage == 0.0
    assert not registry.is_validated("v1")


def test_meaningful_probe_can_validate():
    registry = VerifierRegistry(min_coverage=0.5)
    registry.register("v1", object())

    validation = registry.record_probe(
        "v1",
        passed=True,
        meaningful=True,
    )

    assert validation.status is VerifierValidationStatus.VALIDATED
    assert validation.total_probes == 1
    assert validation.meaningful_probes == 1
    assert validation.meaningful_passes == 1


def test_vacuous_probe_counts_in_denominator():
    registry = VerifierRegistry(min_coverage=0.5)
    registry.register("v1", object())

    registry.record_probe("v1", passed=True, meaningful=False)
    validation = registry.record_probe("v1", passed=True, meaningful=True)

    assert validation.total_probes == 2
    assert validation.meaningful_probes == 1
    assert validation.coverage == 0.5
    assert validation.status is VerifierValidationStatus.VALIDATED


def test_failed_probe_is_terminal_failure():
    registry = VerifierRegistry()
    registry.register("v1", object())

    validation = registry.record_probe(
        "v1",
        passed=False,
        meaningful=True,
    )

    assert validation.status is VerifierValidationStatus.FAILED
    assert registry.is_failed("v1")


def test_unknown_verifier_probe_fails_closed():
    registry = VerifierRegistry()

    with pytest.raises(KeyError):
        registry.record_probe("missing", passed=True)
