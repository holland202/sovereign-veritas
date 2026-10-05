#!/usr/bin/env python3
"""EO-1 harness (registration docs/EO1_PREREG.md): does SV's record observe the external effect, or only the
workflow's account of calling the executor?

  python tools/eo1_probe.py [--sabotage] [--json PATH]

The effect is counted outside SV: a counting executor appends one JSON line per execute() to a marker file.
Mutant M1 runs on a temporary copy of the repository; the checkout is never edited.
--sabotage replaces the effect counter with one that always reads 0 (must refute E2, E4, E5 and exit 1).
"""
import contextlib
import hashlib
import io
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
RECORDED = None

ANCHOR = '        if decision.decision == "ALLOW":\n            if action is None:'
MUTANT = ('        if decision.decision != "ALLOW" and action is not None:\n'
          '            self.executor.execute(action)  # EO-1 MUTANT\n\n')


# ---------------------------------------------------------------- child side: runs inside a repo copy
def child_workflow(case, executor_kind, marker):
    sys.path.insert(0, os.getcwd())
    from sovereign_veritas.capability import Capability
    from sovereign_veritas.evidence import Ledger, LedgerSink
    from sovereign_veritas.interfaces.contracts import ActionProposal, Prediction
    from sovereign_veritas.runtime import RuntimeState
    from sovereign_veritas.workflow import EvidenceWorkflow

    class Sensor:
        def observe(self):
            return "obs"

    class Predictor:
        def predict(self, o):
            return Prediction(value="p", uncertainty=0.1, model_id="eo1")

    class Verifier:
        def verify(self, o, p):
            return {"status": "PASS"}

    class Counting:
        def execute(self, action):
            requested = "close_valve" if executor_kind == "wrong_action" else action.requested
            if executor_kind != "noop":
                with open(marker, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps({"requested": requested}) + "\n")
            return {"executed": action.requested}

    ledger = Ledger()
    wf = EvidenceWorkflow(sensor=Sensor(), predictor=Predictor(), verifier=Verifier(), executor=Counting(),
                          evidence_sink=LedgerSink(ledger))
    cap = Capability("valve", case != "REFUSE", ("fresh",))
    rt = RuntimeState(platform="eo1", python_version="eo1", thermal_status="hot" if case == "DEFER" else "normal")
    result = wf.run(record_id="eo1", input_digest="sha256:eo1", capability=cap, runtime=rt,
                    action=ActionProposal("valve", "open_valve", {"target": "V1"}), metadata={"fresh": True})
    rec = ledger.all()[-1].to_dict()
    print(json.dumps({"decision": rec["decision"], "execution_status": rec["metadata"].get("execution_status"),
                      "action_requested": rec["action"]["requested"], "executed": result.executed}))


