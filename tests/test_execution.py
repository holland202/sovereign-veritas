"""EX-1 regression tests: sovereign_veritas/execution.py and receipts.py (docs/EX1_PREREG.md, docs/EX1_RESULTS.md).

These pin what the campaign, the fuzzer and the proofs of concept observed; the evidence for X1-X8 is results/ex1/, not this
file. Most tests use a named stand-in verifier (structure and binding as receipts.py, signature "ok"); the X5 tests use real
ssh-keygen signatures and skip without it, except the one that checks a missing ssh-keygen fails closed.
"""
import json
import os
import shutil
import subprocess
import sys
import time

import pytest

from sovereign_veritas import execution as ex
from sovereign_veritas import receipts
from sovereign_veritas.receipts import BINDING, problems

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CMD = {"op": "transfer", "amount": 100}
OTHER = {"op": "transfer", "amount": 999999}
AUTH = "sha256:auth"
needs_ssh = pytest.mark.skipif(shutil.which("ssh-keygen") is None, reason="ssh-keygen not installed")


def stand_in_verify(receipt, expected):
    """Named stand-in for receipts.verify_receipt: real structure and binding rules, signature must equal "ok"."""
    found = problems(receipt)
    if found:
        return False, ex.UNCONFIRMED, found
    if receipt["signature"] != "ok":
        return False, ex.UNCONFIRMED, ["signature"]
    bad = [k for k in BINDING if receipt[k] != expected.get(k)]
    if bad:
        return False, ex.UNCONFIRMED, bad
    ok = receipt["effect_result"] == "ATTESTED"
    return ok, ex.ATTESTED if ok else ex.UNCONFIRMED, []


def receipt(ctx, result="ATTESTED", sig="ok", **over):
    r = {"schema": receipts.SCHEMA, "receipt_id": "r-" + ctx["attempt_id"], "executor_id": "executor-1",
         "executor_key_id": "executor-1", "effect_type": "transfer/1", "effect_result": result, "effect_reference": "ref",
         "observed_at": None, "prior_receipt_digest": None, **{k: ctx[k] for k in BINDING}}
    r.update(over)
    r["signature"] = sig
    return r


class Executor:
    def __init__(self, mode="ok"):
        self.mode, self.calls = mode, []

    def execute(self, command, ctx):
        self.calls.append(ctx)
        if self.mode == "raise":
            raise TimeoutError("response lost")
        if self.mode == "none":
            return None
        return receipt(ctx, "FAILED" if self.mode == "failed" else "ATTESTED")


class Crash(BaseException):
    pass


def crash_at(point, exc=Crash):
    def fault(p):
        if p == point:
            raise exc(p)
    return fault


def coordinator(tmp_path, decision="ALLOW", executor=None, observer=None, fault=None, verify=stand_in_verify):
    j = ex.ExecutionJournal(tmp_path / "journal", fault=fault)
    return ex.ExecutionCoordinator(j, decide=lambda c: (decision, ["test"]), executor=executor or Executor(),
                                   verify=verify, observer=observer, fault=fault), j


def submit(co, command=CMD):
    return co.submit("payments", "client:alice", "invoice-7", command, AUTH)


def authorized(j, attempt="a1", command=CMD):
    """A journal brought to AUTHORIZED by hand; returns (intent, the context a correct dispatch must carry)."""
    intent, _ = j.reserve("payments", "client:alice", "invoice-7", command, "coordinator")
    j.append(intent, ex.AUTHORIZED, "coordinator", {"decision": "ALLOW", "authorization_digest": AUTH}, attempt_id=attempt)
    return intent, {"record_id": intent, "attempt_id": attempt, "command_digest": ex.digest(command),
                    "authorization_digest": AUTH}


def unconfirmed(j, attempt="a1"):
    intent, ctx = authorized(j, attempt)
    j.append(intent, ex.DISPATCHED, "coordinator", {"context": ctx})
    j.append(intent, ex.UNCONFIRMED, "coordinator", {"why": "test"})
    return intent, ctx


def test_context_keys_are_the_receipt_binding():
    assert ex.CONTEXT_KEYS == receipts.BINDING


# --- reservation ------------------------------------------------------------------------------------------------------

def test_reserve_is_exclusive_and_a_different_command_conflicts(tmp_path):
    j = ex.ExecutionJournal(tmp_path)
    assert j.reserve("payments", "client:alice", "k", CMD, "c")[1] is True
    assert j.reserve("payments", "client:alice", "k", CMD, "c")[1] is False
    with pytest.raises(ex.ConflictingIntent):
        j.reserve("payments", "client:alice", "k", OTHER, "c")


