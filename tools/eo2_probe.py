#!/usr/bin/env python3
"""EO-2 harness (registration docs/EO2_PREREG.md): which checker catches which attack on the EO-1 gap?

  python tools/eo2_probe.py [--sabotage] [--json PATH]

Each run uses the real EvidenceWorkflow on a temporary copy of the repository (the M1 mutant on its own copy).
The target is a file-backed valve; the observer reads it before and after the run and never calls the executor.
--sabotage replaces the observer with a blind one (after = before): P3 must be REFUTED and the exit code 1.
"""
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
RECORDED = (("P1", "P2", "P5", "P6", "P7"),
            "3f7a451075292af5d194e2677250f37c9614ca2b51d1489136d591de5505ff32")  # first registered run, 2026-11-07

ANCHOR = '        if decision.decision == "ALLOW":\n            if action is None:'
MUTANT = ('        if decision.decision != "ALLOW" and action is not None:\n'
          '            self.executor.execute(action)  # EO-1 MUTANT M1\n\n')
SPEC = {"open_valve": {"V1": "open"}, "close_valve": {"V1": "closed"}}

# case: (repo, decision, executor, initial V1)
CASES = {
    "C1": ("clean", "ALLOW", "honest", "closed"),
    "C2": ("clean", "REFUSE", "honest", "closed"),
    "C3": ("clean", "DEFER", "honest", "closed"),
    "C4": ("clean", "ALLOW", "honest", "open"),
    "A1": ("mutant", "REFUSE", "honest", "closed"),
    "A2": ("mutant", "DEFER", "honest", "closed"),
    "A3": ("clean", "ALLOW", "noop", "closed"),
    "A4": ("clean", "ALLOW", "wrong", "open"),
    "A5": ("clean", "ALLOW", "forge", "closed"),
}


# ---------------------------------------------------------------- child side: runs inside a repo copy
def child(case, decision, kind, initial, work):
    sys.path.insert(0, os.getcwd())
    from sovereign_veritas.capability import Capability
    from sovereign_veritas.evidence import Ledger, LedgerSink
    from sovereign_veritas.interfaces.contracts import ActionProposal, Prediction
    from sovereign_veritas.runtime import RuntimeState
    from sovereign_veritas.workflow import EvidenceWorkflow

    work = pathlib.Path(work)

    class Target:  # the real state; changed only by apply()
        path = work / "valve.json"

        def read(self):
            return json.loads(self.path.read_text(encoding="utf-8"))

        def apply(self, requested):
            self.path.write_text(json.dumps(SPEC[requested]), encoding="utf-8")

    view = work / "executor_view.json"  # A7: a view the executor can write
    target = Target()
    target.path.write_text(json.dumps({"V1": initial}), encoding="utf-8")
    view.write_text(json.dumps({"V1": initial}), encoding="utf-8")

    class Executor:
        def execute(self, action):
            if kind == "honest":
                target.apply(action.requested)
                return {"receipt": {"requested": action.requested, "target": "V1", "state": target.read()["V1"]}}
            if kind == "wrong":
                target.apply("close_valve")
                return {"receipt": {"requested": "close_valve", "target": "V1", "state": target.read()["V1"]}}
            if kind == "forge":
                view.write_text(json.dumps({"V1": "open"}), encoding="utf-8")
                return {"receipt": {"requested": action.requested, "target": "V1", "state": "open"}}
            return {"executed": action.requested}  # noop: returns normally, no receipt, no effect

    class Sensor:
        def observe(self):
            return "obs"

    class Predictor:
        def predict(self, o):
            return Prediction(value="p", uncertainty=0.1, model_id="eo2")

    class Verifier:
        def verify(self, o, p):
            return {"status": "PASS"}

    ledger = Ledger()
    wf = EvidenceWorkflow(sensor=Sensor(), predictor=Predictor(), verifier=Verifier(), executor=Executor(),
                          evidence_sink=LedgerSink(ledger))
    cap = Capability("valve", decision != "REFUSE", ("fresh",))
    rt = RuntimeState(platform="eo2", python_version="eo2", thermal_status="hot" if decision == "DEFER" else "normal")
    before, view_before = target.read(), json.loads(view.read_text(encoding="utf-8"))
    result = wf.run(record_id=f"eo2-{case}", input_digest="sha256:eo2", capability=cap, runtime=rt,
                    action=ActionProposal("valve", "open_valve", {"target": "V1"}), metadata={"fresh": True})
    after, view_after = target.read(), json.loads(view.read_text(encoding="utf-8"))
    print(json.dumps({"record": ledger.all()[-1].to_dict(), "execution_result": result.execution_result,
                      "real": [before, after], "view": [view_before, view_after]}, default=str))


