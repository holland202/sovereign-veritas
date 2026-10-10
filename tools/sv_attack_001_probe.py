#!/usr/bin/env python3
"""SV-ATTACK-001 probe: can an ALLOW cover an action whose parameters changed after authorization?

Registered in docs/SV_ATTACK_001_PREREG.md (6a524e5) and docs/SV_ATTACK_001_AMENDMENT1.md (a80e6b5),
both committed before this file existed. Written by Claude (Opus 5.5) at Chad Holland's direction.
Not reviewed line by line by Chad. It changes no file under sovereign_veritas/ or tools/; the only
mechanism it adds is a harness-side wrapper around a Gate INSTANCE that calls the real, unmodified
Gate.evaluate() and returns its decision unchanged, then (mutating cases only) changes the shared
parameters dict. That is a deterministic stand-in for a concurrent writer (Amendment 1, M2).

Inert by construction (Amendment 1, M5): case parameters are strings and numbers compared by hash.
No path taken from a case parameter is ever opened. Layer A's executor only stores a deep copy of what
it was given. Layer B's commands go only to FakeVehicle (tools/vehicle_action.py), an in-memory list.
The only files written are under the output directory (results, packages, and a per-case HOME
directory that vehicle_action.py writes its package into).

  python -I tools/sv_attack_001_probe.py --label run1        # writes results/sv_attack_001/run1/
Runs only with the owner's authorization, which must state the number of executions (Amendment 1, M1).
Refuses to overwrite an existing output directory: every run's evidence is kept.
Exit 0 = the run completed (verdicts are in the output, whatever they are) | 3 = precondition failed
(target hash mismatch or comparator self-test failed): nothing was attacked, run is INCONCLUSIVE.
"""
import argparse, contextlib, copy, hashlib, importlib.util, io, json, os, platform, subprocess, sys, traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.dont_write_bytecode = True

TARGETS = {  # docs/SV_ATTACK_001_PREREG.md, table "Target (exact bytes)", main 438e6d5
    "sovereign_veritas/workflow.py": "dc845506e704ef9c305128b4272031dc67c60aafbc10b278f6b32d273e34a358",
    "sovereign_veritas/decision.py": "84a4a59a4692973b9440e66fdcafdaa0e57d18e5f1e284ab04a9ccacd1893462",
    "sovereign_veritas/interfaces/contracts.py": "21183bd8cab0e39bb670c5e7248270a192b4f127cf0265e65c2ff3d10e8c03b3",
    "sovereign_veritas/evidence.py": "6eb33ba5d013f54658b6422042340563bef053c39d972543d232c3ccf0554ace",
    "sovereign_veritas/idempotency.py": "b8e92c6f5da51c2569dd9e8f7024ca166829d2fd17183037047946ebbdbbdd3a",
    "sovereign_veritas/package.py": "960922275727eff2862c5dce60852fdd2787dafcdd87f0ba84c3a45a73c2aada",
    "tools/vehicle_action.py": "408b3d5b1a58087805cda1b586b3452f06af7ed53dc3c6d59986c5ba3a00b657",
    "tools/verify_package.py": "fc952616158c3ab6d7749dd9e27ed9bf58b76f12a6eaa6a02aabdeac224d7746",
}
LOG = []


def say(line=""):
    print(line)
    LOG.append(line)


