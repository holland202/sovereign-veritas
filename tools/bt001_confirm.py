#!/usr/bin/env python3
"""BT-001 survivor triage, BT-P7: run one concrete input against the original code and against a surviving mutant.

A survivor is a GAP when the two print different results for an input written here. The script, not an argument,
is the evidence. Each case runs in a fresh scratch copy of the repository, with bytecode caching off.

    python tools/bt001_confirm.py [SCRATCH_DIR]
Stdlib only; uses tools/bt001_mutate.py to build the mutant text. Self-tested: Claude wrote the inputs.
"""
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bt001_mutate as bm  # noqa: E402

ROOT = bm.ROOT
PRE = ("import math,sys,os,tempfile\n"
       "from dataclasses import replace\n"
       "from sovereign_veritas.capability import Capability, CapabilityRegistry\n"
       "from sovereign_veritas.decision import Gate\n"
       "from sovereign_veritas.evidence import EvidenceRecord, Ledger, canonical_json, _validate_jsonable\n"
       "from sovereign_veritas.runtime import RuntimeState\n"
       "RT = RuntimeState(platform='t', python_version='3')\n"
       "def rec(**kw): return EvidenceRecord(record_id='r', input_digest='d', verification={'status': 'PASS'}, **kw)\n"
       "def tryit(f):\n"
       "    try: return repr(f())\n"
       "    except Exception as e: return type(e).__name__ + ': ' + str(e)[:90]\n")

