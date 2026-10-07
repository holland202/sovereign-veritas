#!/usr/bin/env python3
"""ex1_campaign.py - EX-1 crash campaign (docs/EX1_PREREG.md, X1-X4, X6, X8).

Every case runs the first submission in a child process that dies (os._exit, PROCESS_KILL) or fails a storage write
(OSError, STORAGE_FAILURE) at one fault point. The parent then restarts: recovery, then a retry with the same key, then a
second retry. Ground truth is world.jsonl, written (and fsynced) by the executor and read only by this harness and the
independent observer, never by the coordinator's decision path.

  python tools/ex1_campaign.py            # registered run; exit 0 iff every prediction held
  python tools/ex1_campaign.py --sabotage # the coordinator calls the executor BEFORE writing DISPATCHED: X1/X4 must fail
Needs ssh-keygen (receipts are really signed). Container/desktop only; not validated on Android storage.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.dont_write_bytecode = True

POINTS = ["before_reserve_publish", "after_reserve_publish", "after_authorize", "before_append:DISPATCHED",
          "after_append:DISPATCHED", "before_execute", "after_execute", "before_append:EXECUTOR_ACKNOWLEDGED",
          "after_ack", "before_append:EFFECT_ATTESTED", "after_attest"]
FAULTS = ["kill", "storage"]
ADMITS_EFFECT = {"EFFECT_ATTESTED", "EFFECT_UNCONFIRMED", "INDEPENDENTLY_CONFIRMED", "EFFECT_DISPUTED", "FINALIZED",
                 "EXECUTOR_ACKNOWLEDGED", "DISPATCHED"}

CHILD = r"""
import json, os, sys
cfg = json.loads(sys.argv[1]); sys.path.insert(0, cfg["root"])
from tools.ex1_campaign import build
co = build(cfg)
co.submit("payments", "client:alice", cfg["key"], {"op": "transfer", "amount": 100}, "sha256:auth")
"""


def keys(tmp):
    key = os.path.join(tmp, "executor_key")
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "executor-1", "-f", key], check=True)
    pub = open(key + ".pub").read().split()
    signers = os.path.join(tmp, "receipt_signers")
    open(signers, "w").write(f'executor-1 namespaces="sv-effect-receipt" {pub[0]} {pub[1]}\n')
    return key, signers


def build(cfg):
    """A coordinator wired as cfg says; used by the parent and by child processes."""
    from sovereign_veritas.execution import ExecutionCoordinator, ExecutionJournal
    from sovereign_veritas.receipts import sign_receipt, verify_receipt

    def fault(point):
        if point == cfg.get("point"):
            if cfg.get("fault") == "kill":
                os._exit(9)
            raise OSError(f"injected storage failure at {point}")

    class Executor:
        done = {}

        def execute(self, command, ctx):
            if ctx["attempt_id"] in self.done:  # the same attempt delivered twice in-process: no second effect
                return self.done[ctx["attempt_id"]]
            if not cfg.get("lying"):
                with open(cfg["world"], "a", encoding="utf-8") as fh:
                    fh.write(json.dumps({"record_id": ctx["record_id"], "attempt_id": ctx["attempt_id"]}) + "\n")
                    fh.flush()
                    os.fsync(fh.fileno())
            receipt = {"schema": "sv.effect-receipt/1", "receipt_id": ctx["attempt_id"] + "-r", "executor_id": "executor-1",
                       "executor_key_id": "executor-1", "effect_type": "transfer/1", "effect_result": "ATTESTED",
                       "effect_reference": "bank-ref", "observed_at": {"value": None, "source": "executor", "confidence": "declared"},
                       "prior_receipt_digest": None, **{k: ctx[k] for k in ("record_id", "attempt_id", "command_digest",
                                                                             "authorization_digest")}}
            self.done[ctx["attempt_id"]] = sign_receipt(receipt, cfg["key_path"])
            return self.done[ctx["attempt_id"]]

    def observer(command, ctx):
        if not os.path.exists(cfg["world"]):
            return False
        return any(json.loads(l)["record_id"] == ctx["record_id"] for l in open(cfg["world"]) if l.strip())

    co = ExecutionCoordinator(ExecutionJournal(cfg["journal"], fault=fault), decide=lambda c: ("ALLOW", []),
                              executor=Executor(), verify=lambda r, ctx: verify_receipt(r, expected=ctx,
                                                                                       allowed_signers=cfg["signers"]),
                              observer=observer if cfg.get("observer") else None, fault=fault)
    if cfg.get("sabotage"):  # dispatch before the write-ahead record: what EvidenceWorkflow does today
        orig = co.j.append

        def append(intent, to, actor, detail=None, attempt_id=None):
            if to == "DISPATCHED":
                co.executor.execute({"op": "transfer", "amount": 100}, detail["context"])
            return orig(intent, to, actor, detail, attempt_id)
        co.j.append = append
    return co


def world_effects(cfg):
    if not os.path.exists(cfg["world"]):
        return 0
    return sum(1 for l in open(cfg["world"]) if l.strip())


def run_case(tmp, key_path, signers, point, fault, sabotage=False):
    d = tempfile.mkdtemp(dir=tmp)
    cfg = {"root": ROOT, "journal": os.path.join(d, "journal"), "world": os.path.join(d, "world.jsonl"),
           "key_path": key_path, "signers": signers, "key": "invoice-7", "point": point, "fault": fault,
           "sabotage": sabotage}
    subprocess.run([sys.executable, "-c", CHILD, json.dumps(cfg)], capture_output=True, text=True, cwd=ROOT)
    restart = dict(cfg, point=None, fault=None)
    co = build(restart)
    from sovereign_veritas.execution import ExecutionJournal, JournalCorrupt
    states = []
    for _ in range(2):  # restart: recovery happens inside submit (DISPATCHED/ACKNOWLEDGED are recovered, not redone)
        try:
            states.append(co.submit("payments", "client:alice", "invoice-7", {"op": "transfer", "amount": 100}, "sha256:auth"))
        except (JournalCorrupt, OSError) as exc:
            states.append(f"{type(exc).__name__}")
    j = ExecutionJournal(cfg["journal"])
    intent = j.intent_id("payments", "client:alice", "invoice-7")
    try:
        evs = j.events(intent)
    except JournalCorrupt:
        evs = None
    final = evs[-1]["to"] if evs else None
    # X4, as registered ("no DISPATCHED event before it"): every effect's attempt must have its own DISPATCHED event.
    # Deviation 1 (docs/EX1_RESULTS.md): the first version only asked whether any DISPATCHED event existed.
    dispatched_attempts = {e["detail"]["context"]["attempt_id"] for e in (evs or []) if e["to"] == "DISPATCHED"}
    effect_attempts = [json.loads(l)["attempt_id"] for l in open(cfg["world"]) if l.strip()] if os.path.exists(cfg["world"]) else []
    dispatched = all(a in dispatched_attempts for a in effect_attempts)
    return {"point": point, "fault": fault, "effects": world_effects(cfg), "final": final, "states": states,
            "dispatched_recorded": dispatched}


def baseline_workflow(tmp, crash_at):
    """X3: EvidenceWorkflow + FileReservations + FileLedger, killed after execute() at `crash_at`, then retried."""
    d = tempfile.mkdtemp(dir=tmp)
    world, ledger = os.path.join(d, "world.jsonl"), os.path.join(d, "ledger.jsonl")
    child = r"""
