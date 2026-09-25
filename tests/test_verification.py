from sovereign_veritas.verification import (
    REFUSAL_REASONS,
    VerificationStatus,
)


def test_verification_status_coercion():
    assert VerificationStatus.coerce("PASS") is VerificationStatus.PASS
    assert VerificationStatus.coerce(None) is VerificationStatus.NOT_VERIFIED
    assert VerificationStatus.coerce("garbage") is VerificationStatus.UNKNOWN
    assert (
        VerificationStatus.coerce(VerificationStatus.REFUTED)
        is VerificationStatus.REFUTED
    )


def test_refusal_reasons_are_explicit():
    assert (
        REFUSAL_REASONS[VerificationStatus.FAIL]
        == "verification_not_passed"
    )
    assert (
        REFUSAL_REASONS[VerificationStatus.REFUTED]
        == "verification_refuted"
    )
