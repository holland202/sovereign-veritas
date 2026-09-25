#!/usr/bin/env python3
"""Controlled physical-interruption durability experiment for FileLedger.

This harness does not simulate power loss. It creates a disposable ledger,
writes with one writer, and provides a separate recovery command to run after
an externally induced interruption. Evidence remains characterization-level.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import signal
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from sovereign_veritas.evidence import EvidenceRecord
from sovereign_veritas.file_ledger import FileLedger

MANIFEST_NAME = "SESSION.json"
REPORT_NAME = "RECOVERY.json"
LEDGER_NAME = "durability_ledger.jsonl"
SCHEMA_VERSION = 1


def _atomic_json_write(path: Path, value: dict[str, Any]) -> None:
    tmp = path.with_name(path.name + ".tmp")
    payload = json.dumps(value, sort_keys=True, indent=2) + "\n"

    with tmp.open("w", encoding="utf-8") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())

    os.replace(tmp, path)

    try:
        fd = os.open(path.parent, os.O_RDONLY)
    except OSError:
        return

    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _getprop(name: str) -> str | None:
    try:
        result = subprocess.run(
            ["getprop", name],
            capture_output=True,
            text=True,
            check=False,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    value = result.stdout.strip()
    return value or None


def _environment() -> dict[str, Any]:
    u = platform.uname()

    return {
        "python": sys.version,
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "uname": {
            "system": u.system,
            "release": u.release,
            "version": u.version,
            "machine": u.machine,
        },
        "android_release": _getprop("ro.build.version.release"),
        "android_sdk": _getprop("ro.build.version.sdk"),
        "device_model": _getprop("ro.product.model"),
        "device_manufacturer": _getprop("ro.product.manufacturer"),
        "termux_prefix": os.environ.get("PREFIX"),
    }


def _record(index: int) -> EvidenceRecord:
    return EvidenceRecord(
        record_id=f"physical-dur-{index:08d}",
        input_digest=f"physical-input-{index:08d}",
        verification={"status": "PASS"},
    )


@dataclass
class RecoveryReport:
    schema_version: int
    session_id: str
    interruption_method: str
    recovered_ok: bool
    recovered_count: int | None
    ledger_size_bytes: int
    ledger_sha256: str
    reload_error: str | None
    manifest_status: str | None
    environment: dict[str, Any]
    recovered_at_epoch_s: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def run_writer(work_dir: Path, interval_s: float) -> int:
    work_dir.mkdir(parents=True, exist_ok=True)

    ledger_path = work_dir / LEDGER_NAME

    if ledger_path.exists():
        raise FileExistsError(
            f"{ledger_path} exists; use a new disposable directory"
        )

    session_id = f"{int(time.time())}-{os.getpid()}"

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "session_id": session_id,
        "status": "running",
        "started_at_epoch_s": time.time(),
        "pid": os.getpid(),
        "ledger": LEDGER_NAME,
        "environment": _environment(),
        "operator_note": (
            "Disposable experiment; never use production evidence."
        ),
    }

    _atomic_json_write(work_dir / MANIFEST_NAME, manifest)

    ledger = FileLedger(ledger_path)
    stopping = False

    def stop(_signum: int, _frame: Any) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    print(
        json.dumps(
            {
                "mode": "writer",
                "session_id": session_id,
                "pid": os.getpid(),
                "ledger": str(ledger_path),
                "status": "running",
                "abrupt_test": (
                    "Use an external SIGKILL/force-stop/reboot; "
                    "do not use SIGINT/SIGTERM."
                ),
            }
        ),
        flush=True,
    )

    index = 0

    while not stopping:
        ledger.append(_record(index))
        index += 1

        if interval_s > 0:
            time.sleep(interval_s)

    manifest["status"] = "clean_stop"
    manifest["stopped_at_epoch_s"] = time.time()
    manifest["records_written"] = index

    _atomic_json_write(work_dir / MANIFEST_NAME, manifest)

    print(
        json.dumps(
            {
                "status": "clean_stop",
                "records_written": index,
            }
        ),
        flush=True,
    )

    return 0


def recover(work_dir: Path, interruption_method: str) -> RecoveryReport:
    manifest_path = work_dir / MANIFEST_NAME
    ledger_path = work_dir / LEDGER_NAME

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    recovered_ok = False
    recovered_count: int | None = None
    reload_error: str | None = None

    try:
        ledger = FileLedger(ledger_path)
        ledger.verify()

        recovered_ok = True
        recovered_count = len(ledger.all())

    except Exception as exc:
        reload_error = f"{type(exc).__name__}:{exc}"

    report = RecoveryReport(
        schema_version=SCHEMA_VERSION,
        session_id=str(manifest["session_id"]),
        interruption_method=interruption_method,
        recovered_ok=recovered_ok,
        recovered_count=recovered_count,
        ledger_size_bytes=ledger_path.stat().st_size,
        ledger_sha256=_sha256(ledger_path),
        reload_error=reload_error,
        manifest_status=manifest.get("status"),
        environment=_environment(),
        recovered_at_epoch_s=time.time(),
    )

    _atomic_json_write(work_dir / REPORT_NAME, report.to_dict())

    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)

    sub = parser.add_subparsers(dest="command", required=True)

    writer = sub.add_parser("writer")
    writer.add_argument("work_dir", type=Path)
    writer.add_argument("--interval-s", type=float, default=0.01)

    rec = sub.add_parser("recover")
    rec.add_argument("work_dir", type=Path)
    rec.add_argument(
        "--interruption-method",
        required=True,
        choices=(
            "sigkill",
            "termux-force-stop",
            "device-reboot",
            "power-loss",
            "other",
        ),
    )

    args = parser.parse_args()

    if args.command == "writer":
        return run_writer(args.work_dir, args.interval_s)

    recover(args.work_dir, args.interruption_method)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
