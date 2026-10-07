#!/usr/bin/env python3
"""ex1_test_mutants.py - can tests/test_execution.py fail? (EX-1, docs/EX1_RESULTS.md; method from tools/verifier_mutants.py)

Each mutant re-plants one EX-1 defect (or removes one guard) in a temporary copy of sovereign_veritas/execution.py and runs
tests/test_execution.py there. A mutant must make at least one test fail (KILLED). A mutant declared EQUIVALENT must
survive, because another rule defends the same property, and its witness (the same mutant plus that other rule removed)
must be KILLED: an equivalence claim has to be shown, not asserted.

  python tools/ex1_test_mutants.py     # exit 0 iff every mutant is killed and every equivalence has a killed witness
"""
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = "sovereign_veritas/execution.py"
EDGE = ('    REFUSED: frozenset(),', '    REFUSED: frozenset({DISPATCHED}),')
NO_DISPATCH_RULE = ('    if to == DISPATCHED:\n        auth = evs[-1]', '    if False:\n        auth = evs[-1]')
MUTANTS = {
  "fix3-authorized-off": ('    if to == AUTHORIZED:\n        if detail.get("decision") != "ALLOW":', '    if False:\n        if detail.get("decision") != "ALLOW":'),
  "fix3-attempt-reuse-off": ('        if any(e["to"] == AUTHORIZED and e["attempt_id"] == attempt_id for e in evs):', '        if False:'),
  "fix3-dispatch-binding-off": ('        if detail.get("context") != want:', '        if False:'),
  "fix3-ack-receipt-off": ('    if to == ACKNOWLEDGED and detail.get("receipt") is None:', '    if False:'),
  "fix2-attestation-off": ('        if self.verify is None:\n            raise IllegalTransition("EFFECT_ATTESTED needs a receipt verifier; none is configured")', '        return\n        if self.verify is None:\n            raise IllegalTransition("EFFECT_ATTESTED needs a receipt verifier; none is configured")'),
  "fix2+3-attest-binding-off": ('        if any(receipt.get(k) != ctx.get(k) for k in CONTEXT_KEYS):', '        if False:'),
  "fix1-actor-off": ('        if not (isinstance(actor, str) and actor.startswith(OBSERVER_ACTORS)):', '        if False:'),
  "basis-off": ('        if not _nonempty(detail.get("basis")):', '        if False:'),
  "finalized-free": ('NEEDS_BASIS = frozenset({CONFIRMED, NO_EFFECT, DISPUTED, FINALIZED})', 'NEEDS_BASIS = frozenset({CONFIRMED, NO_EFFECT, DISPUTED})'),
  "read-admit-off": ('            if why:\n                raise JournalCorrupt(f"{intent[:12]} line {n}: inadmissible event on disk: {why}")', '            pass'),
  "read-intent-off": ('            if ev.get("schema") != EVENT_SCHEMA or ev.get("intent") != intent:', '            if False:'),
  "table-edge-added": [EDGE],
  "table-edge+dispatch-rule-off": [EDGE, NO_DISPATCH_RULE],
  "chain-off": ('            if ev.get("prev_event_digest") != prev or ev.get("seq") != n or ev.get("from") != state:', '            if False:'),
  "digest-off": ('            if ev.get("event_digest") != digest(body):', '            if False:'),
  "torn-off": ('        if raw and not raw.endswith(b"\\n"):', '        if False:'),
  "reserve-overwrites": ('                os.link(tmp, path)', '                os.replace(tmp, path)'),
  "append-creates": ('        if to == RESERVED or not self.path(intent).exists():', '        if False:'),
  "no-lock": ('        if fcntl is not None:\n            fcntl.flock(self.fd, fcntl.LOCK_EX)', '        if fcntl is not None:\n            pass'),
  "recover-redispatch": ('        if state in (DISPATCHED, ACKNOWLEDGED):\n            return self.recover(intent)\n        if state not in (RESERVED, DEFERRED, AUTHORIZED, NO_EFFECT):', '        if state == ACKNOWLEDGED:\n            return self.recover(intent)\n        if state not in (RESERVED, DEFERRED, AUTHORIZED, NO_EFFECT, DISPATCHED):'),
  "dispatch-after-execute": ('        self.j.append(intent, DISPATCHED, self.actor, {"context": ctx})  # write-ahead: durable before the executor runs\n        self.fault("before_execute")\n        try:\n            receipt = self.executor.execute(command, ctx)', '        self.fault("before_execute")\n        try:\n            receipt = self.executor.execute(command, ctx)\n            self.j.append(intent, DISPATCHED, self.actor, {"context": ctx})'),
  "raise-is-no-effect": ('            self.j.append(intent, UNCONFIRMED, self.actor, {"why": f"executor raised {type(exc).__name__}: {exc}"})\n            return UNCONFIRMED', '            self.j.append(intent, UNCONFIRMED, self.actor, {"why": f"executor raised {type(exc).__name__}: {exc}"})\n            self.j.append(intent, NO_EFFECT, "human:auto", {"basis": "executor raised"})\n            return NO_EFFECT'),
  "late-receipt-any-state": ('        if state != UNCONFIRMED:\n            return state\n        ctx = next', '        if state in (REFUSED, None):\n            return state\n        ctx = next'),
  "observer-ignored": ('        if seen is False and state == ATTESTED:', '        if False:'),
}
# name -> (why it survives, its witness)
EQUIVALENT = {"table-edge-added": ("fix 3: a DISPATCHED needs an AUTHORIZED event just before it to bind to",
                                   "table-edge+dispatch-rule-off")}