def sha_file(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def phash(params):
    return hashlib.sha256(canon(params).encode("utf-8")).hexdigest()


def diverges(authorized, executed):
    """The comparator. Divergence = executed parameters differ from the authorized ones (by hash)."""
    return phash(authorized) != phash(executed)


def thaw(v):
    if isinstance(v, dict) or hasattr(v, "items"):
        return {k: thaw(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [thaw(x) for x in v]
    return v


# ---- harness pieces (no repository code is modified) ------------------------------------------------
from sovereign_veritas.capability import Capability  # noqa: E402
from sovereign_veritas.decision import Gate  # noqa: E402
from sovereign_veritas.evidence import Ledger, LedgerSink  # noqa: E402
from sovereign_veritas.idempotency import MemoryReservations, ReservationRefused  # noqa: E402
from sovereign_veritas.interfaces.contracts import ActionProposal, Prediction  # noqa: E402
from sovereign_veritas.runtime import RuntimeState  # noqa: E402
from sovereign_veritas.workflow import EvidenceWorkflow  # noqa: E402


class HookGate(Gate):
    """Calls the real Gate.evaluate and returns its decision unchanged; then optionally mutates."""

    def __init__(self, order, mutate=None):
        self.order, self.mutate, self.mutations = order, mutate, 0

    def evaluate(self, *args, **kwargs):
        decision = super().evaluate(*args, **kwargs)
        self.order.append("evaluate_returned")
        if self.mutate is not None:
            self.mutate()
            self.mutations += 1
            self.order.append("mutated")
        return decision


class RecordingExecutor:
    """Layer A executor: stores a deep copy of the parameters it receives. Touches nothing else."""

    def __init__(self, order):
        self.order, self.received = order, []

    def execute(self, action):
        self.order.append("execute")
        self.received.append(copy.deepcopy(dict(action.parameters)))
        return {"recorded": True}


class Q:
    def observe(self):
        return {"probe": "sv-attack-001"}


class P:
    def predict(self, observation):
        return Prediction(value=1, uncertainty=0.0, model_id="sv-attack-001-fixed")


class V:
    def verify(self, observation, prediction):
        return {"status": "PASS"}


LEGIT = {"target": "sandbox/a.txt", "mode": "append"}      # inert strings, never opened
MODIFIED = {"target": "/etc/passwd", "mode": "overwrite"}  # inert strings, never opened


def kernel_workflow(order, mutate=None, reservations=None):
    executor = RecordingExecutor(order)
    gate = HookGate(order, mutate)
    wf = EvidenceWorkflow(sensor=Q(), predictor=P(), verifier=V(), executor=executor,
                          evidence_sink=LedgerSink(Ledger()), gate=gate, reservations=reservations)
    return wf, executor, gate


def kernel_run(wf, record_id, params, key=None):
    action = ActionProposal("write_marker", "write", params)
    return wf.run(record_id=record_id, input_digest=phash(params),
                  capability=Capability("write_marker", authorized=True),
                  runtime=RuntimeState(platform="probe", python_version=platform.python_version()),
                  action=action, policy={"allow_only": ["write"]}, idempotency_key=key)


def case_record(cid, result, executor_received, before, extra=None):
    auth = thaw(result.evidence.to_dict()["action"]["parameters"]) if result is not None else None
    executed = executor_received[before:] if executor_received is not None else []
    rec = {"case": cid,
           "decision": result.decision.decision if result is not None else None,
           "reasons": list(result.decision.reasons) if result is not None else None,
           "authorized_params": auth, "authorized_sha256": phash(auth) if auth is not None else None,
           "executed_params": executed, "executed_sha256": [phash(e) for e in executed],
           "effects": len(executed),
           "record_digest": result.evidence.record_digest if result is not None else None,
           "divergence": bool(executed) and auth is not None and any(diverges(auth, e) for e in executed)}
    rec.update(extra or {})
    return rec


# ---- layer A ----------------------------------------------------------------------------------------
def layer_a():
    out = {}
    # A0 (also control C1 for layer A): legitimate action through the wrapper, mutation off.
    order = []
    wf, ex, gate = kernel_workflow(order)
    r = kernel_run(wf, "A0", dict(LEGIT))
    out["A0"] = case_record("A0", r, ex.received, 0, {"order": list(order), "mutations": gate.mutations})

    # A2: replay A0's record_id with modified parameters on the same workflow/ledger.
    before = len(ex.received)
    try:
        kernel_run(wf, "A0", dict(MODIFIED))
        out["A2"] = {"case": "A2", "refused_before_execution": False, "error": None,
                     "new_effects": len(ex.received) - before}
    except Exception as e:  # expected: duplicate record_id refused
        out["A2"] = {"case": "A2", "refused_before_execution": len(ex.received) == before,
                     "error": f"{type(e).__name__}: {e}", "new_effects": len(ex.received) - before}

    # O1 (observation): fresh record_id, no key, modified parameters -> a fresh decision.
    before = len(ex.received)
    r = kernel_run(wf, "O1", dict(MODIFIED))
    out["O1"] = case_record("O1", r, ex.received, before)

    # A3: idempotency key reused with a new record_id and modified parameters.
    order3 = []
    wf3, ex3, _ = kernel_workflow(order3, reservations=MemoryReservations())
    first = kernel_run(wf3, "A3-1", dict(LEGIT), key="k1")
    before = len(ex3.received)
    try:
        kernel_run(wf3, "A3-2", dict(MODIFIED), key="k1")
        out["A3"] = {"case": "A3", "first_decision": first.decision.decision, "refused_before_execution": False,
                     "error": None, "new_effects": len(ex3.received) - before}
    except Exception as e:  # expected: ReservationRefused
        out["A3"] = {"case": "A3", "first_decision": first.decision.decision,
                     "refused_before_execution": len(ex3.received) == before,
                     "error": f"{type(e).__name__}: {e}", "reservation_refused": isinstance(e, ReservationRefused),
                     "new_effects": len(ex3.received) - before}

    # A1: legitimate action; after the Gate decides, the shared dict becomes MODIFIED.
    order1 = []
    params = dict(LEGIT)

    def swap():
        params.clear()
        params.update(MODIFIED)

    wf1, ex1, gate1 = kernel_workflow(order1, mutate=swap)
    try:
        r = kernel_run(wf1, "A1", params)
        out["A1"] = case_record("A1", r, ex1.received, 0, {"order": list(order1), "mutations": gate1.mutations})
    except Exception as e:
        out["A1"] = {"case": "A1", "crash": f"{type(e).__name__}: {e}", "order": list(order1),
                     "mutations": gate1.mutations, "effects": len(ex1.received), "divergence": None}
    return out


# ---- layer B ----------------------------------------------------------------------------------------
def load_vehicle_action():
    spec = importlib.util.spec_from_file_location("sv_vehicle_action", os.path.join(ROOT, "tools", "vehicle_action.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def make_swap(params, latlon):
    """The B1 mutation: move the goto target (an in-memory dict) to latlon. Inert: FakeVehicle only."""
    def swap():
        params["lat_e7"], params["lon_e7"] = latlon
    return swap


def vehicle_case(va, cid, home, mutate_to_north_m=None):
    """Run vehicle_action.main() on fake:healthy_air with a hooked workflow; return what happened."""
    seen = {"order": [], "executed": [], "result": None, "mutations": 0, "commands": None}

    class HookedWorkflow(EvidenceWorkflow):
        def run(self, **kw):
            action = kw.get("action")
            hook = None
            if mutate_to_north_m is not None and action is not None:
                fence_lat = int(round(35.3632 * 1e7))  # vehicle_action.py default --fence-lat
                fence_lon = int(round(-96.9270 * 1e7))  # vehicle_action.py default --fence-lon
                hook = make_swap(action.parameters, va.offset(fence_lat, fence_lon, mutate_to_north_m, 0.0))
            self.gate = HookGate(seen["order"], hook)
            inner = self.executor

            class Proxy:
                def execute(self_, act):
                    seen["order"].append("execute")
                    seen["executed"].append(copy.deepcopy(dict(act.parameters)))
                    return inner.execute(act)

            self.executor = Proxy()
            res = super().run(**kw)
            seen["result"], seen["mutations"] = res, self.gate.mutations
            seen["commands"] = list(getattr(inner.vehicle, "commands", []))
            return res

    os.makedirs(home)
    old_home, old_argv, old_wf = os.environ.get("HOME"), sys.argv, va.EvidenceWorkflow
    os.environ["HOME"] = home
    sys.argv = ["vehicle_action.py", "--link", "fake:healthy_air", "--action", "goto", "--north", "100",
                "--alt", "20", "--thermal-status", "normal"]
    va.EvidenceWorkflow = HookedWorkflow
    stdout, crash = io.StringIO(), None
    try:
        with contextlib.redirect_stdout(stdout):
            va.main()
    except SystemExit as e:
        crash = f"SystemExit {e.code}"
    except Exception as e:
        crash = f"{type(e).__name__}: {e}\n{traceback.format_exc()[-400:]}"
    finally:
        va.EvidenceWorkflow = old_wf
        sys.argv = old_argv
        if old_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = old_home
    pkgs = sorted(f for f in os.listdir(home) if f.startswith("sv_package_") and f.endswith(".json"))
    rec = case_record(cid, seen["result"], seen["executed"], 0,
                      {"order": seen["order"], "mutations": seen["mutations"], "commands_sent": seen["commands"],
                       "crash": crash, "stdout": stdout.getvalue().splitlines(),
                       "package": os.path.join(home, pkgs[-1]) if pkgs else None})
    return rec


def verify(path):
    p = subprocess.run([sys.executable, "-I", os.path.join(ROOT, "tools", "verify_package.py"), path],
                       capture_output=True, text=True, timeout=120)
    return {"exit": p.returncode, "stdout": p.stdout.splitlines(), "stderr": p.stderr.splitlines()[-5:]}


def layer_b(out_dir):
    va = load_vehicle_action()
    res = {"B0": vehicle_case(va, "B0", os.path.join(out_dir, "home_B0")),
           "B1": vehicle_case(va, "B1", os.path.join(out_dir, "home_B1"), mutate_to_north_m=500.0)}
    for cid in ("B0", "B1"):
        pkg = res[cid]["package"]
        res[cid]["package_sha256"] = sha_file(pkg) if pkg else None
        res[cid]["verify"] = verify(pkg) if pkg else None
    # B2 (control C4): B0's package with the decision record's parameters edited, no digest recomputed.
    b2 = {"case": "B2", "source": res["B0"]["package"]}
    if res["B0"]["package"]:
        with open(res["B0"]["package"], encoding="utf-8") as fh:
            pkg = json.load(fh)
        pkg["provenance"]["chain"][-1]["record"]["action"]["parameters"]["alt_m"] = 99
        path = os.path.join(out_dir, "packages", "B2_tampered.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(canon(pkg))
        b2.update(package=path, package_sha256=sha_file(path), verify=verify(path))
    res["B2"] = b2
    return res


# ---- verdicts (docs/SV_ATTACK_001_PREREG.md "Verdict rules", as amended) ---------------------------
def verdicts(pre_ok, a, b):
    v = {}
    c1 = (a["A0"]["decision"] == "ALLOW" and a["A0"]["effects"] == 1 and not a["A0"]["divergence"]
          and b["B0"]["decision"] == "ALLOW" and b["B0"]["effects"] == 1 and not b["B0"]["divergence"])
    c2 = all(x.get("mutations") == 1 and x.get("order", [])[:3] == ["evaluate_returned", "mutated", "execute"]
             for x in (a["A1"], b["B1"]))
    crashed = bool(a["A1"].get("crash")) or bool(b["B1"].get("crash"))
    v["C1"], v["C2"] = c1, c2
    if not (pre_ok and c1 and c2) or crashed:
        v["Q1"] = "INCONCLUSIVE"
    elif a["A1"]["divergence"] or b["B1"]["divergence"]:
        v["Q1"] = "FAIL"
    else:
        v["Q1"] = "PASS"
    a2, a3 = a["A2"], a["A3"]
    if not pre_ok:
        v["Q2"] = "INCONCLUSIVE"
    elif a2["new_effects"] > 0 or a3["new_effects"] > 0:
        v["Q2"] = "FAIL"
    elif a2["refused_before_execution"] and a3["refused_before_execution"]:
        v["Q2"] = "PASS"
    else:
        v["Q2"] = "INCONCLUSIVE"
    c4 = bool(b["B2"].get("verify")) and b["B2"]["verify"]["exit"] != 0
    v["C4"] = c4
    if not pre_ok or not c4 or not b["B1"].get("verify"):
        v["Q3"] = "INCONCLUSIVE"
    else:
        v["Q3"] = "FAIL" if b["B1"]["verify"]["exit"] == 0 else "PASS"
    v["O1"] = f"observation: {a['O1']['decision']}, {a['O1']['effects']} effect(s)"
    return v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True, help="run1, or run2 only if the owner authorized two executions")
    ap.add_argument("--out", default=os.path.join(ROOT, "results", "sv_attack_001"))
    args = ap.parse_args()
    out_dir = os.path.join(args.out, args.label)
    if os.path.exists(out_dir):
        print(f"REFUSED: {out_dir} exists; every run's evidence is kept, choose a new label")
        return 3
    os.makedirs(out_dir)

    say(f"SV-ATTACK-001 probe  label={args.label}  python={platform.python_version()}  platform={platform.platform()}")
    me = os.path.abspath(__file__)
    say(f"probe sha256 {sha_file(me)}")
    hashes, pre_ok = {}, True
    for rel, want in TARGETS.items():
        got = sha_file(os.path.join(ROOT, rel))
        hashes[rel] = got
        ok = got == want
        pre_ok &= ok
        say(f"{'ok      ' if ok else 'MISMATCH'} {got}  {rel}")
    c3 = (not diverges(LEGIT, dict(LEGIT))) and diverges({"a": {"b": 1}}, {"a": {"b": 2}})
    say(f"C3 comparator self-test: {'ok' if c3 else 'FAILED'}")
    pre_ok &= c3
    record = {"label": args.label, "python": platform.python_version(), "platform": platform.platform(),
              "probe_sha256": sha_file(me), "target_hashes": hashes, "C3": c3}
    if not pre_ok:
        say("PRECONDITION FAILED: nothing attacked. Q1 Q2 Q3 INCONCLUSIVE")
        record["verdicts"] = {"Q1": "INCONCLUSIVE", "Q2": "INCONCLUSIVE", "Q3": "INCONCLUSIVE"}
        finish(out_dir, record)
        return 3

    try:
        a = layer_a()
        b = layer_b(out_dir)
    except Exception as e:  # a harness crash is kept as evidence and makes every question INCONCLUSIVE
        say(f"HARNESS CRASH: {type(e).__name__}: {e}")
        LOG.extend(traceback.format_exc().splitlines())
        record["harness_crash"] = traceback.format_exc()
        record["verdicts"] = {"Q1": "INCONCLUSIVE", "Q2": "INCONCLUSIVE", "Q3": "INCONCLUSIVE"}
        say("VERDICT  Q1 INCONCLUSIVE  |  Q2 INCONCLUSIVE  |  Q3 INCONCLUSIVE  (harness crash)")
        finish(out_dir, record)
        return 3
    record.update(layer_a=a, layer_b=b)
    v = verdicts(pre_ok, a, b)
    record["verdicts"] = v

    say("")
    for cid in ("A0", "A1", "O1"):
        x = a[cid]
        say(f"{cid}  {x.get('decision')}  effects {x.get('effects')}  divergence {x.get('divergence')}  "
            f"authorized {x.get('authorized_params')}  executed {x.get('executed_params')}"
            + (f"  order {x.get('order')}" if 'order' in x else "") + (f"  CRASH {x['crash']}" if x.get('crash') else ""))
    for cid in ("A2", "A3"):
        x = a[cid]
        say(f"{cid}  refused_before_execution {x['refused_before_execution']}  new_effects {x['new_effects']}  {x['error']}")
    for cid in ("B0", "B1"):
        x = b[cid]
        say(f"{cid}  {x.get('decision')}  effects {x.get('effects')}  divergence {x.get('divergence')}  "
            f"authorized {x.get('authorized_params')}  executed {x.get('executed_params')}  order {x.get('order')}"
            + (f"  CRASH {x['crash']}" if x.get('crash') else ""))
        say(f"{cid}  commands_sent {x.get('commands_sent')}")
        if x.get("verify"):
            say(f"{cid}  verify_package exit {x['verify']['exit']}  {x['verify']['stdout'][-1] if x['verify']['stdout'] else ''}")
    if b["B2"].get("verify"):
        say(f"B2  verify_package exit {b['B2']['verify']['exit']}  {b['B2']['verify']['stdout'][-1] if b['B2']['verify']['stdout'] else ''}")
    say("")
    say(f"controls  C1 {v['C1']}  C2 {v['C2']}  C3 {c3}  C4 {v['C4']}")
    say(f"VERDICT  Q1 (execution boundary) {v['Q1']}  |  Q2 (replay) {v['Q2']}  |  Q3 (offline verifier) {v['Q3']}")
    say(f"         {v['O1']} (not a verdict)")
    say("Q1 is a deterministic race simulation: it shows the window, not how likely a real writer hits it (M2).")
    finish(out_dir, record)
    return 0


def finish(out_dir, record):
    pk = os.path.join(out_dir, "packages")
    os.makedirs(pk, exist_ok=True)
    for cid in ("B0", "B1"):
        src = (record.get("layer_b") or {}).get(cid, {}).get("package")
        if src:
            with open(src, "rb") as fi, open(os.path.join(pk, f"{cid}.json"), "wb") as fo:
                fo.write(fi.read())
    with open(os.path.join(out_dir, "run.json"), "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=1, sort_keys=True, default=str)
    with open(os.path.join(out_dir, "run.log"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(LOG) + "\n")
    sums = []
    for base, _, files in sorted(os.walk(out_dir)):
        for f in sorted(files):
            if f == "SHA256SUMS":
                continue
            p = os.path.join(base, f)
            sums.append(f"{sha_file(p)}  {os.path.relpath(p, out_dir)}")
    with open(os.path.join(out_dir, "SHA256SUMS"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(sums) + "\n")
    print(f"evidence: {out_dir}  (SHA256SUMS sha256 {sha_file(os.path.join(out_dir, 'SHA256SUMS'))})")


if __name__ == "__main__":
    sys.exit(main())
