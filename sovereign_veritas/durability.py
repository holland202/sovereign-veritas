from __future__ import annotations

"""Stage-2 durability characterization for FileLedger.

Answers: after an interrupted single-writer append sequence, does reload
fail closed or recover a valid chain?

This is NOT a physical power-cycle test. Automated proxies:
  - stop after N successful appends (clean stop)
  - stop after writing a partial line to the file (torn write simulation)
  - operator SIGKILL during a long run (manual; record separately)

Physical wall-power loss on device remains a manual experiment.
"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from .evidence import EvidenceRecord
from .file_ledger import FileLedger

StopMode = Literal["clean", "torn_last_line"]


@dataclass
class DurabilityReport:
    mode: str
    target_records: int
    records_written_before_stop: int
    ledger_path: str
    reload_ok: bool | None = None
    reload_error: str | None = None
    recovered_count: int | None = None
    file_size_bytes: int | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim_level": "durability_characterization",
            "claim_text": (
                "Measured single-writer interrupt/restart recovery under the "
                "stated mode. This is NOT a physical power-cycle or dirty "
                "filesystem claim."
            ),
            "mode": self.mode,
            "target_records": self.target_records,
            "records_written_before_stop": self.records_written_before_stop,
            "ledger_path": self.ledger_path,
            "reload_ok": self.reload_ok,
            "reload_error": self.reload_error,
            "recovered_count": self.recovered_count,
            "file_size_bytes": self.file_size_bytes,
            "notes": list(self.notes),
        }


def _record(i: int) -> EvidenceRecord:
    return EvidenceRecord(
        record_id=f"dur-{i}",
        input_digest=f"d-{i}",
        verification={"status": "PASS"},
    )


class DurabilityProbe:
    """Single-writer write → interrupt proxy → reload characterization."""

    def __init__(self, work_dir: str | Path) -> None:
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)

    def run(
        self,
        *,
        target_records: int = 100,
        stop_after: int | None = None,
        mode: StopMode = "clean",
    ) -> DurabilityReport:
        """Write records, stop per mode, then attempt FileLedger reload.

        stop_after: if set, stop after this many successful appends
                    (default: target_records for clean full run).
        mode:
          clean         — stop between complete records
          torn_last_line — after stop_after records, append a partial JSON line
        """
        if target_records < 1:
            raise ValueError("target_records must be >= 1")

        path = self.work_dir / "durability_ledger.jsonl"
        if path.exists():
            path.unlink()

        limit = stop_after if stop_after is not None else target_records
        if limit < 0:
            raise ValueError("stop_after must be >= 0")

        written = 0
        ledger = FileLedger(path)
        for i in range(limit):
            ledger.append(_record(i))
            written += 1

        notes: list[str] = []
        if mode == "torn_last_line":
            # Simulate a torn write: incomplete line at end of file.
            with path.open("a", encoding="utf-8") as handle:
                handle.write('{"record": {"record_id": "TORN"')
                handle.flush()
                os.fsync(handle.fileno())
            notes.append("appended_partial_json_line_without_newline_close")

        report = DurabilityReport(
            mode=mode,
            target_records=target_records,
            records_written_before_stop=written,
            ledger_path=str(path),
            notes=notes,
        )

        if path.exists():
            report.file_size_bytes = path.stat().st_size

        try:
            reloaded = FileLedger(path)
            reloaded.verify()
            report.reload_ok = True
            report.recovered_count = len(reloaded.all())
        except Exception as exc:
            report.reload_ok = False
            report.reload_error = f"{type(exc).__name__}:{exc}"

        return report