def run(name, edits, base):
    for old, _ in edits:
        if base.count(old) != 1:
            return f"NOT APPLIED (pattern count {base.count(old)}: {old[:40]!r})"
    text = base
    for old, new in edits:
        text = text.replace(old, new)
    d = tempfile.mkdtemp()
    try:
        for item in ("sovereign_veritas", "tests"):
            shutil.copytree(os.path.join(ROOT, item), os.path.join(d, item), ignore=shutil.ignore_patterns("__pycache__"))
        with open(os.path.join(d, SRC), "w", encoding="utf-8") as fh:
            fh.write(text)
        p = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", "tests/test_execution.py"],
                           cwd=d, capture_output=True, text=True,
                           env=dict(os.environ, PYTHONPATH=d, PYTHONDONTWRITEBYTECODE="1"))
    finally:
        shutil.rmtree(d, ignore_errors=True)
    last = (p.stdout.strip().splitlines() or ["?"])[-1]
    return ("KILLED  " if p.returncode == 1 else "SURVIVED" if p.returncode == 0 else f"ERROR rc={p.returncode}") + "  " + last


def main():
    with open(os.path.join(ROOT, SRC), encoding="utf-8") as fh:
        base = fh.read()
    results = {name: run(name, edits if isinstance(edits, list) else [edits], base) for name, edits in MUTANTS.items()}
    for k, v in results.items():
        note = f"   EQUIVALENT ({EQUIVALENT[k][0]}); witness: {EQUIVALENT[k][1]}" if k in EQUIVALENT else ""
        print(f"  {k:<32} {v}{note}")
    bad = [k for k, v in results.items() if not v.startswith("KILLED") and k not in EQUIVALENT]
    bad += [k for k, (_, w) in EQUIVALENT.items() if not results[k].startswith("SURVIVED") or not results[w].startswith("KILLED")]
    killed = sum(v.startswith("KILLED") for v in results.values())
    print(f"VERDICT  {killed} of {len(results)} killed; {len(EQUIVALENT)} declared equivalent with a killed witness"
          if not bad else f"VERDICT  NOT ESTABLISHED: {', '.join(bad)}")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
