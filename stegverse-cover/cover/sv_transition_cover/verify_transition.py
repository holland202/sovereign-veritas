"""Offline pair verifier for the Sovereign Veritas covering (StegVerse Build Lane).

Shares no code with the covering's writer path beyond the published formats (the
transition ledger's canonical-JSON chain; EO-2's observation and verdict function,
which it re-runs rather than trusts - the gate_replay discipline applied to effects).

Given the evidence records a run produced and the transition ledger, it checks the
PAIR, which is what neither side can check alone:

    V1  the transition ledger's hash chain is intact;
    V2  no record_id carries two INTENTs;
    V3  every evidence record claiming execution_status SUCCEEDED has a COMPLETION
        whose action digest matches the record's action, whose stored EO-2 verdict
        recomputes from the stored observation, and whose verdict attests the
        effect (OK or UNOBSERVABLE);
    V4  every COMPLETION has its evidence record - a completion standing alone is
        named (XB-1 X5's asymmetry), never passed over in silence;
    V5  no COMPLETION exists for a record that claims no execution - the EO-1
        construction (executor ran, record says it did not) fails here, where the
        package alone verified CONSISTENT;
    V6  open transitions (INTENT with no COMPLETION and no UNKNOWN) and UNKNOWN
        transitions are listed by record_id: open is a state, reported, and never
        counted as success.

Verdict language follows the repository's verifier: CONSISTENT, or the failed
checks named. Exit code 0 iff CONSISTENT.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from sovereign_veritas.effect_observation import action_digest, check_observed_effect
from sovereign_veritas.evidence import canonical_json

ATTESTING = {"OK", "UNOBSERVABLE"}


def _entry_hash(entry: dict[str, Any]) -> str:
    body = {k: v for k, v in entry.items() if k != "hash"}
    return "sha256:" + hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()


def load_chain(path: str | Path) -> tuple[list[dict[str, Any]], list[str]]:
    failures: list[str] = []
    entries: list[dict[str, Any]] = []
    prev = "GENESIS"
    text = Path(path).read_text(encoding="utf-8") if Path(path).exists() else ""
    for line in text.splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        if entry.get("prev") != prev:
            failures.append(f"V1 chain prev mismatch at seq {entry.get('seq')}")
        if _entry_hash(entry) != entry.get("hash"):
            failures.append(f"V1 entry hash mismatch at seq {entry.get('seq')}")
        prev = entry.get("hash", prev)
        entries.append(entry)
    return entries, failures


def verify(records: list[dict[str, Any]], ledger_path: str | Path) -> list[str]:
    entries, failures = load_chain(ledger_path)
    intents: dict[str, dict[str, Any]] = {}
    completions: dict[str, dict[str, Any]] = {}
    unknowns: dict[str, dict[str, Any]] = {}
    for e in entries:
        rid = e["record_id"]
        if e["kind"] == "INTENT":
            if rid in intents:
                failures.append(f"V2 duplicate INTENT for {rid}")
            intents[rid] = e
        elif e["kind"] == "COMPLETION":
            completions[rid] = e
        elif e["kind"] == "UNKNOWN":
            unknowns[rid] = e

    by_id = {r.get("record_id"): r for r in records}
    for rid, record in by_id.items():
        status = (record.get("metadata") or {}).get("execution_status")
        if status == "SUCCEEDED":
            comp = completions.get(rid)
            if comp is None:
                failures.append(f"V3 SUCCEEDED claimed with no COMPLETION: {rid}")
                continue
            if comp["observation"].get("action_digest") != action_digest(record.get("action")):
                failures.append(f"V3 completion action digest mismatch: {rid}")
            recomputed = check_observed_effect(record, comp["observation"], comp.get("expected"))
            if recomputed != comp["effect_verdict"]:
                failures.append(
                    f"V3 stored verdict {comp['effect_verdict']} does not recompute "
                    f"({recomputed}): {rid}")
            elif comp["effect_verdict"] not in ATTESTING:
                failures.append(
                    f"V3 effect not attested (verdict {comp['effect_verdict']}): {rid}")
        else:
            if rid in completions:
                failures.append(
                    f"V5 COMPLETION exists for a record claiming no execution: {rid}")
    for rid in completions:
        if rid not in by_id:
            failures.append(f"V4 COMPLETION without its evidence record: {rid}")
    open_ids = [rid for rid in intents if rid not in completions and rid not in unknowns]
    for rid in open_ids:
        failures.append(f"V6 open transition (INTENT, no COMPLETION, no UNKNOWN): {rid}")
    for rid in unknowns:
        if rid not in completions:
            print(f"note  UNKNOWN transition held for a person: {rid} ({unknowns[rid].get('why')})")
    return failures


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: verify_transition.py <transition-ledger.jsonl> <records.json>")
        return 2
    records = json.loads(Path(argv[2]).read_text(encoding="utf-8"))
    failures = verify(records, argv[1])
    if failures:
        for f in failures:
            print(f"FAIL  {f}")
        print(f"VERDICT  {len(failures)} check(s) failed")
        return 1
    print("VERDICT  CONSISTENT")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
