from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class VeritasScienceAdapter:
    source: str = "veritas-science"
    version: str = "0.1.0"

    def to_record(
        self,
        *,
        record_id: str,
        input_digest: str,
        prediction: dict[str, Any],
        verification: dict[str, Any],
        capability: str | None = None,
        action: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "record_id": record_id,
            "source": self.source,
            "version": self.version,
            "input_digest": input_digest,
            "prediction": prediction,
            "verification": verification,
            "capability": capability,
            "action": action,
            "metadata": metadata or {},
        }

    def verify_status(self, result: dict[str, Any]) -> dict[str, Any]:
        verdict = result.get("claim_verdict", "INSUFFICIENT_EVIDENCE")
        return {
            "status": "PASS" if verdict in {"SUPPORTED", "REFUTED"} else "FAIL",
            "verdict": verdict,
            "source": self.source,
        }
