#!/usr/bin/env python3
"""ex1_receipts.py - EX-1 X5: receipts that must never attest (docs/EX1_PREREG.md). Real ssh-keygen signatures.

Registered cases: missing (I5), another command's (I6), another authorization's (I7), another attempt's, wrong namespace,
unknown key. Each is checked twice: by receipts.verify_receipt, and by ExecutionJournal.append(EFFECT_ATTESTED) with that
verifier (the enforcement point since fix 2). A valid receipt must attest through both (the positive control: without it,
"never attests" could mean "nothing ever attests").

  python tools/ex1_receipts.py            # exit 0 iff the control attests and no registered case does
  python tools/ex1_receipts.py --sabotage # the journal's verifier accepts anything: the cases must attest -> exit 1
"""
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.dont_write_bytecode = True

from sovereign_veritas import execution as ex  # noqa: E402
from sovereign_veritas import receipts  # noqa: E402

CMD, OTHER, AUTH = {"op": "transfer", "amount": 100}, {"op": "transfer", "amount": 999999}, "sha256:auth"
CASES = ["missing", "other_command", "other_authorization", "other_attempt", "wrong_namespace", "unknown_key"]


def keygen(d, name):
    path = os.path.join(d, name)
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", name, "-f", path], check=True)
    return path


def make(ctx, key, tmp, case="valid"):
    if case == "missing":
        return None
    field = {"other_command": ("command_digest", ex.digest(OTHER)), "other_authorization": ("authorization_digest", "x"),
             "other_attempt": ("attempt_id", "a-other")}.get(case)
    body = {"schema": receipts.SCHEMA, "receipt_id": "r1", "executor_id": "executor-1", "executor_key_id": "executor-1",
            "effect_type": "transfer/1", "effect_result": "ATTESTED", "effect_reference": "bank-ref", "observed_at": None,
            "prior_receipt_digest": None, **ctx}
    if field:
        body[field[0]] = field[1]
    if case == "wrong_namespace":  # the executor's own key, but the package namespace
        f = os.path.join(tmp, "body")
        with open(f, "wb") as fh:
            fh.write(receipts.body_bytes(body))
        if os.path.exists(f + ".sig"):
            os.remove(f + ".sig")
        subprocess.run(["ssh-keygen", "-Y", "sign", "-f", key["executor-1"], "-n", "sv-package", f], check=True,
                       capture_output=True)
        return dict(body, signature=open(f + ".sig").read())
    return receipts.sign_receipt(body, key["stranger" if case == "unknown_key" else "executor-1"])


def main(argv):
    if shutil.which("ssh-keygen") is None:
        print("COULD NOT RUN: ssh-keygen not found")
        return 2
    sabotage = "--sabotage" in argv
    tmp = tempfile.mkdtemp()
    try:
        key = {n: keygen(tmp, n) for n in ("executor-1", "stranger")}
        pub = open(key["executor-1"] + ".pub").read().split()
        signers = os.path.join(tmp, "signers")  # unscoped on purpose: the namespace must be enforced by the signature
        with open(signers, "w") as fh:
            fh.write(f"executor-1 {pub[0]} {pub[1]}\n")

        def verify(r, ctx):
            if sabotage:
                return True, "EFFECT_ATTESTED", []
            return receipts.verify_receipt(r, expected=ctx, allowed_signers=signers)

        rows = []
        for case in ["valid"] + CASES:
            j = ex.ExecutionJournal(os.path.join(tmp, "j-" + case), verify=verify)
            intent, _ = j.reserve("payments", "client:alice", "invoice-7", CMD, "coordinator")
            ctx = {"record_id": intent, "attempt_id": "a1", "command_digest": ex.digest(CMD), "authorization_digest": AUTH}
            j.append(intent, ex.AUTHORIZED, "coordinator", {"decision": "ALLOW", "authorization_digest": AUTH}, attempt_id="a1")
            j.append(intent, ex.DISPATCHED, "coordinator", {"context": ctx})
            j.append(intent, ex.UNCONFIRMED, "coordinator", {"why": "receipt awaited"})
            r = make(ctx, key, tmp, case)
            direct = "n/a (no receipt)" if r is None else verify(r, ctx)[1]
            try:
                j.append(intent, ex.ATTESTED, "coordinator", {} if r is None else {"receipt": r})
                journal = ex.ATTESTED
            except ex.IllegalTransition as exc:
                journal = f"refused ({str(exc)[:60]})"
            rows.append((case, direct, journal))
            print(f"  {case:<20} verify_receipt -> {direct:<18} journal -> {journal}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    control = rows[0][1] == ex.ATTESTED and rows[0][2] == ex.ATTESTED
    attested = [c for c, d, jr in rows[1:] if d == ex.ATTESTED or jr == ex.ATTESTED]
    print(f"  positive control (valid receipt attests through both): {'yes' if control else 'NO'}")
    print(f"mode: {'SABOTAGE (verifier accepts anything)' if sabotage else 'registered'}")
    if not control:
        print("VERDICT  NOT ESTABLISHED: the valid receipt did not attest, so 'never attests' would be vacuous")
        return 1
    print(f"VERDICT  X5 {'HELD: none of 6 registered cases attests' if not attested else 'REFUTED: ' + ', '.join(attested)}")
    return 0 if not attested else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