CASES = [
    ("sovereign_veritas/capability.py#0", "a Capability built without `authorized` is evaluated by the Gate",
     "print(Gate().evaluate(rec(), Capability('x'), RT).decision)"),
    ("sovereign_veritas/capability.py#16", "CapabilityRegistry.check on a name that is not registered",
     "print(CapabilityRegistry().check('ghost', {}))"),
    ("sovereign_veritas/decision.py#72", "step_count equal to max_steps",
     "print(Gate().evaluate(rec(metadata={'step_count': 3}), Capability('x', True, max_steps=3), RT).decision)"),
    ("sovereign_veritas/evidence.py#59", "Ledger.append of a record with an empty record_id",
     "print(tryit(lambda: Ledger().append(EvidenceRecord(record_id='', input_digest='d')).record_id))"),
    ("sovereign_veritas/evidence.py#56", "Ledger.append of a record with an id but an empty input_digest",
     "print(tryit(lambda: Ledger().append(EvidenceRecord(record_id='r', input_digest='')).record_id))"),
    ("sovereign_veritas/evidence.py#70", "a ledger whose record 1 points at the wrong predecessor, digests kept consistent",
     "L=Ledger(); L.append(EvidenceRecord(record_id='a', input_digest='d')); L.append(EvidenceRecord(record_id='b', input_digest='d'))\n"
     "bad=replace(L._records[1], previous_digest='0'*64); L._records[1]=bad; L._digests[1]=bad.record_digest\n"
     "print(tryit(L.verify))"),
    ("sovereign_veritas/evidence.py#18", "canonical JSON of a non-ASCII value (the hash-chain input)",
     "print(canonical_json({'name': 'caf\\u00e9'}))"),
    ("sovereign_veritas/evidence.py#20", "a dict with mixed key types passed to the JSON validator",
     "print(tryit(lambda: _validate_jsonable({1: 'a', 'b': 2})))"),
    ("sovereign_veritas/evidence.py#7", "a tuple inside action parameters, as frozen into a record",
     "print(rec(action={'capability': 'x', 'requested': 'r', 'parameters': {'t': (1, 2)}}).action['parameters']['t'])"),
    ("sovereign_veritas/workflow.py#18", "a prediction whose uncertainty is NaN, everything else ALLOW (effects counted at the executor)",
     "sys.path.insert(0, 'tools'); import execution_boundary_probe as xb\n"
     "from sovereign_veritas.evidence import LedgerSink\n"
     "from sovereign_veritas.interfaces.contracts import ActionProposal, Prediction\n"
     "from sovereign_veritas.workflow import EvidenceWorkflow\n"
     "class P:\n    def predict(self, o): return Prediction(value='v', uncertainty=float('nan'), model_id='m')\n"
     "ex=xb.CountingExecutor()\n"
     "w=EvidenceWorkflow(sensor=xb.Sensor(), predictor=P(), verifier=xb.Verifier(), executor=ex, evidence_sink=LedgerSink(Ledger()))\n"
     "r=tryit(lambda: w.run(record_id='r', input_digest='d', capability=Capability('x', True), runtime=RT, action=ActionProposal('x', 'go', {})).decision.decision)\n"
     "print('effects', ex.effects, '|', r)"),
    ("sovereign_veritas/idempotency.py#44", "a reservation file that is not valid JSON, then reserve() on its key",
     "from sovereign_veritas.idempotency import FileReservations\n"
     "d=tempfile.mkdtemp(); s=FileReservations(d); open(s._path('K'),'w').write('{')\n"
     "print(tryit(lambda: s.reserve('K')))"),
    ("sovereign_veritas/idempotency.py#42", "a reservation file holding {} (no state), then state() and release()",
     "from sovereign_veritas.idempotency import FileReservations\n"
     "d=tempfile.mkdtemp(); s=FileReservations(d); open(s._path('K'),'w').write('{}')\n"
     "print(s.state('K'), '|', tryit(lambda: s.release('K', by='p', reason='r')))"),
    ("sovereign_veritas/idempotency.py#42", "a reservation file holding a JSON list that contains \"state\", then reserve()",
     "from sovereign_veritas.idempotency import FileReservations\n"
     "d=tempfile.mkdtemp(); s=FileReservations(d); open(s._path('K'),'w').write('[\"state\"]')\n"
     "print(tryit(lambda: s.reserve('K')))"),
    ("sovereign_veritas/idempotency.py#38", "a FileReservations directory whose parent does not exist",
     "from sovereign_veritas.idempotency import FileReservations\n"
     "d=tempfile.mkdtemp(); print(tryit(lambda: type(FileReservations(os.path.join(d, 'a', 'b'))).__name__))"),
    ("sovereign_veritas/idempotency.py#4", "lease_s=0 with the clock frozen (a coarse clock reads the same instant twice)",
     "import time; time.time=lambda: 1000.0\n"
     "from sovereign_veritas.idempotency import MemoryReservations\n"
     "s=MemoryReservations(); s.reserve('K', lease_s=0); print(s.state('K'))"),
]


def run(work, code):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    env.pop("PYTHONPATH", None)
    bm.clear_pyc(work)
    p = subprocess.run([sys.executable, "-B", "-c", PRE + code], cwd=work, env=env, capture_output=True, text=True,
                       timeout=120)
    return (p.stdout.strip() or p.stderr.strip().splitlines()[-1])[:160]


def main():
    scratch = sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp()
    work = os.path.join(scratch, "bt001_confirm_work")
    bm.make_work(work)
    gaps = 0
    for mid, what, code in CASES:
        target = mid.split("#")[0]
        _, ms = bm.mutants(target)
        m = next(x for x in ms if x["id"] == mid)
        orig = run(work, code)
        path = os.path.join(work, target)
        original_text = open(os.path.join(ROOT, target), encoding="utf-8").read()
        open(path, "w", encoding="utf-8").write(m["text"])
        try:
            mutated = run(work, code)
        finally:
            open(path, "w", encoding="utf-8").write(original_text)
        verdict = "GAP (differs)" if orig != mutated else "SAME (not shown to differ by this input)"
        gaps += orig != mutated
        print(f"{mid}  [{m['op']}, line {m['line']}]  {what}\n    original: {orig}\n    mutant:   {mutated}\n    {verdict}")
    print(f"\n{gaps} of {len(CASES)} inputs separate the mutant from the original")
    return 0


if __name__ == "__main__":
    sys.exit(main())
