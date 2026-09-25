from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .evidence import EvidenceRecord
from .file_ledger import FileLedger


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    detail: str = ""
    limitations: tuple[str, ...] = ()


@dataclass
class ValidationReport:
    seed: int
    checks: list[CheckResult] = field(default_factory=list)

    def add(self, result: CheckResult) -> None:
        self.checks.append(result)

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)

    @property
    def check_count(self) -> int:
        return len(self.checks)

    @property
    def failure_count(self) -> int:
        return sum(1 for c in self.checks if not c.passed)

    def to_dict(self) -> dict[str, Any]:
        return {
            "seed": self.seed,
            "passed": self.passed,
            "check_count": self.check_count,
            "failure_count": self.failure_count,
            "checks": [
                {
                    "name": c.name,
                    "passed": c.passed,
                    "detail": c.detail,
                    "limitations": list(c.limitations),
                }
                for c in self.checks
            ],
            "claim_level": "synthetic_fault_injection",
            "claim_text": (
                "The specified synthetic fault model was rejected or contained. "
                "This is not a physical power-cycle, concurrency-safety, or "
                "motivated-adversary claim."
            ),
        }


def _record(record_id: str, digest: str = "inp") -> EvidenceRecord:
    return EvidenceRecord(
        record_id=record_id,
        input_digest=digest,
        verification={"status": "PASS"},
    )


