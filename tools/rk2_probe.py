#!/usr/bin/env python3
"""RK-2 probe (registration: docs/RK2_PREREG.md, commit 262c23a, pushed before this file or the change existed).

Effects are counted at the executor; the ledger and the reservation store are compared with them.

  python tools/rk2_probe.py              exit 0 only if every registered prediction R1-R10 holds
  python tools/rk2_probe.py --sabotage   A5 uses a NON-atomic memory store (check, sleep, write); must exit 1
Stdlib only.
"""
import os
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.dont_write_bytecode = True

import execution_boundary_probe as xb  # noqa: E402
from sovereign_veritas.capability import Capability  # noqa: E402
from sovereign_veritas.evidence import Ledger, LedgerSink  # noqa: E402
from sovereign_veritas.file_ledger import FileLedger  # noqa: E402
from sovereign_veritas.idempotency import (IN_FLIGHT, UNKNOWN, FileReservations, MemoryReservations,  # noqa: E402
                                           ReservationRefused)
from sovereign_veritas.interfaces.contracts import ActionProposal  # noqa: E402
from sovereign_veritas.runtime import RuntimeState  # noqa: E402
from sovereign_veritas.workflow import EvidenceWorkflow  # noqa: E402

SABOTAGE = "--sabotage" in sys.argv
TRIALS = 50


class TimeoutAfterEffect(xb.CountingExecutor):
    """Applies the effect, then loses the response, once (as in RK-1)."""

    def __init__(self, delay=0.0):
        super().__init__(delay=delay)
        self.timed_out = False

    def execute(self, action):
        result = super().execute(action)
        if not self.timed_out:
            self.timed_out = True
            raise TimeoutError("response lost after the effect was applied")
        return result


class NonAtomicReservations(MemoryReservations):
    """SABOTAGE ONLY: check, then sleep, then write, with no lock across the gap."""

    def reserve(self, key, lease_s=30.0):
        if key in self._entries:
            raise ReservationRefused(f"idempotency key {key!r} exists: refused before execution")
        time.sleep(0.005)
        self._entries[key] = {"state": IN_FLIGHT, "lease_expires": time.time() + lease_s,
                              "history": [{"at": time.time(), "to": IN_FLIGHT}]}


def wf(sink, ex, store):
    return EvidenceWorkflow(sensor=xb.Sensor(), predictor=xb.Predictor(), verifier=xb.Verifier(),
                            executor=ex, evidence_sink=sink, reservations=store)


def run(w, rid, key):
    return w.run(record_id=rid, input_digest="abc", capability=Capability("read_only", True, ("fresh",)),
                 runtime=RuntimeState(platform="probe", python_version=sys.version.split()[0]),
                 action=ActionProposal(capability="read_only", requested="read", parameters={"t": 1}),
                 metadata={"fresh": True}, idempotency_key=key)


def refused(e):
    return e is not None and "refused before execution" in e


def statuses(sink):
    return [(r.metadata or {}).get("execution_status") for r in sink.ledger.all()]