# ---------------------------------------------------------------- parent side
def repo_copy(mutate):
    d = pathlib.Path(tempfile.mkdtemp(prefix="eo2_")) / "sv"
    shutil.copytree(ROOT, d, ignore=shutil.ignore_patterns(".git", "__pycache__", "*.egg-info", ".pytest_cache"))
    if mutate:
        p = d / "sovereign_veritas" / "workflow.py"
        s = p.read_text(encoding="utf-8")
        if s.count(ANCHOR) != 1:
            print("COULD NOT RUN: mutant anchor not found exactly once in workflow.py")
            sys.exit(2)
        p.write_text(s.replace(ANCHOR, MUTANT + ANCHOR), encoding="utf-8")
    return d


def run_case(repo, case):
    _, decision, kind, initial = CASES[case]
    work = tempfile.mkdtemp(prefix="eo2w_")
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    env.pop("PYTHONPATH", None)
    p = subprocess.run([sys.executable, str(ROOT / "tools" / "eo2_probe.py"), "--child", case, decision, kind,
                        initial, work], cwd=repo, capture_output=True, text=True, env=env)
    if p.returncode != 0:
        print(f"COULD NOT RUN: case {case}: {p.stderr.strip().splitlines()[-1:]}")
        sys.exit(2)
    return json.loads(p.stdout.strip().splitlines()[-1])


def r0(rec, _res):
    s = (rec.get("metadata") or {}).get("execution_status")
    return "OK" if s is None or (s in ("SUCCEEDED", "FAILED") and rec["decision"] == "ALLOW") else "RECORD_FAIL"


def r1(rec, res):
    receipt = res.get("receipt") if isinstance(res, dict) else None
    if rec["decision"] == "ALLOW" and (rec.get("metadata") or {}).get("execution_status") == "SUCCEEDED":
        want = SPEC[rec["action"]["requested"]]["V1"]
        ok = (receipt is not None and receipt.get("requested") == rec["action"]["requested"]
              and receipt.get("state") == want)
        return "OK" if ok else "RECEIPT_FAIL"
    return "OK" if receipt is None else "RECEIPT_FAIL"