import json, os, sys
sys.path.insert(0, %r)
from sovereign_veritas.capability import Capability
from sovereign_veritas.evidence import LedgerSink
from sovereign_veritas.file_ledger import FileLedger
from sovereign_veritas.idempotency import FileReservations
from sovereign_veritas.interfaces.contracts import ActionProposal, Prediction
from sovereign_veritas.runtime import RuntimeState
from sovereign_veritas.workflow import EvidenceWorkflow
world, ledger, res, crash = sys.argv[1:5]
class S:
    def observe(self): return "o"
    def predict(self, o): return Prediction(value=1)
    def verify(self, o, p): return {"status": "PASS"}
class E:
    def execute(self, a):
        with open(world, "a") as fh:
            fh.write("effect\n"); fh.flush(); os.fsync(fh.fileno())
        if crash == "after_execute": os._exit(9)
        return "ok"
store = FileReservations(res)
if crash == "after_complete":
    orig = store.complete
    def complete(*a, **k):
        orig(*a, **k); os._exit(9)
    store.complete = complete
wf = EvidenceWorkflow(sensor=S(), predictor=S(), verifier=S(), executor=E(), evidence_sink=LedgerSink(FileLedger(ledger)),
                      reservations=store)
try:
    wf.run(record_id="r1", input_digest="d", capability=Capability("pay", authorized=True), runtime=RuntimeState("x", "3"),
           action=ActionProposal("pay", "transfer", {}), idempotency_key="invoice-7")
