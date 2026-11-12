"""Covering probe for the Sovereign Veritas transition wrap (StegVerse Build Lane).

Registered expectations, in the repository's probe style. Effects are counted at the
executor, which stands in for the external world; the target is a state dict the
executor changes and the probe reads back without going through the executor.

    C0  anti-vacuity: two distinct record_ids, guarded -> 2 effects, pair CONSISTENT
    C1  duplicate record_id, sink WITHOUT has_record (XB-1's documented-limit
        configuration, which gives 2 effects unguarded) -> refused, 1 effect
    C2  two threads race one record_id -> exactly 1 effect, one refusal (XB-1 X4)
    C3  evidence write fails after the effect (XB-1 X5) -> the COMPLETION stands;
        the verifier names completion-without-evidence instead of silence
    C4  EO-1 construction: executor driven directly (guard bypassed), the record
        then claims no execution -> the pair verifier FAILS it (V5)
    C5  a record claims SUCCEEDED with no transition entries -> FAIL (V3)
    C6  executor raises -> intent UNKNOWN, held; a second attempt is refused
        before the executor is reached again

Run from a Sovereign Veritas checkout with this file's directory on the path:
    PYTHONPATH=<sovereign-veritas>:<this dir> python3 run_cover_tests.py
Exit 0 only if every case is as registered.
"""
from __future__ import annotations

import sys
import tempfile
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from sovereign_veritas.capability import Capability
from sovereign_veritas.evidence import Ledger, LedgerSink
from sovereign_veritas.interfaces.contracts import ActionProposal, Prediction
from sovereign_veritas.runtime import RuntimeState
from sovereign_veritas.workflow import EvidenceWorkflow

from sv_transition_cover import TransitionLedger, run_guarded
from sv_transition_cover.guarded_workflow import TransitionExecutor
from sv_transition_cover.transition_ledger import TransitionLedger as TL
from sv_transition_cover.verify_transition import verify

RESULTS: list[tuple[str, bool, str]] = []


def case(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))
    print(f"{'ok  ' if ok else 'FAIL'} {name}  {detail}")


class _Sensor:
    def observe(self):
        return "o"


class _Predictor:
    def predict(self, observation):
        return Prediction(value="p", uncertainty=0.1, model_id="m")


class _Verifier:
    def verify(self, observation, prediction):
        return {"status": "PASS"}


class _PlainSink:
    """The sink from XB-1's documented limit: no has_record, plain append."""

    def __init__(self):
        self.ledger = Ledger()

    def record(self, r):
        return self.ledger.append(r)


class _Target:
    def __init__(self):
        self.state = {"lamp": "off"}
        self.effects = 0

    def execute(self, action):
        self.effects += 1
        self.state["lamp"] = "on"
        return {"n": self.effects}

    def probe(self):
        return dict(self.state)


def _expected(action_dict):
    return {"lamp": "on"}


def _wf(sink, ex):
    return EvidenceWorkflow(sensor=_Sensor(), predictor=_Predictor(),
                            verifier=_Verifier(), executor=ex, evidence_sink=sink)


def _kwargs(rid):
    return dict(record_id=rid, input_digest="abc",
                capability=Capability("read_only", True, ("fresh",)),
                runtime=RuntimeState(platform="android", python_version="3.11"),
                action=ActionProposal(capability="read_only", requested="read", parameters={}),
                metadata={"fresh": True})