def main():
    if "--child" in sys.argv:
        i = sys.argv.index("--child")
        return child(*sys.argv[i + 1:i + 6])

    sabotage = "--sabotage" in sys.argv
    print(f"EO-2 | {'SABOTAGE: blind observer (after = before)' if sabotage else 'registered run'} | python "
          f"{sys.version.split()[0]} | {sys.platform}")
    sys.path.insert(0, str(ROOT))
    from sovereign_veritas.effect_observation import check_observed_effect, make_observation

    repos = {"clean": repo_copy(False), "mutant": repo_copy(True)}
    runs = {c: run_case(repos[spec[0]], c) for c, spec in CASES.items()}

    def obs(run, case, which="real"):
        before, after = run[which]
        if sabotage:
            after = before
        return make_observation(f"eo2-{case}", run["record"]["action"], before, after)

    # (record, executor result, observation) per case; A6 and A7 reuse the A5 run.
    inputs = {c: (runs[c]["record"], runs[c]["execution_result"], obs(runs[c], c)) for c in CASES}
    inputs["A6"] = (runs["A5"]["record"], runs["A5"]["execution_result"], obs(runs["C1"], "C1"))
    inputs["A7"] = (runs["A5"]["record"], runs["A5"]["execution_result"], obs(runs["A5"], "A5", "view"))

    checkers = {
        "R0": lambda rec, res, o: r0(rec, res),
        "R1": lambda rec, res, o: r1(rec, res),
        "R2": lambda rec, res, o: check_observed_effect(rec, o, SPEC.get(rec["action"]["requested"])),
        "R2u": lambda rec, res, o: check_observed_effect(rec, o, SPEC.get(rec["action"]["requested"]), bind=False),
        "PARANOID": lambda rec, res, o: "FLAG",
    }
    order = ["C1", "C2", "C3", "C4", "A1", "A2", "A3", "A4", "A5", "A6", "A7"]
    table = {k: {c: f(*inputs[c]) for c in order} for k, f in checkers.items()}
    facts = {c: {"decision": inputs[c][0]["decision"],
                 "execution_status": (inputs[c][0].get("metadata") or {}).get("execution_status"),
                 "real_before_after": runs[c]["real"] if c in runs else None} for c in order}

    print(f"  {'':9}" + "".join(f"{c:>21}" for c in order))
    for k, row in table.items():
        print(f"  {k:9}" + "".join(f"{row[c]:>21}" for c in order))
    for c in ("A1", "A2", "A3", "A4", "A5"):
        print(f"  {c}: {json.dumps(facts[c], sort_keys=True)}")

    attacks = ["A1", "A2", "A3", "A4", "A5", "A6", "A7"]
    det = lambda k: {a for a in attacks if table[k][a] not in ("OK", "UNOBSERVABLE")}  # noqa: E731
    no_false_alarm = lambda k: all(table[k][c] == "OK" for c in ("C1", "C2", "C3"))  # noqa: E731
    p = {
        "P1": det("R0") == set() and no_false_alarm("R0") and table["R0"]["C4"] == "OK",
        "P2": det("R1") == {"A3", "A4"} and no_false_alarm("R1") and table["R1"]["C4"] == "OK",
        "P3": (no_false_alarm("R2") and [table["R2"][a] for a in attacks[:6]]
               == ["UNAUTHORIZED_EFFECT", "UNAUTHORIZED_EFFECT", "NO_EFFECT", "WRONG_EFFECT", "NO_EFFECT",
                   "BINDING_MISMATCH"]),
        "P4": det("R2u") == set(attacks[:5]) and no_false_alarm("R2u"),
        "P5": table["R2"]["A7"] == "OK",
        "P6": table["R2"]["C4"] == "UNOBSERVABLE" and table["R2u"]["C4"] == "UNOBSERVABLE",
        "P7": all(table["PARANOID"][c] != "OK" for c in ("C1", "C2", "C3")),
    }
    print()
    for k, x in p.items():
        print(f"  {k}  {'HELD' if x else 'REFUTED'}")
    if sabotage:  # P8 as registered: R2 misses A1, A2, A4, false-alarms NO_EFFECT on C1, and P3 is REFUTED
        p8 = ([table["R2"][a] for a in ("A1", "A2")] == ["OK", "OK"] and table["R2"]["A4"] in ("OK", "UNOBSERVABLE")
              and table["R2"]["C1"] == "NO_EFFECT" and not p["P3"])
        print(f"  P8  {'HELD' if p8 else 'REFUTED'} (sabotage arm)")
    held = tuple(k for k, x in p.items() if x)
    print(f"VERDICT {len(held)} of {len(p)} as registered (P8 is --sabotage; P9 is the tests; P10 is the door)")
    dg = hashlib.sha256(json.dumps({"table": table, "facts": facts, "verdicts": p}, sort_keys=True).encode()).hexdigest()
    print(f"DIGEST {dg}")
    if "--json" in sys.argv:
        pathlib.Path(sys.argv[sys.argv.index("--json") + 1]).write_text(
            json.dumps({"table": table, "facts": facts, "verdicts": p}, sort_keys=True, indent=1) + "\n",
            encoding="utf-8")
    if sabotage or RECORDED is None:
        return 0 if all(p.values()) else 1
    return 0 if (held, dg) == RECORDED else 1


if __name__ == "__main__":
    sys.exit(main() or 0)
