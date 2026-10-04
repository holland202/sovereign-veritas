"""Outside the repo. Prediction (written before running):
E1: slow holder (>30 s default lease, not settable via run()) -> lease expires -> key UNKNOWN; an operator who checks
    downstream sees 0 effects, releases, retries -> 2 effects for one key; holder's late complete() overwrites the new
    holder's entry.
E2: store-level: a late complete() racing reserve()'s lease_expired write can lose COMPLETED (final UNKNOWN, no
    COMPLETED in history) in some trials.
E3: a torn (empty) reservation file is IN_FLIGHT forever and release() refuses it.
"""
import os, sys, tempfile, threading, time, json
ROOT = sys.argv[1]
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "tools"))
import execution_boundary_probe as xb
from sovereign_veritas.capability import Capability
from sovereign_veritas.evidence import Ledger, LedgerSink
from sovereign_veritas.idempotency import FileReservations, ReservationRefused, UNKNOWN, COMPLETED
from sovereign_veritas.interfaces.contracts import ActionProposal
from sovereign_veritas.runtime import RuntimeState
from sovereign_veritas.workflow import EvidenceWorkflow

def run(ex, d, rid, key):
    w = EvidenceWorkflow(sensor=xb.Sensor(), predictor=xb.Predictor(), verifier=xb.Verifier(),
                         executor=ex, evidence_sink=LedgerSink(Ledger()), reservations=FileReservations(d))
    return w.run(record_id=rid, input_digest="abc", capability=Capability("read_only", True, ("fresh",)),
                 runtime=RuntimeState(platform="probe", python_version=sys.version.split()[0]),
                 action=ActionProposal(capability="read_only", requested="read", parameters={"t": 1}),
                 metadata={"fresh": True}, idempotency_key=key)

class SlowThenEffect(xb.CountingExecutor):
    def __init__(self, shared, wait): super().__init__(); self.shared, self.wait = shared, wait
    def execute(self, action):
        time.sleep(self.wait)
        with self.shared._lock: self.shared.effects += 1
        return {"ok": True}

tmp = tempfile.mkdtemp()
if "E1" in sys.argv:
    d = os.path.join(tmp, "e1"); world = xb.CountingExecutor(); K = "K-e1"
    errs = {}
    A = threading.Thread(target=lambda: errs.__setitem__("A", xb.attempt(lambda: run(SlowThenEffect(world, 34), d, "a", K))))
    t0 = time.time(); A.start()
    time.sleep(31)
    errs["B"] = xb.attempt(lambda: run(SlowThenEffect(world, 0), d, "b", K))
    st = FileReservations(d)
    print(f"t={time.time()-t0:.1f}s  B retry: {errs['B']}")
    print(f"t={time.time()-t0:.1f}s  operator sees state={st.state(K)} downstream effects={world.effects} history={[h.get('to')+'/'+str(h.get('why')) for h in st.history(K)]}")
    st.release(K, by="operator", reason="checked downstream: effect absent")
    errs["C"] = xb.attempt(lambda: run(SlowThenEffect(world, 0), d, "c", K))
    print(f"t={time.time()-t0:.1f}s  C after release: {errs['C']} effects={world.effects}")
    A.join()
    print(f"t={time.time()-t0:.1f}s  A finished: {errs['A']}  EFFECTS FOR ONE KEY = {world.effects}")
    print("final state", st.state(K), "history", [h.get("to") for h in st.history(K)])

if "E2" in sys.argv:
    lost = 0; N = 300
    for i in range(N):
        d = os.path.join(tmp, f"e2-{i}"); K = f"K{i}"
        a = FileReservations(d); a.reserve(K, lease_s=0.01)
        time.sleep(0.011)
        stop = threading.Event()
        def hammer():
            b = FileReservations(d)
            while not stop.is_set():
                try: b.reserve(K)
                except ReservationRefused: pass
        hs = [threading.Thread(target=hammer) for _ in range(2)]
        for h in hs: h.start()
        time.sleep(0.002)
        a.complete(K)          # late holder reports success
        time.sleep(0.005); stop.set()
        for h in hs: h.join()
        hist = [h["to"] for h in a.history(K)]
        if COMPLETED not in hist and a.state(K) == UNKNOWN: lost += 1
    print(f"E2 COMPLETED lost (final UNKNOWN, no COMPLETED in history): {lost} of {N}")
    if lost:
        print("   example: releasable after success ->", end=" ")
        # find one and release
        for i in range(N):
            d = os.path.join(tmp, f"e2-{i}"); s = FileReservations(d); K=f"K{i}"
            if COMPLETED not in [h["to"] for h in s.history(K)]:
                s.release(K, by="op", reason="no completion recorded"); print("release() accepted; reserve() now:", end=" ")
                try: s.reserve(K); print("succeeds (key free)")
                except ReservationRefused as e: print(e)
                break

if "E3" in sys.argv:
    d = os.path.join(tmp, "e3"); s = FileReservations(d); K = "K-e3"
    open(s._path(K), "w").close()   # simulates crash between O_EXCL create and json.dump
    print("E3 torn file state:", s.state(K), "history:", s.history(K))
    try: s.release(K, by="op", reason="x"); print("released")
    except ValueError as e: print("E3 release:", e)