def _records(sink):
    return [r.to_dict() for r in sink.ledger.all()]


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="sv-cover-"))

    # C0 anti-vacuity
    t, sink = _Target(), LedgerSink(Ledger())
    led = TL(tmp / "c0.jsonl")
    wf = _wf(sink, t)
    run_guarded(wf, led, t.probe, _expected, **_kwargs("c0-a"))
    run_guarded(wf, led, t.probe, _expected, **_kwargs("c0-b"))
    fails = verify(_records(sink), led.path)
    case("C0 anti-vacuity: 2 effects, pair CONSISTENT",
         t.effects == 2 and not fails, f"effects={t.effects} failures={fails}")

    # C1 duplicate, sink without has_record
    t, sink = _Target(), _PlainSink()
    led = TL(tmp / "c1.jsonl")
    wf = _wf(sink, t)
    run_guarded(wf, led, t.probe, _expected, **_kwargs("dup"))
    refused = False
    try:
        run_guarded(wf, led, t.probe, _expected, **_kwargs("dup"))
    except ValueError:
        refused = True
    case("C1 duplicate refused before effect (no has_record sink)",
         refused and t.effects == 1, f"refused={refused} effects={t.effects}")

    # C2 race
    t, led = _Target(), TL(tmp / "c2.jsonl")
    errors: list[str] = []

    def racer():
        try:
            run_guarded(_wf(_PlainSink(), t), led, t.probe, _expected, **_kwargs("race"))
        except Exception as exc:  # noqa: BLE001 - the refusal is the expectation
            errors.append(type(exc).__name__)

    threads = [threading.Thread(target=racer) for _ in range(2)]
    [th.start() for th in threads]
    [th.join() for th in threads]
    case("C2 race: exactly one effect", t.effects == 1 and len(errors) == 1,
         f"effects={t.effects} refusals={errors}")

    # C3 X5: evidence write fails after the effect
    class _FailingSink:
        def record(self, r):
            raise OSError("simulated write failure (disk full)")

    t = _Target()
    led = TL(tmp / "c3.jsonl")
    raised = False
    try:
        run_guarded(_wf(_FailingSink(), t), led, t.probe, _expected, **_kwargs("x5"))
    except OSError:
        raised = True
    kinds = [e["kind"] for e in led.entries()]
    fails = verify([], led.path)
    named = any(f.startswith("V4") for f in fails)
    case("C3 X5: completion stands, asymmetry named (not silence)",
         raised and kinds == ["INTENT", "COMPLETION"] and named,
         f"kinds={kinds} verifier_failures={fails}")

    # C4 EO-1 construction
    t = _Target()
    led = TL(tmp / "c4.jsonl")
    proxy = TransitionExecutor(t, led, "eo1", t.probe, _expected)
    proxy.execute(ActionProposal(capability="read_only", requested="read", parameters={}))
    # the workflow's record, as EO-1 constructs it: the guard was broken, the
    # executor ran, the record was written - and claims no execution took place.
    # The sink proxy flushes the completion before that record is delegated.
    from sv_transition_cover.guarded_workflow import TransitionSink
    from types import SimpleNamespace

    class _Collector:
        def record(self, r):
            return None

    TransitionSink(_Collector(), led, proxy).record(SimpleNamespace(record_id="eo1"))
    false_record = {"record_id": "eo1",
                    "action": {"capability": "read_only", "requested": "read", "parameters": {}},
                    "decision": "REFUSE", "metadata": {}}
    fails = verify([false_record], led.path)
    case("C4 EO-1 pair mismatch FAILS (V5)", any(f.startswith("V5") for f in fails),
         f"failures={fails}")

    # C5 unattested SUCCEEDED
    led = TL(tmp / "c5.jsonl")
    claim = {"record_id": "ghost",
             "action": {"capability": "read_only", "requested": "read", "parameters": {}},
             "decision": "ALLOW", "metadata": {"execution_status": "SUCCEEDED"}}
    fails = verify([claim], led.path)
    case("C5 SUCCEEDED with no COMPLETION FAILS (V3)",
         any(f.startswith("V3") for f in fails), f"failures={fails}")

    # C6 executor raises: UNKNOWN held, retry refused at the boundary
    class _Boom:
        def __init__(self):
            self.calls = 0

        def execute(self, action):
            self.calls += 1
            raise RuntimeError("executor failed")

    boom, sink = _Boom(), _PlainSink()
    led = TL(tmp / "c6.jsonl")
    wf = _wf(sink, boom)
    try:
        run_guarded(wf, led, lambda: {}, None, **_kwargs("boom"))
    except RuntimeError:
        pass
    refused = False
    try:
        run_guarded(wf, led, lambda: {}, None, **_kwargs("boom"))
    except ValueError:
        refused = True
    kinds = [e["kind"] for e in led.entries()]
    case("C6 executor failure: UNKNOWN held, retry refused before executor",
         kinds == ["INTENT", "UNKNOWN"] and refused and boom.calls == 1,
         f"kinds={kinds} refused={refused} executor_calls={boom.calls}")

    bad = [r for r in RESULTS if not r[1]]
    print(f"COVER VERDICT  {'PASS' if not bad else 'FAIL'} - {len(RESULTS) - len(bad)}/{len(RESULTS)} as registered")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