CHILD = r"""
import sys, time
sys.path.insert(0, sys.argv[1])
from sovereign_veritas.execution import ExecutionJournal, ConflictingIntent
j, t0 = ExecutionJournal(sys.argv[2]), float(sys.argv[3])
while time.time() < t0:
    pass
try:
    print(j.reserve("payments", "client:alice", "k", {"op": "transfer", "amount": int(sys.argv[4])}, "c")[1])
except ConflictingIntent:
    print("conflict")
"""


def test_concurrent_reservers_have_exactly_one_winner(tmp_path):
    t0 = time.time() + 3
    procs = [subprocess.Popen([sys.executable, "-c", CHILD, ROOT, str(tmp_path), str(t0), str(100 + 100 * (i % 2))],
                              stdout=subprocess.PIPE, text=True) for i in range(8)]
    out = [p.communicate(timeout=60)[0].strip() for p in procs]
    assert out.count("True") == 1, out
    winner = 100 + 100 * (out.index("True") % 2)
    j = ex.ExecutionJournal(tmp_path)
    intent = j.intent_id("payments", "client:alice", "k")
    assert j.events(intent)[0]["detail"]["command_digest"] == ex.digest({"op": "transfer", "amount": winner})
    for i, o in enumerate(out):  # losers with the winner's command see a reservation; the others a conflict
        if o != "True":
            assert o == ("False" if 100 + 100 * (i % 2) == winner else "conflict"), (i, out)


CHILD_SUBMIT = r"""
import json, os, sys, time
sys.path.insert(0, sys.argv[1])
from sovereign_veritas import execution as ex
d, world, t0 = sys.argv[2], sys.argv[3], float(sys.argv[4])
class E:
    def execute(self, command, ctx):
        with open(world, "a") as fh:
            fh.write(json.dumps(ctx) + "\n"); fh.flush(); os.fsync(fh.fileno())
        return None
co = ex.ExecutionCoordinator(ex.ExecutionJournal(d), decide=lambda c: ("ALLOW", []), executor=E(),
                             verify=lambda r, ctx: (False, "EFFECT_UNCONFIRMED", ["unused"]))
while time.time() < t0:
    pass
try:
    print(co.submit("payments", "client:alice", "invoice-7", {"op": "transfer", "amount": 100}, "sha256:auth"))
except (ex.IllegalTransition, ex.JournalCorrupt) as exc:
    print(type(exc).__name__)
"""


