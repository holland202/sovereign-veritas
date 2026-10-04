#!/usr/bin/env python3
"""RK-1 probe (registration: docs/RK1_PREREG.md, commit 10aa66d, pushed before this file existed).

A retry after a timeout, with the same or a fresh record_id. Counts external effects against ledger records.

  python tools/rk1_probe.py              exit 0 only if every registered prediction holds
  python tools/rk1_probe.py --sabotage   K2 runs against the content-keyed test double; must exit 1
Stdlib only. Reuses the XB-1 probe's sensor, predictor, verifier, counting executor and run_once.
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.dont_write_bytecode = True

import execution_boundary_probe as xb  # noqa: E402
from sovereign_veritas.evidence import Ledger, LedgerSink  # noqa: E402
from sovereign_veritas.file_ledger import FileLedger  # noqa: E402

SABOTAGE = "--sabotage" in sys.argv
PROBE_ACTION = {"capability": "read_only", "requested": "read", "parameters": {"t": 1}}


class TimeoutAfterEffect(xb.CountingExecutor):
    """Applies the effect, then loses the response, once. Later calls behave normally."""

    def __init__(self):
        super().__init__()
        self.timed_out = False

    def execute(self, action):
        result = super().execute(action)
        if not self.timed_out:
            self.timed_out = True
            raise TimeoutError("response lost after the effect was applied")
        return result


class ContentKeyedSink(LedgerSink):
    """TEST DOUBLE, not a proposed fix: also refuses when it already holds a record for the probe's action.
    has_record() only receives the record_id, so this double knows the probe's single action in advance."""

    def has_record(self, record_id):
        return super().has_record(record_id) or any(r.action == PROBE_ACTION for r in self.ledger.all())


def records(sink):
    return sink.ledger.all()


def statuses(sink):
    return [(r.metadata or {}).get("execution_status") for r in records(sink)]


def timeout_then_retry(sink_first, sink_retry, rid_first, rid_retry):
    ex = TimeoutAfterEffect()
    e1 = xb.attempt(lambda: xb.run_once(xb.make(sink_first, ex), rid_first))
    e2 = xb.attempt(lambda: xb.run_once(xb.make(sink_retry, ex), rid_retry))
    return ex.effects, e1, e2


def main():
    out, held = {}, {}
    with tempfile.TemporaryDirectory() as tmp:
        ex, sink = xb.CountingExecutor(), LedgerSink(Ledger())
        err = xb.attempt(lambda: xb.run_once(xb.make(sink, ex), "k0"))
        out["K0"] = (ex.effects, len(records(sink)), err, statuses(sink))

        sink = LedgerSink(Ledger())
        eff, e1, e2 = timeout_then_retry(sink, sink, "k1", "k1")
        out["K1"] = (eff, len(records(sink)), e2, statuses(sink), e1)

        sink = ContentKeyedSink(Ledger()) if SABOTAGE else LedgerSink(Ledger())
        eff, e1, e2 = timeout_then_retry(sink, sink, "k2-first", "k2-retry")
        out["K2"] = (eff, len(records(sink)), e2, statuses(sink), e1)

        path = os.path.join(tmp, "k3.jsonl")
        first = LedgerSink(FileLedger(path))
        ex = TimeoutAfterEffect()
        e1 = xb.attempt(lambda: xb.run_once(xb.make(first, ex), "k3-first"))
        rebuilt = LedgerSink(FileLedger(path))  # a new process builds its sink from disk
        e2 = xb.attempt(lambda: xb.run_once(xb.make(rebuilt, ex), "k3-retry"))
        final = LedgerSink(FileLedger(path))
        out["K3"] = (ex.effects, len(records(final)), e2, statuses(final), e1)

        sink = ContentKeyedSink(Ledger())
        eff, e1, e2 = timeout_then_retry(sink, sink, "k4-first", "k4-retry")
        out["K4"] = (eff, len(records(sink)), e2, statuses(sink), e1)

    for k, v in out.items():
        print(f"{k}: effects={v[0]} records={v[1]} retry_raised={v[2]!r} record_statuses={v[3]}"
              + (f" first_raised={v[4]!r}" if len(v) > 4 else ""))

    dup = lambda e: e is not None and "duplicate record_id refused before execution" in e
    held["RK0"] = out["K0"][:3] == (1, 1, None)
    held["RK1"] = out["K1"][0] == 1 and out["K1"][1] == 1 and dup(out["K1"][2])
    held["RK2"] = out["K1"][3] == ["FAILED"] and out["K1"][0] == 1
    held["RK3"] = out["K2"][:3] == (2, 2, None)
    held["RK4"] = out["K3"][:3] == (2, 2, None)
    held["RK5"] = out["K4"][0] == 1 and dup(out["K4"][2])
    print("\nmode:", "SABOTAGE (K2 uses the content-keyed test double)" if SABOTAGE else "normal")
    for k, ok in held.items():
        print(f"  {k}  {'HELD' if ok else 'NOT HELD'}")
    n = sum(held.values())
    print(f"VERDICT  {n} of {len(held)} as registered (RK6: run --sabotage, expect exit 1)")
    return 0 if n == len(held) else 1


if __name__ == "__main__":
    sys.exit(main())
