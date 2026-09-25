from __future__ import annotations

from enum import Enum


class VerificationStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    REFUTED = "REFUTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    NOT_VERIFIED = "NOT_VERIFIED"
    UNKNOWN = "UNKNOWN"

    @classmethod
    def coerce(cls, value: object) -> "VerificationStatus":
        if isinstance(value, cls):
            return value
        if value is None:
            return cls.NOT_VERIFIED
        try:
            return cls(str(value))
        except ValueError:
            return cls.UNKNOWN


REFUSAL_REASONS: dict[VerificationStatus, str] = {
    VerificationStatus.FAIL: "verification_not_passed",
    VerificationStatus.NOT_VERIFIED: "verification_not_passed",
    VerificationStatus.UNKNOWN: "verification_not_passed",
    VerificationStatus.REFUTED: "verification_refuted",
}