def test_concurrent_submitters_cause_one_effect_and_a_valid_journal(tmp_path):
    """Appends re-read the journal under the lock, and a dispatch must bind the latest authorization: one effect, no fork."""
    world, t0 = tmp_path / "world.jsonl", time.time() + 3
    procs = [subprocess.Popen([sys.executable, "-c", CHILD_SUBMIT, ROOT, str(tmp_path / "j"), str(world), str(t0)],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(6)]
    out = [p.communicate(timeout=60) for p in procs]
    assert all(not err for _, err in out), [err for _, err in out]
    assert len(world.read_text().splitlines()) == 1, [o for o, _ in out]
    j = ex.ExecutionJournal(tmp_path / "j")
    evs = j.events(j.intent_id("payments", "client:alice", "invoice-7"))
    assert [e["to"] for e in evs].count(ex.DISPATCHED) == 1


def test_a_crash_before_publishing_leaves_no_reservation(tmp_path):
    j = ex.ExecutionJournal(tmp_path, fault=crash_at("before_reserve_publish"))
    with pytest.raises(Crash):
        j.reserve("payments", "client:alice", "k", CMD, "c")
    assert os.listdir(tmp_path) == []  # neither the journal nor its temporary file
    assert ex.ExecutionJournal(tmp_path).reserve("payments", "client:alice", "k", OTHER, "c")[1] is True


def test_append_never_creates_a_journal(tmp_path):
    j = ex.ExecutionJournal(tmp_path)
    intent = j.intent_id("payments", "client:alice", "k")
    for to in (ex.RESERVED, ex.AUTHORIZED, ex.REFUSED):
        with pytest.raises(ex.IllegalTransition):
            j.append(intent, to, "c", {"decision": "ALLOW", "authorization_digest": AUTH}, attempt_id="a1")
    assert not j.path(intent).exists()


# --- I1 / I2 ----------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("decision,state", [("REFUSE", ex.REFUSED), ("DEFER", ex.DEFERRED), ("garbage", ex.REFUSED)])
def test_refused_and_deferred_never_dispatch(tmp_path, decision, state):
    e = Executor()
    co, j = coordinator(tmp_path, decision=decision, executor=e)
    assert submit(co) == state
    assert e.calls == []
    intent = j.intent_id("payments", "client:alice", "invoice-7")
    ctx = {"record_id": intent, "attempt_id": "a1", "command_digest": ex.digest(CMD), "authorization_digest": AUTH}
    with pytest.raises(ex.IllegalTransition):
        j.append(intent, ex.DISPATCHED, "coordinator", {"context": ctx}, attempt_id="a1")


# --- fix 3: the journal enforces each transition's evidence -----------------------------------------------------------

@pytest.mark.parametrize("change", [
    {"record_id": "0" * 64}, {"attempt_id": "a2"}, {"command_digest": ex.digest(OTHER)}, {"authorization_digest": "sha256:x"},
    {"extra": "field"}, None])
def test_dispatch_must_bind_intent_attempt_command_and_authorization(tmp_path, change):
    j = ex.ExecutionJournal(tmp_path)
    intent, ctx = authorized(j)
    detail = {} if change is None else {"context": dict(ctx, **change)}
    with pytest.raises(ex.IllegalTransition):
        j.append(intent, ex.DISPATCHED, "coordinator", detail)
    j.append(intent, ex.DISPATCHED, "coordinator", {"context": ctx})  # the exact binding is accepted
    assert j.state(intent) == ex.DISPATCHED


def test_dispatch_carries_the_authorized_attempt_id(tmp_path):
    j = ex.ExecutionJournal(tmp_path)
    intent, ctx = authorized(j)
    with pytest.raises(ex.IllegalTransition):
        j.append(intent, ex.DISPATCHED, "coordinator", {"context": ctx}, attempt_id="a2")


def test_an_attempt_id_cannot_be_authorized_twice(tmp_path):
    """P2: a reused attempt id let an old receipt attest a new attempt whose executor never ran."""
    j = ex.ExecutionJournal(tmp_path, verify=stand_in_verify)
    intent, ctx = unconfirmed(j, "a1")
    j.append(intent, ex.NO_EFFECT, "human:operator", {"basis": "bank shows no transfer"})
    with pytest.raises(ex.IllegalTransition, match="already authorized"):
        j.append(intent, ex.AUTHORIZED, "coordinator", {"decision": "ALLOW", "authorization_digest": AUTH}, attempt_id="a1")
    j.append(intent, ex.AUTHORIZED, "coordinator", {"decision": "ALLOW", "authorization_digest": AUTH}, attempt_id="a2")


@pytest.mark.parametrize("detail,attempt", [
    ({}, "a1"), ({"decision": "DEFER", "authorization_digest": AUTH}, "a1"), ({"decision": "ALLOW"}, "a1"),
    ({"decision": "ALLOW", "authorization_digest": ""}, "a1"), ({"decision": "ALLOW", "authorization_digest": AUTH}, None)])
def test_authorized_needs_allow_an_authorization_digest_and_an_attempt(tmp_path, detail, attempt):
    """P3: AUTHORIZED was accepted with no decision at all."""
    j = ex.ExecutionJournal(tmp_path)
    intent, _ = j.reserve("payments", "client:alice", "k", CMD, "c")
    with pytest.raises(ex.IllegalTransition):
        j.append(intent, ex.AUTHORIZED, "anyone", detail, attempt_id=attempt)


def test_acknowledged_needs_a_receipt_so_recovery_cannot_crash(tmp_path):
    """The fuzzer's KeyError: a receipt-less EXECUTOR_ACKNOWLEDGED crashed recover(). It can no longer be written."""
    e = Executor()
    co, j = coordinator(tmp_path, executor=e, fault=crash_at("after_append:DISPATCHED"))
    with pytest.raises(Crash):
        submit(co)
    intent = j.intent_id("payments", "client:alice", "invoice-7")
    with pytest.raises(ex.IllegalTransition):
        j.append(intent, ex.ACKNOWLEDGED, "fuzz", {"basis": "fuzz"})
    co, _ = coordinator(tmp_path, executor=e)
    assert submit(co) == ex.UNCONFIRMED and e.calls == []


def _line(intent, evs, to, detail, attempt=None, actor="x"):
    """An event with a correct digest chain, written by hand (an attacker or an older writer)."""
    prev = evs[-1] if evs else None
    body = {"schema": ex.EVENT_SCHEMA, "intent": intent, "seq": len(evs), "from": prev["to"] if prev else None, "to": to,
            "attempt_id": attempt, "actor": actor, "contract_version": ex.CONTRACT_VERSION,
            "command_digest": ex.digest(CMD), "prev_event_digest": prev["event_digest"] if prev else None,
            "at": {"value": "t", "source": "test"}, "detail": detail}
    evs.append(dict(body, event_digest=ex.digest(body)))
    return evs


@pytest.mark.parametrize("tail", ["illegal_edge", "inadmissible"])
def test_a_rechained_journal_is_still_checked_on_read(tmp_path, tail):
    """The chain is unkeyed, so anyone can recompute it; the reader still applies the table and the admission rules."""
    j = ex.ExecutionJournal(tmp_path)
    intent = j.intent_id("payments", "client:alice", "k")
    evs = _line(intent, [], ex.RESERVED, {"command_digest": ex.digest(CMD)})
    if tail == "illegal_edge":
        _line(intent, evs, ex.REFUSED, {"decision": "REFUSE"})
        _line(intent, evs, ex.DISPATCHED, {"context": {}})
    else:
        _line(intent, evs, ex.AUTHORIZED, {}, attempt="a1")  # table-legal, but no decision
    j.path(intent).write_bytes(b"".join(ex._canon(e) + b"\n" for e in evs))
    with pytest.raises(ex.JournalCorrupt):
        j.events(intent)


def test_a_rechained_attestation_must_carry_a_binding_receipt(tmp_path):
    """The read path checks receipt binding structurally (it has no verifier): a hand-written ATTESTED with another
    command's receipt is refused on read, not only on write."""
    j = ex.ExecutionJournal(tmp_path)
    intent = j.intent_id("payments", "client:alice", "k")
    ctx = {"record_id": intent, "attempt_id": "a1", "command_digest": ex.digest(CMD), "authorization_digest": AUTH}
    evs = _line(intent, [], ex.RESERVED, {"command_digest": ex.digest(CMD)})
    _line(intent, evs, ex.AUTHORIZED, {"decision": "ALLOW", "authorization_digest": AUTH}, attempt="a1")
    _line(intent, evs, ex.DISPATCHED, {"context": ctx}, attempt="a1")
    _line(intent, evs, ex.ACKNOWLEDGED, {"receipt": receipt(ctx)}, attempt="a1")
    good = list(evs)
    _line(intent, evs, ex.ATTESTED, {"receipt": receipt(dict(ctx, command_digest=ex.digest(OTHER)))}, attempt="a1")
    j.path(intent).write_bytes(b"".join(ex._canon(e) + b"\n" for e in evs))
    with pytest.raises(ex.JournalCorrupt, match="does not bind"):
        j.events(intent)
    _line(intent, good, ex.ATTESTED, {"receipt": receipt(ctx)}, attempt="a1")  # control: the bound receipt reads fine
    j.path(intent).write_bytes(b"".join(ex._canon(e) + b"\n" for e in good))
    assert j.state(intent) == ex.ATTESTED


# --- I10: tampering -----------------------------------------------------------------------------------------------------

def _settled_journal(tmp_path):
    co, j = coordinator(tmp_path, observer=lambda c, ctx: True)
    assert submit(co) == ex.CONFIRMED
    intent = j.intent_id("payments", "client:alice", "invoice-7")
    return j, intent, j.path(intent).read_bytes()


@pytest.mark.parametrize("how", ["edit", "torn", "replay", "remove", "reorder"])
def test_a_tampered_journal_is_detected(tmp_path, how):
    j, intent, raw = _settled_journal(tmp_path)
    lines = raw.splitlines(keepends=True)
    new = {"edit": raw.replace(b'"actor":"coordinator"', b'"actor":"coordinatoX"', 1),
           "torn": raw[:-7],
           "replay": raw + lines[-1],
           "remove": b"".join(lines[:2] + lines[3:]),
           "reorder": b"".join([lines[0], lines[2], lines[1]] + lines[3:])}[how]
    j.path(intent).write_bytes(new)
    with pytest.raises(ex.JournalCorrupt):
        j.events(intent)


@pytest.mark.parametrize("how", ["replay", "remove"])
def test_tampering_that_keeps_every_transition_legal_is_detected_by_the_chain(tmp_path, how):
    """DEFERRED -> DEFERRED is a legal self-loop, so replaying or removing one DEFERRED event leaves a history the table
    accepts; only the chain (seq, prev_event_digest, from) catches it."""
    co, j = coordinator(tmp_path, decision="DEFER")
    for _ in range(3):
        assert submit(co) == ex.DEFERRED
    intent = j.intent_id("payments", "client:alice", "invoice-7")
    lines = j.path(intent).read_bytes().splitlines(keepends=True)
    j.path(intent).write_bytes(b"".join(lines + [lines[-1]] if how == "replay" else lines[:2] + lines[3:]))
    with pytest.raises(ex.JournalCorrupt, match="chain"):
        j.events(intent)


def test_a_last_event_missing_only_its_newline_is_torn(tmp_path):
    """The JSON is complete, but the next append would run two events into one line: the reader refuses it."""
    j, intent, raw = _settled_journal(tmp_path)
    j.path(intent).write_bytes(raw[:-1])
    with pytest.raises(ex.JournalCorrupt, match="torn"):
        j.events(intent)


def test_a_journal_copied_from_another_intent_is_detected(tmp_path):
    j, intent, raw = _settled_journal(tmp_path)
    other = j.intent_id("payments", "client:bob", "invoice-7")
    j.path(other).write_bytes(raw)
    with pytest.raises(ex.JournalCorrupt, match="another journal"):
        j.events(other)


# --- receipts and attestation (stand-in signature) ----------------------------------------------------------------------

def test_no_verifier_no_attestation(tmp_path):
    j = ex.ExecutionJournal(tmp_path)  # no verify configured
    intent, ctx = unconfirmed(j)
    with pytest.raises(ex.IllegalTransition, match="verifier"):
        j.append(intent, ex.ATTESTED, "coordinator", {"receipt": receipt(ctx)})


@pytest.mark.parametrize("bad", ["missing", "record", "attempt", "command", "authorization", "signature", "failed"])
def test_attestation_needs_a_bound_verified_receipt(tmp_path, bad):
    """I5-I7 at the journal: whoever calls append(), not only the coordinator."""
    j = ex.ExecutionJournal(tmp_path, verify=stand_in_verify)
    intent, ctx = unconfirmed(j)
    r = {"missing": None, "record": receipt(dict(ctx, record_id="0" * 64)), "attempt": receipt(dict(ctx, attempt_id="ff")),
         "command": receipt(dict(ctx, command_digest=ex.digest(OTHER))),
         "authorization": receipt(dict(ctx, authorization_digest="sha256:x")), "signature": receipt(ctx, sig="forged"),
         "failed": receipt(ctx, "FAILED")}[bad]
    with pytest.raises(ex.IllegalTransition):
        j.append(intent, ex.ATTESTED, "coordinator", {} if r is None else {"receipt": r})
    j.append(intent, ex.ATTESTED, "coordinator", {"receipt": receipt(ctx)})  # positive control
    assert j.state(intent) == ex.ATTESTED


@pytest.mark.parametrize("mode", ["raise", "none", "failed"])
def test_a_failure_report_is_unconfirmed_never_no_effect(tmp_path, mode):
    co, _ = coordinator(tmp_path, executor=Executor(mode))
    assert submit(co) == ex.UNCONFIRMED


@pytest.mark.parametrize("settle", [ex.ATTESTED, ex.CONFIRMED, ex.DISPUTED, ex.REFUSED, ex.FINALIZED])
def test_a_late_receipt_never_changes_a_settled_state(tmp_path, settle):
    """I9: only EFFECT_UNCONFIRMED accepts a late receipt."""
    observer = {ex.CONFIRMED: lambda c, ctx: True, ex.DISPUTED: lambda c, ctx: False}.get(settle)
    co, j = coordinator(tmp_path, decision="REFUSE" if settle == ex.REFUSED else "ALLOW", observer=observer)
    submit(co)
    intent = j.intent_id("payments", "client:alice", "invoice-7")
    if settle == ex.FINALIZED:
        j.append(intent, ex.FINALIZED, "human:operator", {"basis": "reconciled with the bank statement"})
    assert j.state(intent) == settle
    ctx = next((e["detail"]["context"] for e in j.events(intent) if e["to"] == ex.DISPATCHED),
               {"record_id": intent, "attempt_id": "a1", "command_digest": ex.digest(CMD), "authorization_digest": AUTH})
    assert co.accept_receipt(intent, receipt(ctx)) == settle
    assert j.state(intent) == settle


def test_a_late_receipt_attests_an_unconfirmed_intent(tmp_path):
    co, j = coordinator(tmp_path, executor=Executor("none"))
    assert submit(co) == ex.UNCONFIRMED
    intent = j.intent_id("payments", "client:alice", "invoice-7")
    ctx = next(e["detail"]["context"] for e in j.events(intent) if e["to"] == ex.DISPATCHED)
    assert co.accept_receipt(intent, receipt(dict(ctx, command_digest=ex.digest(OTHER)))) == ex.UNCONFIRMED
    assert co.accept_receipt(intent, receipt(ctx)) == ex.ATTESTED


def test_a_lying_executor_is_attested_alone_and_disputed_by_an_observer(tmp_path):
    """X6: a valid receipt and no effect. Receipts cannot tell; only the independent observer can."""
    co, _ = coordinator(tmp_path / "a")
    assert submit(co) == ex.ATTESTED
    co, _ = coordinator(tmp_path / "b", observer=lambda c, ctx: False)
    assert submit(co) == ex.DISPUTED


# --- claims about the world -------------------------------------------------------------------------------------------

@pytest.mark.parametrize("to", [ex.NO_EFFECT, ex.CONFIRMED, ex.DISPUTED])
@pytest.mark.parametrize("actor,basis", [("coordinator", "checked"), ("human:operator", ""), ("observer:x", None)])
def test_world_claims_need_a_basis_and_a_person_or_observer(tmp_path, to, actor, basis):
    j = ex.ExecutionJournal(tmp_path, verify=stand_in_verify)
    intent, _ = unconfirmed(j)
    with pytest.raises(ex.IllegalTransition):
        j.append(intent, to, actor, {} if basis is None else {"basis": basis})
    j.append(intent, to, "human:operator", {"basis": "checked the bank"})


def test_finalizing_is_a_person_s_or_observer_s_call(tmp_path):
    co, j = coordinator(tmp_path)
    assert submit(co) == ex.ATTESTED
    intent = j.intent_id("payments", "client:alice", "invoice-7")
    with pytest.raises(ex.IllegalTransition):
        j.append(intent, ex.FINALIZED, "coordinator", {"basis": "executor said so"})
    j.append(intent, ex.FINALIZED, "human:operator", {"basis": "reconciled with the bank statement"})


def test_limit_the_actor_is_declared_not_authenticated(tmp_path):
    """A recorded limit, not a property: any caller may write 'human:...'. The rule stops an orchestrator's mistake, not a
    liar. If actors become authenticated, this test should fail and be replaced."""
    j = ex.ExecutionJournal(tmp_path)
    intent, _ = unconfirmed(j)
    j.append(intent, ex.NO_EFFECT, "human:anyone-at-all", {"basis": "asserted"})
    assert j.state(intent) == ex.NO_EFFECT


def test_limit_on_read_a_receipt_signature_is_not_checked(tmp_path):
    """A recorded limit: the reader has no verifier, so a hand-written history whose receipt binds but carries a forged
    signature reads as valid. Only append() verifies signatures."""
    j = ex.ExecutionJournal(tmp_path)
    intent = j.intent_id("payments", "client:alice", "k")
    ctx = {"record_id": intent, "attempt_id": "a1", "command_digest": ex.digest(CMD), "authorization_digest": AUTH}
    evs = _line(intent, [], ex.RESERVED, {"command_digest": ex.digest(CMD)})
    _line(intent, evs, ex.AUTHORIZED, {"decision": "ALLOW", "authorization_digest": AUTH}, attempt="a1")
    _line(intent, evs, ex.DISPATCHED, {"context": ctx}, attempt="a1")
    _line(intent, evs, ex.UNCONFIRMED, {"why": "test"}, attempt="a1")
    _line(intent, evs, ex.ATTESTED, {"receipt": receipt(ctx, sig="forged")}, attempt="a1")
    j.path(intent).write_bytes(b"".join(ex._canon(e) + b"\n" for e in evs))
    assert j.state(intent) == ex.ATTESTED


# --- recovery (I3, I4, I8) ----------------------------------------------------------------------------------------------

@pytest.mark.parametrize("point", ["after_append:DISPATCHED", "before_execute"])
def test_a_crash_after_dispatch_is_never_redispatched(tmp_path, point):
    e = Executor()
    co, j = coordinator(tmp_path, executor=e, fault=crash_at(point))
    with pytest.raises(Crash):
        submit(co)
    co, _ = coordinator(tmp_path, executor=e)
    assert submit(co) == ex.UNCONFIRMED
    assert submit(co) == ex.UNCONFIRMED
    assert e.calls == []  # the effect is unknown, so nothing runs again
    intent = j.intent_id("payments", "client:alice", "invoice-7")
    co.reconcile_no_effect(intent, "human:operator", "bank shows no transfer")
    assert submit(co) == ex.ATTESTED and len(e.calls) == 1
    attempts = [ev["attempt_id"] for ev in j.events(intent) if ev["to"] == ex.AUTHORIZED]
    assert len(attempts) == 2 and len(set(attempts)) == 2


def test_a_crash_after_execute_is_unconfirmed_and_the_effect_happened_once(tmp_path):
    e = Executor()
    co, _ = coordinator(tmp_path, executor=e, fault=crash_at("after_execute"))
    with pytest.raises(Crash):
        submit(co)
    co, _ = coordinator(tmp_path, executor=e)
    assert submit(co) == ex.UNCONFIRMED
    assert len(e.calls) == 1


def test_a_crash_after_acknowledgement_reattests_without_executing_again(tmp_path):
    e = Executor()
    co, _ = coordinator(tmp_path, executor=e, fault=crash_at("after_ack"))
    with pytest.raises(Crash):
        submit(co)
    co, _ = coordinator(tmp_path, executor=e)
    assert submit(co) == ex.ATTESTED
    assert len(e.calls) == 1


def test_a_storage_failure_before_the_dispatch_record_never_executes(tmp_path):
    e = Executor()
    co, j = coordinator(tmp_path, executor=e, fault=crash_at("before_append:DISPATCHED", OSError))
    with pytest.raises(OSError):
        submit(co)
    assert e.calls == []
    assert j.state(j.intent_id("payments", "client:alice", "invoice-7")) == ex.AUTHORIZED
    co, _ = coordinator(tmp_path, executor=e)
    assert submit(co) == ex.ATTESTED and len(e.calls) == 1


# --- X5 with real ssh signatures ----------------------------------------------------------------------------------------

def _keygen(d, name):
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", name, "-f", str(d / name)], check=True)
    return d / name


def _signers(path, entries):
    path.write_text("".join(f'{ident} {opts}{" " if opts else ""}{" ".join((key.parent / (key.name + ".pub")).read_text().split()[:2])}\n'
                            for ident, key, opts in entries))
    return str(path)


def _ssh_sign(key, data, namespace, d):
    f = d / "body"
    f.write_bytes(data)
    sig = d / "body.sig"
    if sig.exists():
        sig.unlink()
    subprocess.run(["ssh-keygen", "-Y", "sign", "-f", str(key), "-n", namespace, str(f)], check=True, capture_output=True)
    return sig.read_text()


@pytest.fixture
def ssh(tmp_path):
    k1, k2, stranger = (_keygen(tmp_path, n) for n in ("executor-1", "executor-2", "stranger"))
    scoped = _signers(tmp_path / "scoped", [("executor-1", k1, 'namespaces="sv-effect-receipt"'),
                                            ("executor-2", k2, 'namespaces="sv-effect-receipt"')])
    open_ = _signers(tmp_path / "open", [("executor-1", k1, ""), ("executor-2", k2, "")])
    pkg_only = _signers(tmp_path / "pkg_only", [("executor-1", k1, 'namespaces="sv-package"')])
    ctx = {"record_id": "r" * 64, "attempt_id": "a1", "command_digest": ex.digest(CMD), "authorization_digest": AUTH}
    return {"k1": k1, "k2": k2, "stranger": stranger, "scoped": scoped, "open": open_, "pkg_only": pkg_only,
            "ctx": ctx, "d": tmp_path}


def _case(s, name):
    ctx, k1 = s["ctx"], s["k1"]
    base = {k: v for k, v in receipt(ctx).items() if k != "signature"}
    signed = lambda r, key=k1: receipts.sign_receipt(r, str(key))  # noqa: E731
    if name == "valid":
        return signed(base)
    if name == "missing_field":
        return signed({k: v for k, v in base.items() if k != "effect_reference"})
    if name in ("other_command", "other_authorization", "other_attempt", "other_record"):
        field = {"other_command": ("command_digest", ex.digest(OTHER)), "other_authorization": ("authorization_digest", "x"),
                 "other_attempt": ("attempt_id", "a2"), "other_record": ("record_id", "0" * 64)}[name]
        return signed(dict(base, **{field[0]: field[1]}))
    if name == "package_namespace":
        return dict(base, signature=_ssh_sign(k1, receipts.body_bytes(base), "sv-package", s["d"]))
    if name == "unknown_key":
        return signed(base, s["stranger"])
    if name == "identity_mismatch":  # claims executor-2, signed with executor-1's key
        return signed(dict(base, executor_id="executor-2"))
    if name == "edited_after_signing":
        r = signed(dict(base, effect_result="FAILED"))
        r["effect_result"] = "ATTESTED"
        return r
    if name == "failed_validly_signed":
        return signed(dict(base, effect_result="FAILED"))
    raise AssertionError(name)


NEGATIVE = ["missing_field", "other_command", "other_authorization", "other_attempt", "other_record", "package_namespace",
            "unknown_key", "identity_mismatch", "edited_after_signing", "failed_validly_signed"]


@needs_ssh
def test_x5_positive_control_a_valid_receipt_attests(ssh):
    assert receipts.verify_receipt(_case(ssh, "valid"), expected=ssh["ctx"], allowed_signers=ssh["scoped"]) == \
        (True, "EFFECT_ATTESTED", [])


@needs_ssh
@pytest.mark.parametrize("name", NEGATIVE)
@pytest.mark.parametrize("signers", ["scoped", "open"])
def test_x5_receipts_that_must_never_attest(ssh, name, signers):
    attested, status, reasons = receipts.verify_receipt(_case(ssh, name), expected=ssh["ctx"], allowed_signers=ssh[signers])
    assert (attested, status) == (False, "EFFECT_UNCONFIRMED") and reasons


@needs_ssh
def test_x5_a_key_scoped_to_packages_cannot_sign_receipts(ssh):
    assert receipts.verify_receipt(_case(ssh, "valid"), expected=ssh["ctx"], allowed_signers=ssh["pkg_only"])[0] is False


@needs_ssh
@pytest.mark.parametrize("name", NEGATIVE)
def test_x5_the_journal_refuses_every_negative_receipt(tmp_path, ssh, name):
    verify = lambda r, ctx: receipts.verify_receipt(r, expected=ctx, allowed_signers=ssh["scoped"])  # noqa: E731
    j = ex.ExecutionJournal(tmp_path / "j", verify=verify)
    intent, ctx = unconfirmed(j)
    ssh["ctx"] = ctx  # receipts are made for this intent's real context
    with pytest.raises(ex.IllegalTransition):
        j.append(intent, ex.ATTESTED, "coordinator", {"receipt": _case(ssh, name)})
    j.append(intent, ex.ATTESTED, "coordinator", {"receipt": _case(ssh, "valid")})


def test_receipt_verification_without_ssh_keygen_fails_closed(monkeypatch):
    """Not skipped: with no ssh-keygen, nothing is attested (SignatureUnavailable), through the journal too."""
    monkeypatch.setattr(receipts.shutil, "which", lambda name: None)
    ctx = {"record_id": "r" * 64, "attempt_id": "a1", "command_digest": ex.digest(CMD), "authorization_digest": AUTH}
    with pytest.raises(receipts.SignatureUnavailable):
        receipts.verify_receipt(receipt(ctx, sig="anything"), expected=ctx, allowed_signers="/nonexistent")


def test_a_verifier_that_cannot_run_leaves_the_intent_acknowledged(tmp_path, monkeypatch):
    monkeypatch.setattr(receipts.shutil, "which", lambda name: None)
    verify = lambda r, ctx: receipts.verify_receipt(r, expected=ctx, allowed_signers="/nonexistent")  # noqa: E731
    co, j = coordinator(tmp_path, verify=verify)
    with pytest.raises(receipts.SignatureUnavailable):
        submit(co)
    assert j.state(j.intent_id("payments", "client:alice", "invoice-7")) == ex.ACKNOWLEDGED


def test_the_journal_on_disk_is_canonical_json_lines(tmp_path):
    co, j = coordinator(tmp_path)
    submit(co)
    raw = j.path(j.intent_id("payments", "client:alice", "invoice-7")).read_bytes()
    for line in raw.splitlines():
        assert ex._canon(json.loads(line)) == line