except Exception as exc:
    print(type(exc).__name__)
""" % ROOT
    args = [world, ledger, os.path.join(d, "res")]
    subprocess.run([sys.executable, "-c", child, *args, crash_at], capture_output=True, text=True)
    subprocess.run([sys.executable, "-c", child, *args, "none"], capture_output=True, text=True)  # the retry
    effects = sum(1 for l in open(world)) if os.path.exists(world) else 0
    records = sum(1 for l in open(ledger) if l.strip()) if os.path.exists(ledger) else 0
    return {"crash_at": crash_at, "effects": effects, "ledger_records": records}


def main():
    if shutil.which("ssh-keygen") is None:
        print("COULD NOT RUN: ssh-keygen not found")
        return 2
    sabotage = "--sabotage" in sys.argv
    tmp = tempfile.mkdtemp()
    key_path, signers = keys(tmp)
    rows = [run_case(tmp, key_path, signers, p, f, sabotage) for p in POINTS for f in FAULTS]
    for r in rows:
        print(f"  {r['point']:<38} {r['fault']:<8} effects={r['effects']} final={r['final']} "
              f"dispatched_recorded={r['dispatched_recorded']} restarts={r['states']}")
    x1 = all(r["effects"] <= 1 for r in rows)
    x2 = all(r["final"] in ADMITS_EFFECT for r in rows if r["effects"] >= 1)
    x4 = all(r["dispatched_recorded"] for r in rows if r["effects"] >= 1)
    x8_count = sum(1 for r in rows if r["effects"] == 0 and r["final"] == "EFFECT_UNCONFIRMED")
    base = [baseline_workflow(tmp, c) for c in ("after_execute", "after_complete")]
    for b in base:
        print(f"  baseline EvidenceWorkflow crash {b['crash_at']:<15} effects={b['effects']} ledger_records={b['ledger_records']}")
    x3 = sum(1 for b in base if b["effects"] >= 1 and b["ledger_records"] == 0) >= 1
    # X6: a lying executor (signed receipt, no effect), without and with an independent observer
    lie = {}
    for obs in (False, True):
        d = tempfile.mkdtemp(dir=tmp)
        cfg = {"root": ROOT, "journal": os.path.join(d, "j"), "world": os.path.join(d, "w.jsonl"), "key_path": key_path,
               "signers": signers, "key": "k", "lying": True, "observer": obs}
        lie[obs] = build(cfg).submit("payments", "client:alice", "k", {"op": "transfer", "amount": 100}, "sha256:auth")
    print(f"  lying executor: without observer -> {lie[False]}; with observer -> {lie[True]}")
    x6 = lie[False] == "EFFECT_ATTESTED" and lie[True] == "EFFECT_DISPUTED"
    verdicts = {"X1": x1, "X2": x2, "X3": x3, "X4": x4, "X6": x6, "X8": x8_count >= 1}
    print(f"  X8 faulted intents left EFFECT_UNCONFIRMED with no effect (liveness cost): {x8_count} of {len(rows)}")
    for k, v in verdicts.items():
        print(f"  {k}  {'HELD' if v else 'REFUTED'}")
    print(f"mode: {'SABOTAGE (executor before DISPATCHED)' if sabotage else 'registered'}")
    held = sum(verdicts.values())
    print(f"VERDICT  {held} of {len(verdicts)} as registered")
    shutil.rmtree(tmp, ignore_errors=True)
    return 0 if held == len(verdicts) else 1


if __name__ == "__main__":
    sys.exit(main())
