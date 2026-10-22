#!/usr/bin/env python3
"""KC-1 probe (registration: docs/KC1_PREREG.md, merged in PR #90 before this file existed).

A reused idempotency key with changed action parameters (a conflicting reuse) against a plain duplicate. Effects
are counted at the executor; the ledger sink and the reservation store are inspected before and after each attempt.
Every case runs twice: MemoryReservations, and FileReservations on a fresh temporary directory.

  python tools/kc1_probe.py                          exit 0 only if KC-P1, KC-P2, KC-P3 and KC-P7 all hold
  python tools/kc1_probe.py --mutant tagged-refusal  refusal message carries a per-call counter; KC-P2 must be REFUTED (exit 1)
  python tools/kc1_probe.py --mutant accept-all      reserve() never refuses; KC-P1 must be REFUTED (exit 1)
  python tools/kc1_probe.py --mutant digest-bound    stores bind a SHA-256 of the canonical decided action; KC-P2 must be
                                                     REFUTED for C1-C4 and KC-P7 must hold (exit 1)
Stdlib only. KC-P6 (regression) is run separately: the test suite.

Reading of KC-P7 (recorded in docs/KC1_RESULTS.md): refusal messages name the key, so "the same message as D1"
is taken as "the same message as the same-order duplicate on the same key" (D7 vs D7r on key K7).
"""
import hashlib
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.dont_write_bytecode = True

import execution_boundary_probe as xb  # noqa: E402
import sovereign_veritas.idempotency as idem  # noqa: E402
from sovereign_veritas.capability import Capability  # noqa: E402
from sovereign_veritas.evidence import Ledger, LedgerSink  # noqa: E402
from sovereign_veritas.idempotency import FileReservations, MemoryReservations  # noqa: E402
from sovereign_veritas.interfaces.contracts import ActionProposal  # noqa: E402
from sovereign_veritas.runtime import RuntimeState  # noqa: E402
from sovereign_veritas.workflow import EvidenceWorkflow  # noqa: E402

MUTANT = sys.argv[sys.argv.index("--mutant") + 1] if "--mutant" in sys.argv else None
if MUTANT not in (None, "tagged-refusal", "accept-all", "digest-bound"):
    sys.exit(f"unknown mutant {MUTANT!r}")

CAP = Capability("measure", True, ("fresh",))


def canonical(requested, parameters):
    return hashlib.sha256(json.dumps({"capability": "measure", "requested": requested, "parameters": parameters},
                                     sort_keys=True, separators=(",", ":")).encode()).hexdigest()


# ---- mutants (each patches the probe's own objects or the module's refusal builder; no file is edited) ----

if MUTANT == "tagged-refusal":
    _orig_refusal, _calls = idem._refusal, [0]

    def _tagged(key, state):
        _calls[0] += 1
        e = _orig_refusal(key, state)
        return type(e)(f"{e} [call {_calls[0]}]")
    idem._refusal = _tagged


def accept_all(cls):
    class AcceptAll(cls):
        def reserve(self, key, lease_s=idem.DEFAULT_LEASE_S):
            try:
                return super().reserve(key, lease_s)
            except idem.ReservationRefused:
                return "accept-all"   # MUTANT: refuses nothing
    return AcceptAll


def digest_bound(cls):
    class DigestBound(cls):
        """MUTANT (KC-P4b): a reservation remembers the digest of the decided action it was taken for; a later
        reserve under the same key with a different digest is refused as a conflicting reuse."""
        pending = None

        def reserve(self, key, lease_s=idem.DEFAULT_LEASE_S):
            bound = getattr(self, "_bound", None)
            if bound is None:
                bound = self._bound = {}
            try:
                token = super().reserve(key, lease_s)
            except idem.ReservationRefused as e:
                if key in bound and bound[key] != self.pending:
                    raise idem.ReservationRefused(f"idempotency key {key!r} conflicting reuse: decided action differs"
                                                  " from the one the key was reserved for: refused before execution") from None
                raise e
            bound[key] = self.pending
            return token
    return DigestBound


def make_store(kind, tmp):
    cls = MemoryReservations if kind == "memory" else FileReservations
    if MUTANT == "accept-all":
        cls = accept_all(cls)
    elif MUTANT == "digest-bound":
        cls = digest_bound(cls)
    return cls() if kind == "memory" else cls(os.path.join(tmp, "res"))


def attempt(sink, store, ex, rid, key, requested, params):
    if MUTANT == "digest-bound":
        store.pending = canonical(requested, params)
    w = EvidenceWorkflow(sensor=xb.Sensor(), predictor=xb.Predictor(), verifier=xb.Verifier(),
                         executor=ex, evidence_sink=sink, reservations=store)
    before_fx, before_rec = ex.effects, len(sink.ledger.all())
    before_hist, before_state = store.history(key), store.state(key)
    try:
        w.run(record_id=rid, input_digest="abc", capability=CAP,
              runtime=RuntimeState(platform="probe", python_version=sys.version.split()[0]),
              action=ActionProposal(capability="measure", requested=requested, parameters=dict(params)),
              metadata={"fresh": True}, idempotency_key=key)
        etype, emsg = None, None
    except Exception as exc:  # recorded, not judged here
        etype, emsg = type(exc).__name__, str(exc)
    return {"rid": rid, "key": key, "requested": requested, "params": params, "param_order": list(params),
            "effects_added": ex.effects - before_fx, "records_added": len(sink.ledger.all()) - before_rec,
            "exc_type": etype, "exc_msg": emsg, "state_before": before_state, "state_after": store.state(key),
            "history_changed": store.history(key) != before_hist}


