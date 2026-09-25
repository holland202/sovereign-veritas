from __future__ import annotations

"""Stage-1 concurrency characterization for FileLedger.

This module answers: what actually happens when independent processes
append to the same JSONL ledger?

It does NOT claim concurrency safety. A "clean" outcome is a measurement,
not a proof. A broken chain or exception is also a valid measurement.
"""

import json
import multiprocessing as mp
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .evidence import EvidenceRecord
from .file_ledger import FileLedger


@dataclass(frozen=True)
class WorkerOutcome:
    worker_id: int
    attempted: int
    succeeded: int
    errors: tuple[str, ...]


@dataclass
class ConcurrencyReport:
    """Measured multi-process behavior. Not a safety certificate."""

    process_count: int
    records_per_process: int
    ledger_path: str
    worker_outcomes: list[WorkerOutcome] = field(default_factory=list)
    reload_ok: bool | None = None
    reload_error: str | None = None
    final_record_count: int | None = None
    expected_unique_ids: int | None = None
    unique_ids_on_disk: int | None = None
    file_size_bytes: int | None = None

    @property
    def total_succeeded(self) -> int:
        return sum(w.succeeded for w in self.worker_outcomes)

    @property
    def total_errors(self) -> int:
        return sum(len(w.errors) for w in self.worker_outcomes)

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim_level": "concurrency_characterization",
            "claim_text": (
                "Measured multi-process append behavior under the stated "
                "process_count and records_per_process. This is NOT a "
                "concurrency-safety or locking guarantee."
            ),
            "process_count": self.process_count,
            "records_per_process": self.records_per_process,
            "ledger_path": self.ledger_path,
            "total_succeeded": self.total_succeeded,
            "total_errors": self.total_errors,
            "reload_ok": self.reload_ok,
            "reload_error": self.reload_error,
            "final_record_count": self.final_record_count,
            "expected_unique_ids": self.expected_unique_ids,
            "unique_ids_on_disk": self.unique_ids_on_disk,
            "file_size_bytes": self.file_size_bytes,
            "workers": [
                {
                    "worker_id": w.worker_id,
                    "attempted": w.attempted,
                    "succeeded": w.succeeded,
                    "errors": list(w.errors),
                }
                for w in self.worker_outcomes
            ],
        }


def _worker(
    path_str: str,
    worker_id: int,
    count: int,
    result_queue: mp.Queue,
) -> None:
    path = Path(path_str)
    succeeded = 0
    errors: list[str] = []
    try:
        ledger = FileLedger(path)
        for i in range(count):
            rid = f"w{worker_id}_r{i}"
            try:
                ledger.append(
                    EvidenceRecord(
                        record_id=rid,
                        input_digest=f"d-{rid}",
                        verification={"status": "PASS"},
                    )
                )
                succeeded += 1
            except Exception as exc:
                errors.append(f"{type(exc).__name__}:{exc}")
    except Exception as exc:
        errors.append(f"init:{type(exc).__name__}:{exc}")
        errors.append(traceback.format_exc()[-500:])

    result_queue.put(
        {
            "worker_id": worker_id,
            "attempted": count,
            "succeeded": succeeded,
            "errors": errors,
        }
    )


class ConcurrencyProbe:
    """Run N processes against one FileLedger path and measure outcomes."""

    def __init__(self, work_dir: str | Path) -> None:
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)

    def run(
        self,
        *,
        process_count: int = 4,
        records_per_process: int = 25,
    ) -> ConcurrencyReport:
        if process_count < 1:
            raise ValueError("process_count must be >= 1")
        if records_per_process < 1:
            raise ValueError("records_per_process must be >= 1")

        path = self.work_dir / "concurrent_ledger.jsonl"
        if path.exists():
            path.unlink()

        # Seed empty file so all workers open the same path
        path.touch()

        ctx = mp.get_context("spawn")
        queue: mp.Queue = ctx.Queue()
        procs: list[mp.Process] = []

        for wid in range(process_count):
            p = ctx.Process(
                target=_worker,
                args=(str(path), wid, records_per_process, queue),
            )
            procs.append(p)
            p.start()

        for p in procs:
            p.join(timeout=60)
            if p.is_alive():
                p.terminate()
                p.join(timeout=5)

        outcomes: list[WorkerOutcome] = []
        while not queue.empty():
            raw = queue.get_nowait()
            outcomes.append(
                WorkerOutcome(
                    worker_id=raw["worker_id"],
                    attempted=raw["attempted"],
                    succeeded=raw["succeeded"],
                    errors=tuple(raw["errors"]),
                )
            )
        outcomes.sort(key=lambda o: o.worker_id)

        report = ConcurrencyReport(
            process_count=process_count,
            records_per_process=records_per_process,
            ledger_path=str(path),
            worker_outcomes=outcomes,
            expected_unique_ids=process_count * records_per_process,
        )

        if path.exists():
            report.file_size_bytes = path.stat().st_size

        try:
            reloaded = FileLedger(path)
            reloaded.verify()
            report.reload_ok = True
            report.final_record_count = len(reloaded.all())
            report.unique_ids_on_disk = len(
                {r.record_id for r in reloaded.all()}
            )
        except Exception as exc:
            report.reload_ok = False
            report.reload_error = f"{type(exc).__name__}:{exc}"
            # Best-effort count of well-formed lines
            try:
                lines = [
                    ln
                    for ln in path.read_text(encoding="utf-8").splitlines()
                    if ln.strip()
                ]
                ids: set[str] = set()
                for ln in lines:
                    try:
                        ids.add(json.loads(ln)["record"]["record_id"])
                    except Exception:
                        pass
                report.unique_ids_on_disk = len(ids)
                report.final_record_count = len(lines)
            except Exception:
                pass

        return report
