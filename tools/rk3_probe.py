#!/usr/bin/env python3
"""RK-3 probe (registration: docs/RK3_PREREG.md, commit d688b2b, pushed before this file or the fix existed).

  python tools/rk3_probe.py              judges Q1-Q4 as registered; exit 0 only if all hold
  python tools/rk3_probe.py --sabotage   Q5: complete() ignores the holder token (today's behaviour); Q2 must fail, exit 1
Internal: --hammer MODULE_PATH DIR KEY UNTIL
Stdlib only, POSIX timing. Effects are counted at the executor, outside the store and the ledger.
"""
import glob
import importlib.util
import json
import os
import random
import subprocess
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.dont_write_bytecode = True
BASELINE = "1307da7"  # main before RK-3
TRIALS, HAMMERS, LEASE, JITTER = 300, 3, 0.15, 0.0005


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def hammer(argv):
    mod_path, d, key, until = argv[0], argv[1], argv[2], float(argv[3])
    mod = load(mod_path, "store_under_test")
    s = mod.FileReservations(d)
    while time.time() < until:
        try:
            s.reserve(key)
        except mod.ReservationRefused:
            pass


def lost_completed(mod_path, trials):
    """Q1/Q1c: complete() lands at lease expiry while separate processes call reserve() on the key."""
    mod = load(mod_path, f"store_{abs(hash(mod_path))}")
    tmp, lost = tempfile.mkdtemp(), 0
    for i in range(trials):
        d, k = os.path.join(tmp, f"t{i}"), f"K{i}"
        a = mod.FileReservations(d)
        a.reserve(k, lease_s=LEASE)
        t_exp = time.time() + LEASE
        hs = [subprocess.Popen([sys.executable, __file__, "--hammer", mod_path, d, k, str(t_exp + 0.05)])
              for _ in range(HAMMERS)]
        target = t_exp + random.uniform(-JITTER, JITTER)
        while time.time() < target:
            pass
        a.complete(k)  # as in results/rk3/independent_review/e2b.py
        for h in hs:
            h.wait()
        if mod.COMPLETED not in [h["to"] for h in a.history(k)] or a.state(k) == mod.UNKNOWN:
            lost += 1
    return lost


def workflow_case(lease_s, holder_s, check_at, sabotage):
    import execution_boundary_probe as xb
    from sovereign_veritas.capability import Capability
    from sovereign_veritas.evidence import Ledger, LedgerSink
    from sovereign_veritas.idempotency import FileReservations
    from sovereign_veritas.interfaces.contracts import ActionProposal
    from sovereign_veritas.runtime import RuntimeState
    from sovereign_veritas.workflow import EvidenceWorkflow

    if sabotage:
        real = FileReservations.complete
        FileReservations.complete = lambda self, key, token=None: real(self, key)  # today's behaviour: no token

    world = xb.CountingExecutor()

    class Slow:
        def __init__(self, wait):
            self.wait = wait

        def execute(self, action):
            time.sleep(self.wait)
            return world.execute(action)

    d = tempfile.mkdtemp()
    key = "K-rk3"

    def run(rid, wait):
        wf = EvidenceWorkflow(sensor=xb.Sensor(), predictor=xb.Predictor(), verifier=xb.Verifier(), executor=Slow(wait),
                              evidence_sink=LedgerSink(Ledger()), reservations=FileReservations(d))
        return wf.run(record_id=rid, input_digest="abc", capability=Capability("read_only", True, ("fresh",)),
                      runtime=RuntimeState(platform="probe", python_version=sys.version.split()[0]),
                      action=ActionProposal(capability="read_only", requested="read", parameters={"t": 1}),
                      metadata={"fresh": True}, idempotency_key=key, lease_s=lease_s)

    errs = {}
    a = threading.Thread(target=lambda: errs.__setitem__("A", xb.attempt(lambda: run("a", holder_s))))
    t0 = time.time()
    a.start()
    time.sleep(check_at)
    st = FileReservations(d)
    out = {"state_at_check": st.state(key), "effects_at_check": world.effects}
    try:
        st.release(key, by="operator", reason="checked downstream: effect absent")
        out["release"] = "accepted"
        errs["C"] = xb.attempt(lambda: run("c", 0))
    except ValueError as exc:
        out["release"] = f"refused: {exc}"
    a.join()
    if sabotage:
        FileReservations.complete = real
    released = sorted(glob.glob(os.path.join(d, "*.released-*.json")))
    out.update(effects=world.effects, final_state=st.state(key), errors={k: v for k, v in errs.items() if v},
               history=[h["to"] for h in st.history(key)], late=st.late_events(key),
               a_token=json.load(open(released[0]))["token"] if released else None, seconds=round(time.time() - t0, 1))
    return out


