#!/usr/bin/env python3
"""MP-1 probe (registration: docs/MP1_PREREG.md, commit b8e6918, pushed before this file existed).

One idempotency key, many separate OS processes, one FileReservations directory. Effects are counted from an
O_APPEND log written by the executor, outside the reservation store and the ledger.

  python tools/mp1_probe.py              exit 0 only if P1-P5 hold as registered
  python tools/mp1_probe.py --quick      fewer trials (smoke test only, not the registered run)
Internal: --worker DIR KEY EFFECT_LOG START_AT MODE [STORE]
Stdlib only. POSIX only (SIGKILL).
"""
import json
import os
import signal
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.dont_write_bytecode = True

TRIALS = {2: 200, 8: 100, 32: 30}


def worker(argv):
    d, key, log, start_at, mode = argv[:5]
    store_kind = argv[5] if len(argv) > 5 else "real"
    import execution_boundary_probe as xb
    from sovereign_veritas.capability import Capability
    from sovereign_veritas.evidence import Ledger, LedgerSink
    from sovereign_veritas.idempotency import FileReservations, ReservationRefused, IN_FLIGHT
    from sovereign_veritas.interfaces.contracts import ActionProposal
    from sovereign_veritas.runtime import RuntimeState
    from sovereign_veritas.workflow import EvidenceWorkflow

    class SabotageFileReservations(FileReservations):
        """SABOTAGE ONLY: exists() check, sleep, then create without O_EXCL."""

        def reserve(self, k, lease_s=30.0):
            if self._path(k).exists():
                raise ReservationRefused(f"idempotency key {k!r} exists: refused before execution")
            time.sleep(0.005)
            now = time.time()
            self._write(k, {"key": k, "state": IN_FLIGHT, "lease_expires": now + lease_s,
                            "history": [{"at": now, "to": IN_FLIGHT}]})

    class LogExecutor:
        def execute(self, action):
            if mode == "kill_before_effect":
                print("RESERVED", flush=True)
                time.sleep(60)
            fd = os.open(log, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
            os.write(fd, (str(os.getpid()) + "\n").encode())
            os.close(fd)
            if mode == "kill_after_effect":
                print("EFFECTED", flush=True)
                time.sleep(60)
            return {"ok": True}

    store = (SabotageFileReservations if store_kind == "sabotage" else FileReservations)(d)
    w = EvidenceWorkflow(sensor=xb.Sensor(), predictor=xb.Predictor(), verifier=xb.Verifier(),
                         executor=LogExecutor(), evidence_sink=LedgerSink(Ledger()), reservations=store)
    delay = float(start_at) - time.time()
    if delay > 0:
        time.sleep(delay)
    try:
        w.run(record_id=f"r-{os.getpid()}", input_digest="abc",
              capability=Capability("read_only", True, ("fresh",)),
              runtime=RuntimeState(platform="probe", python_version=sys.version.split()[0]),
              action=ActionProposal(capability="read_only", requested="read", parameters={"t": 1}),
              metadata={"fresh": True}, idempotency_key=key)
        print("RESULT ran", flush=True)
    except Exception as exc:  # recorded, not judged
        msg = f"{type(exc).__name__}: {exc}"
        print("RESULT " + ("refused" if "refused before execution" in msg else "error " + msg), flush=True)


def spawn(d, key, log, start_at, mode="normal", store="real"):
    return subprocess.Popen([sys.executable, os.path.abspath(__file__), "--worker", d, key, log, str(start_at),
                             mode, store], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=ROOT)


def effects(log):
    if not os.path.exists(log):
        return 0
    with open(log) as f:
        return sum(1 for line in f if line.strip())


def results(procs):
    out = []
    for p in procs:
        text, _ = p.communicate(timeout=120)
        line = [x for x in text.splitlines() if x.startswith("RESULT ")]
        out.append(line[-1][7:] if line else "error no result: " + text.strip()[-200:])
    return out


def race(tmp, n, trials, store):
    doubled, zero, errors = 0, 0, []
    for t in range(trials):
        d = os.path.join(tmp, f"{store}-{n}-{t}")
        log = d + ".effects"
        start_at = time.time() + 0.6 + 0.02 * n
        procs = [spawn(d, "K", log, start_at, store=store) for _ in range(n)]
        res = results(procs)
        e = effects(log)
        doubled += e > 1
        zero += e == 0
        errors += [r for r in res if r.startswith("error")]
    return {"n": n, "trials": trials, "doubled": doubled, "zero": zero, "errors": len(errors),
            "first_error": errors[0] if errors else None}


def wait_for(proc, marker, timeout=30):
    end = time.time() + timeout
    while time.time() < end:
        line = proc.stdout.readline()
        if marker in line:
            return True
        if not line and proc.poll() is not None:
            return False
    return False


def kill_case(tmp, mode):
    d = os.path.join(tmp, mode)
    log = d + ".effects"
    holder = spawn(d, "K", log, time.time(), mode)
    reached = wait_for(holder, "RESERVED" if mode == "kill_before_effect" else "EFFECTED")
    os.kill(holder.pid, signal.SIGKILL)
    holder.wait()
    procs = [spawn(d, "K", log, time.time() + 0.8) for _ in range(8)]
    res = results(procs)
    fresh = results([spawn(d, "K-fresh", log, time.time())])[0]
    return {"reached_marker": reached, "retries": res, "fresh": fresh,
            "effects_total": effects(log)}


def main():
    quick = "--quick" in sys.argv
    trials = {n: max(2, t // 20) for n, t in TRIALS.items()} if quick else TRIALS
    held, out = {}, {}
    with tempfile.TemporaryDirectory() as tmp:
        out["P1"] = [race(tmp, n, trials[n], "real") for n in (2, 8, 32)]
        held["P1"] = all(r["doubled"] == 0 and r["zero"] == 0 and r["errors"] == 0 for r in out["P1"])
        out["P2"] = race(tmp, 8, trials[8], "sabotage")
        held["P2"] = out["P2"]["doubled"] >= 1
        kb = kill_case(tmp, "kill_before_effect")
        ka = kill_case(tmp, "kill_after_effect")
        # the fresh-key control writes one effect into each log; subtract it for the same-key count
        kb["effects_same_key"] = kb["effects_total"] - (1 if kb["fresh"] == "ran" else 0)
        ka["effects_same_key"] = ka["effects_total"] - (1 if ka["fresh"] == "ran" else 0)
        out["P3"], out["P4"] = kb, ka
        held["P3"] = kb["reached_marker"] and kb["effects_same_key"] == 0 and kb["retries"] == ["refused"] * 8
        held["P4"] = ka["reached_marker"] and ka["effects_same_key"] == 1 and ka["retries"] == ["refused"] * 8
        held["P5"] = kb["fresh"] == "ran" and ka["fresh"] == "ran"
    for r in out["P1"]:
        print(f"P1 real     N={r['n']:<3} trials={r['trials']:<4} doubled={r['doubled']} zero={r['zero']} "
              f"errors={r['errors']}" + (f" first_error={r['first_error']}" if r["first_error"] else ""))
    r = out["P2"]
    print(f"P2 sabotage N={r['n']:<3} trials={r['trials']:<4} doubled={r['doubled']} zero={r['zero']} errors={r['errors']}")
    for k in ("P3", "P4"):
        c = out[k]
        print(f"{k} {'killed before effect' if k == 'P3' else 'killed after effect '}  marker={c['reached_marker']} "
              f"same-key effects={c['effects_same_key']} retries={sorted(set(c['retries']))}x{len(c['retries'])} "
              f"fresh-key={c['fresh']}")
    print()
    for k in ("P1", "P2", "P3", "P4", "P5"):
        print(f"  {k}  {'HELD' if held[k] else 'NOT HELD'}")
    n = sum(held.values())
    print(f"VERDICT  {n} of 5 as registered" + ("  (QUICK: smoke test, not the registered run)" if quick else ""))
    return 0 if n == 5 else 1


if __name__ == "__main__":
    if sys.argv[1:2] == ["--worker"]:
        worker(sys.argv[2:])
    else:
        sys.exit(main())