class ValidationSuite:
    """Stage-0 deterministic fault injection against FileLedger.

    Allowed claim when all checks pass:
      The specified synthetic fault model was rejected/contained.

    Not claimed: physical power-loss recovery, multi-process locking,
    concurrency safety, or motivated-adversary resistance.
    """

    def __init__(self, work_dir: str | Path, seed: int = 42) -> None:
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.seed = seed
        self._rng = random.Random(seed)

    def run_all(self, record_count: int = 100) -> ValidationReport:
        report = ValidationReport(seed=self.seed)
        report.add(self.check_ledger_restart(record_count=record_count))
        report.add(self.check_torn_persistence())
        report.add(self.check_duplicate_writer_identity())
        report.add(self.check_hostile_persistence())
        return report

    def check_ledger_restart(self, record_count: int = 100) -> CheckResult:
        """Write N records, reload FileLedger, verify count and chain."""
        path = self.work_dir / f"restart_{self.seed}.jsonl"
        if path.exists():
            path.unlink()

        limitations = (
            "Single-process sequential writers only",
            "Not a multi-process concurrency test",
        )

        try:
            ledger = FileLedger(path)
            for i in range(record_count):
                ledger.append(_record(f"r{i}", digest=f"d{i}"))

            reloaded = FileLedger(path)
            if len(reloaded.all()) != record_count:
                return CheckResult(
                    "ledger_restart",
                    False,
                    f"count_mismatch:{len(reloaded.all())}!={record_count}",
                    limitations,
                )
            reloaded.verify()
            return CheckResult(
                "ledger_restart",
                True,
                f"reloaded_{record_count}_records",
                limitations,
            )
        except Exception as exc:
            return CheckResult(
                "ledger_restart",
                False,
                f"exception:{type(exc).__name__}:{exc}",
                limitations,
            )

    def check_torn_persistence(self) -> CheckResult:
        """Truncate JSONL at deterministic offsets; load must fail closed.

        Models torn writes. NOT a physical power-cycle test.
        """
        path = self.work_dir / f"torn_{self.seed}.jsonl"
        if path.exists():
            path.unlink()

        limitations = (
            "Synthetic byte truncation only",
            "NOT a physical power-cycle or crash test",
        )

        try:
            ledger = FileLedger(path)
            for i in range(10):
                ledger.append(_record(f"t{i}", digest=f"td{i}"))

            raw = path.read_bytes()
            if len(raw) < 20:
                return CheckResult(
                    "torn_persistence",
                    False,
                    "ledger_too_small_to_truncate",
                    limitations,
                )

            # Deterministic offsets: near end, mid, and after first newline
            offsets = sorted(
                {
                    max(1, len(raw) // 4),
                    max(1, len(raw) // 2),
                    max(1, len(raw) - 7),
                    max(1, self._rng.randint(1, len(raw) - 1)),
                }
            )

            failures_detected = 0
            for off in offsets:
                torn_path = self.work_dir / f"torn_{self.seed}_{off}.jsonl"
                torn_path.write_bytes(raw[:off])
                try:
                    FileLedger(torn_path)
                    # If load succeeds, chain must still verify; partial last
                    # line should fail JSON. Success without error is a miss.
                    return CheckResult(
                        "torn_persistence",
                        False,
                        f"truncation_accepted_at_offset:{off}",
                        limitations,
                    )
                except ValueError:
                    failures_detected += 1

            if failures_detected == len(offsets):
                return CheckResult(
                    "torn_persistence",
                    True,
                    f"rejected_{failures_detected}_truncations",
                    limitations,
                )
            return CheckResult(
                "torn_persistence",
                False,
                f"only_rejected_{failures_detected}_of_{len(offsets)}",
                limitations,
            )
        except Exception as exc:
            return CheckResult(
                "torn_persistence",
                False,
                f"exception:{type(exc).__name__}:{exc}",
                limitations,
            )

    def check_duplicate_writer_identity(self) -> CheckResult:
        """Second independent FileLedger cannot append a duplicate record_id.

        Not concurrent-writer serialization testing.
        """
        path = self.work_dir / f"dup_{self.seed}.jsonl"
        if path.exists():
            path.unlink()

        limitations = (
            "Sequential independent instances only",
            "Not multi-process locking or concurrent-writer safety",
        )

        try:
            first = FileLedger(path)
            first.append(_record("shared", digest="a"))

            second = FileLedger(path)
            try:
                second.append(_record("shared", digest="b"))
                return CheckResult(
                    "duplicate_writer_identity",
                    False,
                    "duplicate_id_accepted",
                    limitations,
                )
            except ValueError as exc:
                if "duplicate" in str(exc).lower():
                    return CheckResult(
                        "duplicate_writer_identity",
                        True,
                        "duplicate_rejected_after_reload",
                        limitations,
                    )
                return CheckResult(
                    "duplicate_writer_identity",
                    False,
                    f"unexpected_error:{exc}",
                    limitations,
                )
        except Exception as exc:
            return CheckResult(
                "duplicate_writer_identity",
                False,
                f"exception:{type(exc).__name__}:{exc}",
                limitations,
            )

    def check_hostile_persistence(self) -> CheckResult:
        """Malformed JSON, field mutation without digest update, forged digest."""
        limitations = (
            "Synthetic hostile file content only",
            "Not a motivated online adversary",
        )

        cases_passed = 0
        details: list[str] = []

        # 1) Malformed JSON line
        p1 = self.work_dir / f"hostile_malformed_{self.seed}.jsonl"
        p1.write_text("{not json\n", encoding="utf-8")
        try:
            FileLedger(p1)
            details.append("malformed_accepted")
        except ValueError:
            cases_passed += 1
            details.append("malformed_rejected")

        # 2) Valid structure but field mutated without updating digest
        p2 = self.work_dir / f"hostile_mutate_{self.seed}.jsonl"
        if p2.exists():
            p2.unlink()
        clean = FileLedger(p2)
        clean.append(_record("h1", digest="orig"))
        entry = json.loads(p2.read_text(encoding="utf-8").strip())
        entry["record"]["input_digest"] = "TAMPERED"
        # keep stored record_digest unchanged → should fail recompute check
        p2.write_text(json.dumps(entry) + "\n", encoding="utf-8")
        try:
            FileLedger(p2)
            details.append("field_mutation_accepted")
        except ValueError:
            cases_passed += 1
            details.append("field_mutation_rejected")

        # 3) Forged record_digest (content intact, digest wrong)
        p3 = self.work_dir / f"hostile_digest_{self.seed}.jsonl"
        if p3.exists():
            p3.unlink()
        clean3 = FileLedger(p3)
        clean3.append(_record("h2", digest="orig2"))
        entry3 = json.loads(p3.read_text(encoding="utf-8").strip())
        entry3["record_digest"] = "0" * 64
        p3.write_text(json.dumps(entry3) + "\n", encoding="utf-8")
        try:
            FileLedger(p3)
            details.append("forged_digest_accepted")
        except ValueError:
            cases_passed += 1
            details.append("forged_digest_rejected")

        passed = cases_passed == 3
        return CheckResult(
            "hostile_persistence",
            passed,
            ";".join(details),
            limitations,
        )