def child_package(marker, home):
    sys.path[:0] = [os.getcwd(), os.path.join(os.getcwd(), "tools")]
    import make_package

    class Counting:
        def execute(self, action):
            with open(marker, "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"requested": action.requested}) + "\n")
            return {"recorded": action.requested}

    make_package.NoSideEffect = Counting
    os.environ["HOME"] = home
    sys.argv = ["make_package.py", "--rounds", "10", "--thermal-status", "hot"]
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        make_package.main()
    path = next(line.split()[1] for line in out.getvalue().splitlines() if line.startswith("package "))
    print(json.dumps({"package": path}))


# ---------------------------------------------------------------- parent side
def repo_copy(mutate):
    d = pathlib.Path(tempfile.mkdtemp(prefix="eo1_")) / "sv"
    shutil.copytree(ROOT, d, ignore=shutil.ignore_patterns(".git", "__pycache__", "*.egg-info", ".pytest_cache"))
    if mutate:
        p = d / "sovereign_veritas" / "workflow.py"
        s = p.read_text(encoding="utf-8")
        if s.count(ANCHOR) != 1:
            print("COULD NOT RUN: mutant anchor not found exactly once in workflow.py")
            sys.exit(2)
        p.write_text(s.replace(ANCHOR, MUTANT + ANCHOR), encoding="utf-8")
    return d


def effects(marker, sabotage):
    if sabotage or not os.path.exists(marker):
        return 0, []
    lines = [json.loads(x) for x in pathlib.Path(marker).read_text(encoding="utf-8").splitlines() if x.strip()]
    return len(lines), [x["requested"] for x in lines]


def run_child(repo, args):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    env.pop("PYTHONPATH", None)
    p = subprocess.run([sys.executable, str(ROOT / "tools" / "eo1_probe.py"), "--child", *args], cwd=repo,
                       capture_output=True, text=True, env=env)
    if p.returncode != 0:
        print(f"COULD NOT RUN: child {args} failed: {p.stderr.strip().splitlines()[-1:]}")
        sys.exit(2)
    return json.loads(p.stdout.strip().splitlines()[-1])


def workflow_arm(repo, case, kind, sabotage):
    marker = str(pathlib.Path(tempfile.mkdtemp(prefix="eo1m_")) / "effects.jsonl")
    out = run_child(repo, ["workflow", case, kind, marker])
    n, req = effects(marker, sabotage)
    return dict(out, effects=n, effect_requested=req)


def main():
    if "--child" in sys.argv:
        i = sys.argv.index("--child")
        mode, rest = sys.argv[i + 1], sys.argv[i + 2:]
        return child_workflow(*rest) if mode == "workflow" else child_package(*rest)

    sabotage = "--sabotage" in sys.argv
    print(f"EO-1 | {'SABOTAGE: effect counter always reads 0' if sabotage else 'registered run'} | python "
          f"{sys.version.split()[0]} | {sys.platform}")
    clean, mutant = repo_copy(False), repo_copy(True)

    r = {"E1": {c: workflow_arm(clean, c, "counting", sabotage) for c in ("ALLOW", "REFUSE", "DEFER")},
         "E2": {c: workflow_arm(mutant, c, "counting", sabotage) for c in ("REFUSE", "DEFER")}}

    # The whole suite, as registered (a first run used tests/test_workflow.py only; see EO1_RESULTS deviations).
    t = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-rf"], cwd=mutant,
                       capture_output=True, text=True)
    failed = sorted({ln[len("FAILED "):].split(" - ")[0] for ln in t.stdout.splitlines() if ln.startswith("FAILED")})
    summary = t.stdout.strip().splitlines()[-1].split(" in ")[0]  # timing removed: the digest must be reproducible
    r["E3"] = {"summary": summary, "failed": failed}

    marker = str(pathlib.Path(tempfile.mkdtemp(prefix="eo1m_")) / "effects.jsonl")
    home = tempfile.mkdtemp(prefix="eo1h_")
    pkg = run_child(mutant, ["package", marker, home])["package"]
    v = subprocess.run([sys.executable, str(mutant / "tools" / "verify_package.py"), pkg], capture_output=True, text=True)
    decision = json.loads(pathlib.Path(pkg).read_text(encoding="utf-8"))["decision"]["decision"]
    n, _ = effects(marker, sabotage)
    r["E4"] = {"decision": decision, "verify_exit": v.returncode,
               "verdict": next((ln for ln in v.stdout.splitlines() if ln.startswith("VERDICT")), None),
               "execution_check": next((ln for ln in v.stdout.splitlines() if "execution_only_if_allowed" in ln), None),
               "effects": n}
    r["E5"] = {k: workflow_arm(clean, "ALLOW", k, sabotage) for k in ("noop", "wrong_action")}

    for k, x in r.items():
        print(f"  {k}: {json.dumps(x, sort_keys=True)}")

    no_status = lambda x: x["execution_status"] is None and x["executed"] is False  # noqa: E731
    e1 = r["E1"]
    v = {
        "E1": (e1["ALLOW"]["effects"] == 1 and (e1["ALLOW"]["decision"], e1["ALLOW"]["execution_status"]) == ("ALLOW", "SUCCEEDED")
               and e1["ALLOW"]["executed"] is True
               and all(e1[c]["effects"] == 0 and e1[c]["decision"] == c and no_status(e1[c]) for c in ("REFUSE", "DEFER"))),
        "E2": all(r["E2"][c]["effects"] == 1 and r["E2"][c]["decision"] == c and no_status(r["E2"][c]) for c in ("REFUSE", "DEFER")),
        "E3": "failed" in r["E3"]["summary"] and {"tests/test_workflow.py::test_refused_capability_never_executes",
                                                    "tests/test_workflow.py::test_failed_verification_never_executes"}
              <= set(r["E3"]["failed"]),
        "E4": (r["E4"]["decision"] == "DEFER" and r["E4"]["verify_exit"] == 0 and r["E4"]["effects"] == 1
               and (r["E4"]["verdict"] or "").startswith("VERDICT  CONSISTENT")
               and r["E4"]["execution_check"] == "PASS  execution_only_if_allowed          no execution recorded"),
        "E5": (r["E5"]["noop"]["effects"] == 0 and r["E5"]["noop"]["execution_status"] == "SUCCEEDED"
               and r["E5"]["wrong_action"]["effect_requested"] == ["close_valve"]
               and r["E5"]["wrong_action"]["action_requested"] == "open_valve"
               and r["E5"]["wrong_action"]["execution_status"] == "SUCCEEDED"),
    }
    print()
    for k, x in v.items():
        print(f"  {k}  {'HELD' if x else 'REFUTED'}")
    held = tuple(k for k, x in v.items() if x)
    print(f"VERDICT {len(held)} of {len(v)} as registered (E6 is --sabotage; E7 is the door)")
    stable = {k: x for k, x in r.items() if k != "E4"} | {"E4": {k: x for k, x in r["E4"].items()}}
    dg = hashlib.sha256(json.dumps({"results": stable, "verdicts": v}, sort_keys=True).encode()).hexdigest()
    print(f"DIGEST {dg}")
    if "--json" in sys.argv:
        pathlib.Path(sys.argv[sys.argv.index("--json") + 1]).write_text(
            json.dumps({"results": r, "verdicts": v}, sort_keys=True, indent=1) + "\n", encoding="utf-8")
    if sabotage or RECORDED is None:
        return 0 if all(v.values()) else 1
    return 0 if (held, dg) == RECORDED else 1


if __name__ == "__main__":
    sys.exit(main() or 0)
