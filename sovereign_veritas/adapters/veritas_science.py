from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class VerificationResult:
    protocol_valid: bool
    evidence_admissible: bool
    prediction_status: str
    verifier_status: str
    claim_verdict: str
    refutes_claim: bool = False
    source: str = "veritas-science"

    def to_dict(self) -> dict[str, Any]:
        return {"protocol_valid": self.protocol_valid, "evidence_admissible": self.evidence_admissible, "prediction_status": self.prediction_status, "verifier_status": self.verifier_status, "claim_verdict": self.claim_verdict, "refutes_claim": self.refutes_claim, "source": self.source}


@dataclass
class VeritasScienceAdapter:
    source: str = "veritas-science"
    version: str = "0.1.1"

    def normalize(self, result: dict[str, Any]) -> VerificationResult:
        return VerificationResult(
            protocol_valid=result.get("claim_verdict") != "VOID",
            evidence_admissible=result.get("claim_verdict") not in {"INVALID_EVIDENCE"},
            prediction_status=result.get("prediction_status", "INDETERMINATE"),
            verifier_status=result.get("verifier_status", "NOT_TESTED"),
            claim_verdict=result.get("claim_verdict", "INSUFFICIENT_EVIDENCE"),
            refutes_claim=bool(result.get("refutation_criterion", False)),
            source=self.source,
        )

    def to_record(self, *, record_id: str, input_digest: str, prediction: dict[str, Any], verification: VerificationResult, capability: str | None = None, action: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        return {"record_id": record_id, "source": self.source, "version": self.version, "input_digest": input_digest, "prediction": prediction, "verification": verification.to_dict(), "capability": capability, "action": action, "metadata": metadata or {}}
