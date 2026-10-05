# vacuity-lint: intentional - "FAILED" here is a status this system reports to the harness, not a check result; the comparator (tools/obs1_compare.py) does the checking
"""OBS-1 system under test (registration docs/OBS1_PREREG.md).

sovereign-veritas's own Gate and RK-3 reservation store, driving the OBS-1 sandbox store through a StoreClient
(set_value, fence, read; nothing else). Per attempt:

1. write ahead the attempt's token in the system's journal for the intent;
2. re-read write permission at execution (never reuse the approval-time answer);
3. if the intent's key shows an earlier attempt, try automated reconciliation: fence every earlier token, then
   read; resolved only if the read is ok and shows no write by a fenced token;
4. the Gate decides, with `prior_outcome_resolved` as required evidence, so an unresolved earlier attempt is
   DEFER (reported HELD) and revoked permission is REFUSE, by the kernel's existing rules;
5. on ALLOW: reserve the key, write, and report what the store said.

sabotage (controls only, docs/OBS1_PREREG.md P8/P9): "no-reconcile" retries without fence or read;
"stale-permission" uses the approval-time permission instead of re-reading it.
"""
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from obs1_store import StoreTimeout  # noqa: E402
from sovereign_veritas.capability import Capability  # noqa: E402
from sovereign_veritas.decision import Gate  # noqa: E402
from sovereign_veritas.evidence import EvidenceRecord  # noqa: E402
from sovereign_veritas.idempotency import COMPLETED, FileReservations  # noqa: E402
from sovereign_veritas.runtime import RuntimeState  # noqa: E402


class PermissionSource:
    """Set by the harness before each attempt; read by the system. The system cannot change it."""

    def __init__(self):
        self._write, self._fence = False, False

    def _set(self, write, fence):  # harness only
        self._write, self._fence = bool(write), bool(fence)

    def write_granted(self):
        return self._write

    def fence_granted(self):
        return self._fence


class System:
    def __init__(self, state_dir, store, permissions, sabotage=None):
        self.store, self.perm, self.sabotage = store, permissions, sabotage
        os.makedirs(state_dir, exist_ok=True)
        self.res = FileReservations(os.path.join(state_dir, "reservations"))
        self.journal_path = os.path.join(state_dir, "journal.json")
        self.gate = Gate()

    def _journal(self):
        if not os.path.exists(self.journal_path):
            return {}
        with open(self.journal_path, encoding="utf-8") as fh:
            return json.load(fh)

    def _journal_add(self, intent_id, token):
        j = self._journal()
        j.setdefault(intent_id, []).append(token)
        tmp = self.journal_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(j, fh, sort_keys=True)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, self.journal_path)

    def attempt(self, case_id, attempt_no, intent, approval, token):
        key, rid = intent["idempotency_key"], intent["record_id"]
        self._journal_add(intent["intent_id"], token)  # written ahead of any store call
        if self.sabotage == "stale-permission":
            perm = "GRANTED" if approval.get("granted") is True else "REVOKED"
        else:
            perm = "GRANTED" if self.perm.write_granted() else "REVOKED"

        resolved, already, recon, why = True, False, None, None
        state = self.res.state(key)
        if state == COMPLETED:
            already = True
        elif state is not None:
            earlier = [t for t in self._journal()[intent["intent_id"]] if t != token]
            if self.sabotage == "no-reconcile":
                self.res.release(key, by="system", reason="sabotage: no reconciliation")
            elif not self.perm.fence_granted():
                resolved, why = False, "unresolved_prior_attempt:no_fence_permission"
            else:
                for t in earlier:
                    self.store.fence(t, token)
                r = self.store.read(rid, token)
                if r["result"] != "ok":
                    resolved, why = False, "unresolved_prior_attempt:observation_unavailable"
                else:
                    n = sum(1 for e in r["events"] if e.get("event") == "write" and e.get("attempt_token") in earlier)
                    recon = {"fenced_tokens": earlier, "observed_at_seq": r["seq"], "observed_writes_by_fenced": n,
                             "by": "system"}
                    if n > 0:
                        already = True
                    else:
                        self.res.release(key, by="system", reason=f"reconciled: fenced {earlier}, read seq {r['seq']}")

        evidence = EvidenceRecord(
            record_id=f"{case_id}-{attempt_no}", input_digest=hashlib.sha256(
                json.dumps(intent, sort_keys=True).encode("utf-8")).hexdigest(),
            verification={"status": "PASS"}, action={"capability": "set_value", "requested": "set_value"},
            metadata={"prior_outcome_resolved": resolved})
        cap = Capability("set_value", authorized=(perm == "GRANTED"), required_evidence=("prior_outcome_resolved",))
        d = self.gate.evaluate(evidence, cap, RuntimeState(platform="obs1", python_version=sys.version.split()[0]),
                               policy={"allow_only": ["set_value"]})

        def report(status, reason, reconciliation=None):
            return {"case_id": case_id, "attempt": attempt_no, "permission_at_execution": perm,
                    "decision": d.decision, "system_status": status, "reason": reason,
                    "reconciliation": reconciliation}

        if d.decision == "REFUSE":
            return report("REFUSED", ";".join(d.reasons))
        if d.decision == "DEFER":
            return report("HELD", why or ";".join(d.reasons))
        if already:
            return report("ALREADY_COMPLETED", "earlier_attempt_completed", recon)

        holder = self.res.reserve(key)
        try:
            out = self.store.set_value(rid, intent["new_value"], token)
        except StoreTimeout:
            self.res.unknown(key, "reply lost", token=holder)
            return report("UNKNOWN", "reply_lost_after_set_value", recon)
        if out["result"] == "ok":
            self.res.complete(key, token=holder)
            return report("COMPLETED", None, recon)
        self.res.unknown(key, f"store rejected: {out['reason']}", token=holder)
        self.res.release(key, by="system", reason="store confirmed the write was rejected")
        return report("FAILED", f"store_rejected:{out['reason']}", recon)