def run_store(kind):
    with tempfile.TemporaryDirectory() as tmp:
        store, sink, ex = make_store(kind, tmp), LedgerSink(Ledger()), xb.CountingExecutor()
        a = {}
        # K0 sets the key up; D1/C1/C2 against COMPLETED
        a["K0"] = attempt(sink, store, ex, "r0", "K", "record_result", {"amount": 1})
        a["D1"] = attempt(sink, store, ex, "r1", "K", "record_result", {"amount": 1})
        a["C1"] = attempt(sink, store, ex, "r2", "K", "record_result", {"amount": 2})
        a["C2"] = attempt(sink, store, ex, "r3", "K", "record_other", {"amount": 1})
        # IN_FLIGHT: K2 reserved directly by a holder that took it for amount 1 and has not finished
        if MUTANT == "digest-bound":
            store.pending = canonical("record_result", {"amount": 1})
        store.reserve("K2", lease_s=60)
        a["D3"] = attempt(sink, store, ex, "r4", "K2", "record_result", {"amount": 1})
        a["C3"] = attempt(sink, store, ex, "r5", "K2", "record_result", {"amount": 2})
        # UNKNOWN: K3's first run (amount 1) raised in the executor
        a["K3setup"] = attempt(sink, store, xb.CountingExecutor(fail=True), "r6", "K3", "record_result", {"amount": 1})
        a["D4"] = attempt(sink, store, ex, "r7", "K3", "record_result", {"amount": 1})
        a["C4"] = attempt(sink, store, ex, "r8", "K3", "record_result", {"amount": 2})
        # KC-P7: key order in parameters
        a["K7"] = attempt(sink, store, ex, "r9", "K7", "record_result", {"a": 1, "b": 2})
        a["D7"] = attempt(sink, store, ex, "r10", "K7", "record_result", {"a": 1, "b": 2})
        a["D7r"] = attempt(sink, store, ex, "r11", "K7", "record_result", {"b": 2, "a": 1})
        k_records = [r for r in sink.ledger.all() if (r.metadata or {}).get("idempotency_key") == "K"]
        k_summary = [{"record_id": r.record_id, "parameters": dict((r.action or {}).get("parameters") or {})} for r in k_records]
        return a, k_summary


def main():
    held, lines = {}, []
    p1 = p2 = p3 = p7 = True
    per_pair = {}
    for kind in ("memory", "file"):
        a, k_summary = run_store(kind)
        for name, r in a.items():
            lines.append(f"{kind:6} {name:7} " + json.dumps(r, sort_keys=True))
        lines.append(f"{kind:6} K-records {json.dumps(k_summary, sort_keys=True)}")
        attempts = ["D1", "C1", "C2", "D3", "C3", "D4", "C4", "D7", "D7r"]
        p1 &= a["K0"]["effects_added"] == 1 and all(
            a[n]["effects_added"] == 0 and a[n]["exc_type"] == "ReservationRefused" for n in attempts)
        for c, d in (("C1", "D1"), ("C2", "D1"), ("C3", "D3"), ("C4", "D4")):
            same = (a[c]["exc_type"], a[c]["exc_msg"]) == (a[d]["exc_type"], a[d]["exc_msg"])
            per_pair[f"{kind}:{c}={d}"] = same
            p2 &= same
        p3 &= all(a[n]["records_added"] == 0 and not a[n]["history_changed"] for n in attempts) and \
            k_summary == [{"record_id": "r0", "parameters": {"amount": 1}}]
        p7 &= a["D7r"]["effects_added"] == 0 and (a["D7r"]["exc_type"], a["D7r"]["exc_msg"]) == \
            (a["D7"]["exc_type"], a["D7"]["exc_msg"])
    held = {"KC-P1": p1, "KC-P2": p2, "KC-P3": p3, "KC-P7": p7}
    for l in lines:
        print(l)
    print("\nmode:", MUTANT or "normal")
    print("KC-P2 pairs:", " ".join(f"{k}:{'same' if v else 'DIFFERENT'}" for k, v in per_pair.items()))
    for k, ok in held.items():
        print(f"  {k:6} {'HELD' if ok else 'REFUTED'}")
    n = sum(held.values())
    print(f"VERDICT  {n} of {len(held)} held (KC-P4/P4b/P5: run the mutants, each must exit 1; KC-P6: test suite)")
    return 0 if n == len(held) else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # a probe crash is not a verdict: exit 2, never 0 or 1
        import traceback
        traceback.print_exc()
        print(f"PROBE ERROR {type(exc).__name__}: {exc} (no verdict)")
        sys.exit(2)