def run_cmd(args):
    p = subprocess.run([sys.executable] + args, cwd=ROOT, capture_output=True, text=True)
    lines = [l for l in (p.stdout + p.stderr).strip().splitlines() if l.strip()]
    return p.returncode, lines[-1] if lines else ""


def main():
    if sys.argv[1:2] == ["--hammer"]:
        hammer(sys.argv[2:])
        return 0
    sabotage = "--sabotage" in sys.argv
    v = {}
    if not sabotage:
        old = os.path.join(tempfile.mkdtemp(), "idempotency_baseline.py")
        p = subprocess.run(["git", "show", f"{BASELINE}:sovereign_veritas/idempotency.py"], cwd=ROOT,
                           capture_output=True, text=True)
        if p.returncode != 0:
            print("COULD NOT RUN: git show", BASELINE, p.stderr.strip())
            return 2
        open(old, "w").write(p.stdout)
        new = os.path.join(ROOT, "sovereign_veritas", "idempotency.py")
        lost_new = lost_completed(new, TRIALS)
        lost_old = lost_completed(old, TRIALS)
        print(f"Q1   changed store   trials={TRIALS} hammers={HAMMERS} COMPLETED lost={lost_new}")
        print(f"Q1c  {BASELINE} store  trials={TRIALS} hammers={HAMMERS} COMPLETED lost={lost_old}")
        v["Q1"], v["Q1c"] = lost_new == 0, lost_old >= 1

    q2 = workflow_case(lease_s=1, holder_s=2, check_at=1.2, sabotage=sabotage)
    print(f"Q2   lease 1 s, holder 2 s, release at 1.2 s: {json.dumps(q2, sort_keys=True)}")
    late = q2["late"]
    v["Q2"] = (q2["effects"] == 2 and q2["history"] == ["IN_FLIGHT", "COMPLETED"] and len(late) == 1
               and late[0]["event"] == "late_complete" and late[0]["late_token"] == q2["a_token"])

    if not sabotage:
        q3 = workflow_case(lease_s=5, holder_s=2, check_at=1.0, sabotage=False)
        print(f"Q3   lease 5 s, holder 2 s, release at 1.0 s: {json.dumps(q3, sort_keys=True)}")
        v["Q3"] = (q3["state_at_check"] == "IN_FLIGHT" and q3["release"].startswith("refused")
                   and q3["effects"] == 1 and q3["final_state"] == "COMPLETED")
        reg = {"rk2": run_cmd(["tools/rk2_probe.py"]), "rk2 --sabotage": run_cmd(["tools/rk2_probe.py", "--sabotage"]),
               "mp1": run_cmd(["tools/mp1_probe.py"]), "pytest": run_cmd(["-m", "pytest", "-q"])}
        for name, (code, last) in reg.items():
            print(f"Q4   {name:<15} exit {code} | {last}")
        v["Q4"] = ([reg[k][0] for k in ("rk2", "rk2 --sabotage", "mp1", "pytest")] == [0, 1, 0, 0]
                   and "10 of 10" in reg["rk2"][1] and "5 of 5" in reg["mp1"][1])

    print()
    for k, ok in v.items():
        print(f"  {k:<4} {'HELD' if ok else 'REFUTED'}")
    if sabotage:
        print("mode: SABOTAGE (complete() ignores the holder token); Q5 holds if Q2 is REFUTED and the exit is 1")
    else:
        print("  Q5   run --sabotage, expect Q2 REFUTED and exit 1")
    print(f"VERDICT  {sum(v.values())} of {len(v)} {'as registered' if not sabotage else 'under sabotage'}")
    return 0 if all(v.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