def main():
    out, held = {}, {}
    with tempfile.TemporaryDirectory() as tmp:
        # A1 same key, same record_id
        ex, sink, st = TimeoutAfterEffect(), LedgerSink(Ledger()), MemoryReservations()
        e1 = xb.attempt(lambda: run(wf(sink, ex, st), "a1", "K-a1"))
        e2 = xb.attempt(lambda: run(wf(sink, ex, st), "a1", "K-a1"))
        out["A1"] = dict(effects=ex.effects, records=len(sink.ledger.all()), retry=e2, statuses=statuses(sink),
                         key_state=st.state("K-a1"), first=e1)
        held["R1"] = ex.effects == 1 and refused(e2) and statuses(sink) == ["UNKNOWN"] and st.state("K-a1") == UNKNOWN

        # A2 fresh record_id, same key
        ex, sink, st = TimeoutAfterEffect(), LedgerSink(Ledger()), MemoryReservations()
        xb.attempt(lambda: run(wf(sink, ex, st), "a2-first", "K-a2"))
        e2 = xb.attempt(lambda: run(wf(sink, ex, st), "a2-retry", "K-a2"))
        out["A2"] = dict(effects=ex.effects, records=len(sink.ledger.all()), retry=e2)
        held["R2"] = ex.effects == 1 and refused(e2)

        # A3 fresh record_id and fresh key
        ex, sink, st = TimeoutAfterEffect(), LedgerSink(Ledger()), MemoryReservations()
        xb.attempt(lambda: run(wf(sink, ex, st), "a3-first", "K-a3-1"))
        e2 = xb.attempt(lambda: run(wf(sink, ex, st), "a3-retry", "K-a3-2"))
        out["A3"] = dict(effects=ex.effects, records=len(sink.ledger.all()), retry=e2)
        held["R3"] = ex.effects == 2 and e2 is None

        # A4 across processes: file store + file ledger rebuilt from disk
        ldir, rdir = os.path.join(tmp, "a4.jsonl"), os.path.join(tmp, "a4res")
        ex = TimeoutAfterEffect()
        xb.attempt(lambda: run(wf(LedgerSink(FileLedger(ldir)), ex, FileReservations(rdir)), "a4-first", "K-a4"))
        e2 = xb.attempt(lambda: run(wf(LedgerSink(FileLedger(ldir)), ex, FileReservations(rdir)), "a4-retry", "K-a4"))
        out["A4"] = dict(effects=ex.effects, retry=e2, key_state=FileReservations(rdir).state("K-a4"))
        held["R4"] = ex.effects == 1 and refused(e2)

        # A5 race: two threads, same record_id, same key, 50 trials; memory store and two file-store objects
        def race(make_stores):
            doubles = 0
            for i in range(TRIALS):
                ex, sink = xb.CountingExecutor(delay=0.01), LedgerSink(Ledger())
                stores = make_stores(i)
                ts = [threading.Thread(target=lambda s=s: xb.attempt(lambda: run(wf(sink, ex, s), "race", f"K-race-{i}")))
                      for s in stores]
                for t in ts:
                    t.start()
                for t in ts:
                    t.join()
                doubles += ex.effects >= 2
            return doubles

        def mem(i):
            s = NonAtomicReservations() if SABOTAGE else MemoryReservations()
            return [s, s]

        def files(i):
            d = os.path.join(tmp, f"race{i}")
            return [FileReservations(d), FileReservations(d)]

        d_mem, d_file = race(mem), race(files)
        out["A5"] = dict(doubled_trials_memory=f"{d_mem} of {TRIALS}", doubled_trials_file=f"{d_file} of {TRIALS}",
                         memory_store="NON-ATOMIC (sabotage)" if SABOTAGE else "MemoryReservations")
        held["R5"] = d_mem == 0 and d_file == 0

        # A6 X5: effect succeeds, record write fails; retry same key through a working sink
        ex, st = xb.CountingExecutor(), MemoryReservations()
        e1 = xb.attempt(lambda: run(wf(xb.BrokenSink(), ex, st), "a6", "K-a6"))
        good = LedgerSink(Ledger())
        e2 = xb.attempt(lambda: run(wf(good, ex, st), "a6-retry", "K-a6"))
        out["A6"] = dict(effects=ex.effects, records=len(good.ledger.all()), first=e1, retry=e2,
                         key_state=st.state("K-a6"))
        held["R6"] = ex.effects == 1 and refused(e2) and len(good.ledger.all()) == 0

        # A7 lease expired (crashed holder), A8 lease live
        ex, sink, st = xb.CountingExecutor(), LedgerSink(Ledger()), MemoryReservations()
        st.reserve("K-a7", lease_s=0)
        e7 = xb.attempt(lambda: run(wf(sink, ex, st), "a7", "K-a7"))
        out["A7"] = dict(effects=ex.effects, retry=e7, key_state=st.state("K-a7"))
        held["R7"] = ex.effects == 0 and refused(e7) and st.state("K-a7") == UNKNOWN

        ex, sink, st = xb.CountingExecutor(), LedgerSink(Ledger()), MemoryReservations()
        st.reserve("K-a8", lease_s=60)
        e8 = xb.attempt(lambda: run(wf(sink, ex, st), "a8", "K-a8"))
        out["A8"] = dict(effects=ex.effects, retry=e8, key_state=st.state("K-a8"))
        held["R8"] = ex.effects == 0 and refused(e8) and st.state("K-a8") == IN_FLIGHT

        # A9 release after A1-style UNKNOWN, then run again
        ex, sink, st = TimeoutAfterEffect(), LedgerSink(Ledger()), MemoryReservations()
        xb.attempt(lambda: run(wf(sink, ex, st), "a9-first", "K-a9"))
        st.release("K-a9", by="operator", reason="checked downstream: effect absent")
        e9 = xb.attempt(lambda: run(wf(sink, ex, st), "a9-after-release", "K-a9"))
        hist = st.released_history("K-a9")
        out["A9"] = dict(effects=ex.effects, retry=e9, released_history=[h["to"] for h in hist[0]] if hist else None)
        held["R9"] = ex.effects == 2 and e9 is None and bool(hist) and hist[0][-1]["to"] == "RELEASED"

        # A10 key, no store
        ex, sink = xb.CountingExecutor(), LedgerSink(Ledger())
        e10 = xb.attempt(lambda: run(wf(sink, ex, None), "a10", "K-a10"))
        out["A10"] = dict(effects=ex.effects, error=e10)
        held["R10"] = ex.effects == 0 and refused(e10)

    for k, v in out.items():
        print(k, " ".join(f"{a}={b!r}" for a, b in v.items()))
    print("\nmode:", "SABOTAGE (non-atomic memory store in A5)" if SABOTAGE else "normal")
    for k, ok in held.items():
        print(f"  {k:4} {'HELD' if ok else 'NOT HELD'}")
    n = sum(held.values())
    print(f"VERDICT  {n} of {len(held)} as registered (R11: run --sabotage, expect exit 1; R12: regression, run separately)")
    return 0 if n == len(held) else 1


if __name__ == "__main__":
    sys.exit(main())
