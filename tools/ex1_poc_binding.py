"""ex1_poc_binding.py - EX-1 fix 3 proof of concept (docs/EX1_RESULTS.md). Real ssh receipts; needs ssh-keygen.

Three direct callers of ExecutionJournal.append (an orchestrator other than ExecutionCoordinator, or a buggy one):
P1 a DISPATCHED context naming another command lets that command's receipt attest this intent (I6 at the journal level);
P2 a reused attempt id lets an old receipt attest a new attempt whose executor never ran; P3 AUTHORIZED with no decision.
Output before fix 3: results/ex1/poc_binding_prefix3.txt (all three ACCEPTED; this script had no exit code then).
Exit 0 iff all three are refused, 1 if any is accepted.

  python tools/ex1_poc_binding.py      # from the repository root
"""
import os, subprocess, sys, tempfile
sys.path.insert(0, os.getcwd()); sys.dont_write_bytecode = True
from sovereign_veritas import execution as ex
from sovereign_veritas.receipts import sign_receipt, verify_receipt

tmp = tempfile.mkdtemp()
key = os.path.join(tmp, "k")
subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "executor-1", "-f", key], check=True)
pub = open(key + ".pub").read().split()
signers = os.path.join(tmp, "signers")
open(signers, "w").write(f'executor-1 namespaces="sv-effect-receipt" {pub[0]} {pub[1]}\n')
verify = lambda r, ctx: verify_receipt(r, expected=ctx, allowed_signers=signers)

def receipt(ctx):
    r = {"schema": "sv.effect-receipt/1", "receipt_id": "r-" + ctx["attempt_id"], "executor_id": "executor-1",
         "executor_key_id": "executor-1", "effect_type": "transfer/1", "effect_result": "ATTESTED", "effect_reference": "ref",
         "observed_at": None, "prior_receipt_digest": None, **ctx}
    return sign_receipt(r, key)

C1, C2 = {"op": "transfer", "amount": 100}, {"op": "transfer", "amount": 999999}
accepted = []

print("P1: DISPATCHED context names another command (I6 at the journal level)")
j = ex.ExecutionJournal(os.path.join(tmp, "j1"), verify=verify)
intent, _ = j.reserve("payments", "client:alice", "invoice-7", C1, "coordinator")
j.append(intent, ex.AUTHORIZED, "coordinator", {"decision": "ALLOW", "authorization_digest": "sha256:auth"}, attempt_id="a1")
ctx2 = {"record_id": intent, "attempt_id": "a1", "command_digest": ex.digest(C2), "authorization_digest": "sha256:auth"}
try:
    j.append(intent, ex.DISPATCHED, "coordinator", {"context": ctx2})
    j.append(intent, ex.ACKNOWLEDGED, "coordinator", {"receipt": receipt(ctx2)})
    j.append(intent, ex.ATTESTED, "coordinator", {"receipt": receipt(ctx2)})
    evs = j.events(intent)
    print(f"  ACCEPTED: reserved for {evs[0]['detail']['command_digest'][:23]}..., final {evs[-1]['to']} by a receipt for "
          f"{ctx2['command_digest'][:23]}...")
    accepted.append("P1")
except ex.IllegalTransition as e:
    print(f"  refused: {e}")

print("P2: a reused attempt id lets an old receipt attest a new attempt whose executor never ran")
j = ex.ExecutionJournal(os.path.join(tmp, "j2"), verify=verify)
intent, _ = j.reserve("payments", "client:alice", "invoice-8", C1, "coordinator")
ctx = {"record_id": intent, "attempt_id": "a1", "command_digest": ex.digest(C1), "authorization_digest": "sha256:auth"}
old = receipt(ctx)
j.append(intent, ex.AUTHORIZED, "coordinator", {"decision": "ALLOW", "authorization_digest": "sha256:auth"}, attempt_id="a1")
j.append(intent, ex.DISPATCHED, "coordinator", {"context": ctx})
j.append(intent, ex.ACKNOWLEDGED, "coordinator", {"receipt": old})
j.append(intent, ex.ATTESTED, "coordinator", {"receipt": old})
j.append(intent, ex.DISPUTED, "observer:independent", {"basis": "observer saw no effect"})
j.append(intent, ex.NO_EFFECT, "human:operator", {"basis": "bank shows no transfer"})
try:
    j.append(intent, ex.AUTHORIZED, "coordinator", {"decision": "ALLOW", "authorization_digest": "sha256:auth"}, attempt_id="a1")
    j.append(intent, ex.DISPATCHED, "coordinator", {"context": ctx})   # the new attempt; suppose its executor never runs
    j.append(intent, ex.UNCONFIRMED, "coordinator", {"why": "executor unreachable"})
    co = ex.ExecutionCoordinator(j, decide=lambda c: ("ALLOW", []), executor=None, verify=verify)
    print(f"  replayed old receipt -> {co.accept_receipt(intent, old)} (attempt ids used: "
          f"{[e['attempt_id'] for e in j.events(intent) if e['to'] == ex.AUTHORIZED]})")
    accepted.append("P2")
except ex.IllegalTransition as e:
    print(f"  refused: {e}")

print("P3: AUTHORIZED with no decision at all")
j = ex.ExecutionJournal(os.path.join(tmp, "j3"), verify=verify)
intent, _ = j.reserve("payments", "client:alice", "invoice-9", C1, "coordinator")
try:
    j.append(intent, ex.AUTHORIZED, "anyone")
    print(f"  ACCEPTED: AUTHORIZED by 'anyone' with detail {j.events(intent)[-1]['detail']}")
    accepted.append("P3")
except ex.IllegalTransition as e:
    print(f"  refused: {e}")
print(f"VERDICT  {'accepted: ' + ', '.join(accepted) if accepted else 'all three refused'}")
sys.exit(1 if accepted else 0)
