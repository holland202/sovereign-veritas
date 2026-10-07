"""Durable execution journal and coordinator (EX-1, docs/EX1_PREREG.md). PROTOTYPE, self-tested.

The execution boundary is a state machine written to disk, not inferred from logs:

    RESERVED -> AUTHORIZED | DEFERRED | REFUSED
    AUTHORIZED -> DISPATCHED  (written and fsynced BEFORE the executor is called)
    DISPATCHED -> EXECUTOR_ACKNOWLEDGED | EFFECT_UNCONFIRMED
    EXECUTOR_ACKNOWLEDGED -> EFFECT_ATTESTED | EFFECT_UNCONFIRMED
    EFFECT_ATTESTED / EFFECT_UNCONFIRMED -> INDEPENDENTLY_CONFIRMED | EFFECT_DISPUTED | ...

One journal file per intent (domain, principal, idempotency key). Publishing it (its first event written to a temporary
file, then os.link, which fails if the path exists) is the reservation, so two submissions of one intent cannot both
reserve. Every event is hash-chained to the previous one, appended under an OS lock, and fsynced. An illegal transition
raises (fail closed): REFUSED and DEFERRED have no edge to DISPATCHED.

The journal itself enforces the evidential precondition of each transition (`_admit`), on write and again on read, rather
than trusting whoever calls append() (EX-1 fixes 1-3, docs/EX1_RESULTS.md): AUTHORIZED needs an ALLOW decision, an
authorization digest and an attempt id new to this intent; DISPATCHED needs a context binding exactly this intent, the
attempt just authorized, the reserved command and that authorization; EXECUTOR_ACKNOWLEDGED needs the executor's receipt;
EFFECT_ATTESTED needs a receipt bound to the dispatched context, and on write one that the configured verifier accepts;
claims about the world (INDEPENDENTLY_CONFIRMED, EFFECT_DISPUTED, RECONCILED_NO_EFFECT) and FINALIZED need a stated basis
and a human: or observer: actor. The actor is declared, not authenticated: these rules stop an orchestrator's mistakes, not
a caller who lies (anyone who can call append() can also write the file).

What this establishes, given an honest filesystem (fsync is trusted, not tested here): no intent is dispatched twice unless a
person records RECONCILED_NO_EFFECT in between, and no effect can happen without a durable DISPATCHED event before it. What
it does not establish: that an effect happened (EFFECT_ATTESTED is the executor's signed claim; INDEPENDENTLY_CONFIRMED is
an observer's claim), or anything about an attacker who can write the journal directory (the chain detects edits, not
replacement of a whole file).
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from sovereign_veritas.evidence import canonical_json

try:
    import fcntl
except ImportError:  # Windows
    fcntl = None
try:
    import msvcrt
except ImportError:  # POSIX
    msvcrt = None

EVENT_SCHEMA = "sv.exec-event/1"
CONTRACT_VERSION = "sv.gate/0"

RESERVED, AUTHORIZED, DEFERRED, REFUSED = "RESERVED", "AUTHORIZED", "DEFERRED", "REFUSED"
DISPATCHED, ACKNOWLEDGED = "DISPATCHED", "EXECUTOR_ACKNOWLEDGED"
ATTESTED, UNCONFIRMED = "EFFECT_ATTESTED", "EFFECT_UNCONFIRMED"
CONFIRMED, DISPUTED, NO_EFFECT, FINALIZED = "INDEPENDENTLY_CONFIRMED", "EFFECT_DISPUTED", "RECONCILED_NO_EFFECT", "FINALIZED"

TRANSITIONS: dict[str | None, frozenset[str]] = {
    None: frozenset({RESERVED}),
    RESERVED: frozenset({AUTHORIZED, DEFERRED, REFUSED}),
    DEFERRED: frozenset({AUTHORIZED, DEFERRED, REFUSED}),
    AUTHORIZED: frozenset({AUTHORIZED, DEFERRED, REFUSED, DISPATCHED}),
    REFUSED: frozenset(),
    DISPATCHED: frozenset({ACKNOWLEDGED, UNCONFIRMED}),
    ACKNOWLEDGED: frozenset({ATTESTED, UNCONFIRMED}),
    ATTESTED: frozenset({CONFIRMED, DISPUTED, FINALIZED}),
    UNCONFIRMED: frozenset({ATTESTED, CONFIRMED, DISPUTED, NO_EFFECT}),
    CONFIRMED: frozenset({FINALIZED}),
    DISPUTED: frozenset({CONFIRMED, NO_EFFECT}),
    NO_EFFECT: frozenset({AUTHORIZED, DEFERRED, REFUSED}),  # a new attempt needs a fresh decision
    FINALIZED: frozenset(),
}
# States in which the effect may have happened. Nothing may move an intent from these into a state that says otherwise
# except RECONCILED_NO_EFFECT, which needs a person or observer and a stated basis (I8).
EFFECT_POSSIBLE = frozenset({DISPATCHED, ACKNOWLEDGED, ATTESTED, UNCONFIRMED, CONFIRMED, DISPUTED, FINALIZED})
# FINALIZED closes the record: once written, no observer can dispute it, so closing is a person's or observer's call too.
NEEDS_BASIS = frozenset({CONFIRMED, NO_EFFECT, DISPUTED, FINALIZED})
# The fields that bind a dispatched attempt; a receipt must carry the same values (receipts.BINDING is the same tuple).
CONTEXT_KEYS = ("record_id", "attempt_id", "command_digest", "authorization_digest")
# EX-1 fuzz (docs/EX1_RESULTS.md): the actor rule lived only in ExecutionCoordinator.reconcile_no_effect(), so any caller of
# ExecutionJournal.append could record RECONCILED_NO_EFFECT after an effect. Claims about the world need an actor who
# observed it: a person or an observer, never the coordinator or an arbitrary caller. (A lying person is out of model.)
OBSERVER_ACTORS = ("human:", "observer:")


class IllegalTransition(ValueError):
    pass


class JournalCorrupt(ValueError):
    """The journal cannot be read as a valid chain: reconciliation by a person is required; nothing is dispatched."""


class ConflictingIntent(ValueError):
    """The idempotency key is already reserved for a different command."""


def _finite(value: Any) -> None:
    """Raise ValueError on NaN/Infinity, which canonical_json would write as the non-JSON literals NaN/Infinity."""
    json.dumps(value, allow_nan=False)


def _canon(value: Any) -> bytes:
    # Every digest in this package hashes evidence.canonical_json (JG-2 P1). The first version had its own copy of it:
    # identical bytes for finite values, but JG-2 P1 was REFUTED at b7d072b (docs/JG2_PREREG.md, Record 2).
    _finite(value)
    return canonical_json(value).encode("utf-8")


def digest(value: Any) -> str:
    _finite(value)
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _now() -> dict[str, str]:
    return {"value": datetime.now(timezone.utc).isoformat(), "source": "local clock (not trusted)"}


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def _admit(intent: str, evs: list[dict[str, Any]], to: Any, actor: Any, detail: dict[str, Any],
           attempt_id: Any) -> str | None:
    """Why an event (to, actor, detail, attempt_id) may not follow `evs` in this intent's journal, or None. The same rules
    apply on write (append) and on read (events). `attempt_id` is the event's effective attempt id (carried if not given).
    EX-1 fix 3: AUTHORIZED, DISPATCHED and EXECUTOR_ACKNOWLEDGED were written with whatever the caller passed, so a direct
    caller could bind a dispatch to another command or reuse an attempt id (tools/ex1_poc_binding.py)."""
    state = evs[-1]["to"] if evs else None
    if to not in TRANSITIONS.get(state, frozenset()):
        return f"{state} -> {to} is not a legal transition"
    if to in NEEDS_BASIS:
        if not _nonempty(detail.get("basis")):
            return f"{to} needs a stated basis (who or what observed it)"
        if not (isinstance(actor, str) and actor.startswith(OBSERVER_ACTORS)):
            return f"{to} needs a human: or observer: actor, not {actor!r}"
    if to == AUTHORIZED:
        if detail.get("decision") != "ALLOW":
            return "AUTHORIZED needs the decision ALLOW"
        if not _nonempty(detail.get("authorization_digest")):
            return "AUTHORIZED needs an authorization_digest"
        if not _nonempty(attempt_id):
            return "AUTHORIZED needs an attempt id"
        if any(e["to"] == AUTHORIZED and e["attempt_id"] == attempt_id for e in evs):
            return f"attempt id {attempt_id!r} was already authorized for this intent"
    if to == DISPATCHED:
        auth = evs[-1] if evs and evs[-1]["to"] == AUTHORIZED else None
        if auth is None:
            return "DISPATCHED has no authorization to bind to"
        want = {"record_id": intent, "attempt_id": auth["attempt_id"],
                "command_digest": evs[0]["detail"].get("command_digest"),
                "authorization_digest": auth["detail"].get("authorization_digest")}
        if detail.get("context") != want:
            return "DISPATCHED context must bind exactly this intent, the authorized attempt, the reserved command and its authorization"
        if attempt_id != auth["attempt_id"]:
            return "DISPATCHED must carry the authorized attempt id"
    if to == ACKNOWLEDGED and detail.get("receipt") is None:
        return "EXECUTOR_ACKNOWLEDGED needs the executor's receipt"
    if to == ATTESTED:
        ctx = next((e["detail"].get("context") for e in reversed(evs) if e["to"] == DISPATCHED), None)
        receipt = detail.get("receipt")
        if not isinstance(ctx, dict) or not isinstance(receipt, dict):
            return "EFFECT_ATTESTED needs a receipt and a dispatched attempt to bind it to"
        if any(receipt.get(k) != ctx.get(k) for k in CONTEXT_KEYS):
            return "EFFECT_ATTESTED receipt does not bind the dispatched attempt"
    return None


class _Locked:
    """Exclusive OS lock on <journal>.lock, released by the OS if the holder dies. A sidecar, like every other lock in this
    repository: msvcrt.locking is mandatory on Windows, so locking the journal itself would stop this process's own second
    handle from reading it (predicted from the LockFile documentation and changed before any Windows run; not observed).
    The sidecar is never unlinked (unlinking a locked file lets a second locker in, K1)."""

    def __init__(self, path: Path):
        self.fd = os.open(path.with_name(path.name + ".lock"), os.O_CREAT | os.O_RDWR, 0o600)

    def __enter__(self):
        if fcntl is not None:
            fcntl.flock(self.fd, fcntl.LOCK_EX)
        elif msvcrt is not None:
            msvcrt.locking(self.fd, msvcrt.LK_LOCK, 1)
        else:
            os.close(self.fd)
            raise RuntimeError("no operating-system file lock available: refusing to append")
        return self

    def __exit__(self, *exc):
        os.close(self.fd)  # releases the lock


class ExecutionJournal:
    def __init__(self, directory: str | os.PathLike[str], fault: Callable[[str], None] | None = None,
                 verify: Callable | None = None) -> None:
        self.dir = Path(directory)
        # EFFECT_ATTESTED is only written with a receipt that `verify` accepts for the current attempt (EX-1 fuzz: the check
        # lived in the coordinator, so any caller of append() could attest with no receipt). No verifier: no attestation.
        self.verify = verify
        self.dir.mkdir(parents=True, exist_ok=True)
        self.fault = fault or (lambda point: None)

    @staticmethod
    def intent_id(domain: str, principal: str, key: str) -> str:
        for name, v in (("domain", domain), ("principal", principal), ("idempotency key", key)):
            if not isinstance(v, str) or not v:
                raise ValueError(f"{name} must be a non-empty string")
        return hashlib.sha256(canonical_json([domain, principal, key]).encode("utf-8")).hexdigest()

    def path(self, intent: str) -> Path:
        return self.dir / f"{intent}.jsonl"

    def events(self, intent: str) -> list[dict[str, Any]]:
        """Every event, chain-verified. Raises JournalCorrupt on a torn line, a broken chain or a replayed sequence."""
        path = self.path(intent)
        if not path.exists():
            return []
        raw = path.read_bytes()
        if raw and not raw.endswith(b"\n"):
            raise JournalCorrupt(f"{intent[:12]}: last line is torn (no newline)")
        out, prev, state = [], None, None
        for n, line in enumerate(raw.splitlines()):
            try:
                ev = json.loads(line)
            except ValueError as exc:
                raise JournalCorrupt(f"{intent[:12]} line {n}: not JSON") from exc
            if not isinstance(ev, dict) or not isinstance(ev.get("detail"), dict):
                raise JournalCorrupt(f"{intent[:12]} line {n}: not an event object")
            body = {k: v for k, v in ev.items() if k != "event_digest"}
            if ev.get("event_digest") != digest(body):
                raise JournalCorrupt(f"{intent[:12]} line {n}: digest mismatch (edited)")
            if ev.get("prev_event_digest") != prev or ev.get("seq") != n or ev.get("from") != state:
                raise JournalCorrupt(f"{intent[:12]} line {n}: chain broken (reordered, replayed or removed event)")
            if ev.get("schema") != EVENT_SCHEMA or ev.get("intent") != intent:
                raise JournalCorrupt(f"{intent[:12]} line {n}: event of schema {ev.get('schema')!r} for intent "
                                     f"{str(ev.get('intent'))[:12]} (copied from another journal?)")
            why = _admit(intent, out, ev.get("to"), ev.get("actor"), ev["detail"], ev.get("attempt_id"))
            if why:
                raise JournalCorrupt(f"{intent[:12]} line {n}: inadmissible event on disk: {why}")
            out.append(ev)
            prev, state = ev["event_digest"], ev["to"]
        return out

    def state(self, intent: str) -> str | None:
        evs = self.events(intent)
        return evs[-1]["to"] if evs else None

    def _event(self, intent: str, evs: list[dict[str, Any]], to: str, actor: str, detail: dict[str, Any],
               attempt_id: str | None) -> dict[str, Any]:
        state = evs[-1]["to"] if evs else None
        if to not in TRANSITIONS.get(state, frozenset()):
            raise IllegalTransition(f"{state} -> {to} is not a legal transition")
        first = evs[0]["detail"] if evs else detail
        body = {"schema": EVENT_SCHEMA, "intent": intent, "seq": len(evs), "from": state, "to": to,
                "attempt_id": attempt_id if attempt_id is not None else (evs[-1]["attempt_id"] if evs else None),
                "actor": actor, "contract_version": CONTRACT_VERSION, "command_digest": first.get("command_digest"),
                "prev_event_digest": evs[-1]["event_digest"] if evs else None, "at": _now(), "detail": detail}
        return dict(body, event_digest=digest(body))

    def _existing(self, intent: str, cdig: str) -> tuple[str, bool]:
        evs = self.events(intent)
        if not evs:
            raise JournalCorrupt(f"{intent[:12]}: reservation file has no events")
        if evs[0]["detail"].get("command_digest") != cdig:
            raise ConflictingIntent(f"intent already reserved for command {evs[0]['detail']['command_digest']}")
        return intent, False

    def reserve(self, domain: str, principal: str, key: str, command: Any, actor: str) -> tuple[str, bool]:
        """(intent, created). created is True for exactly one caller per intent, ever. The first event is written to a
        temporary file and published with os.link, which is atomic and fails if the path exists: a reservation file
        never exists without its first event, so no second caller can mistake a half-made reservation for an abandoned
        one and claim the key for a different command."""
        intent = self.intent_id(domain, principal, key)
        cdig = digest(command)
        path = self.path(intent)
        if path.exists():
            return self._existing(intent, cdig)
        ev = self._event(intent, [], RESERVED, actor, {"domain": domain, "principal": principal, "command_digest": cdig},
                         None)
        tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}-{secrets.token_hex(4)}")
        try:
            with open(tmp, "wb") as fh:
                fh.write(_canon(ev) + b"\n")
                fh.flush()
                os.fsync(fh.fileno())
            self.fault("before_reserve_publish")
            try:
                os.link(tmp, path)
            except FileExistsError:
                return self._existing(intent, cdig)
        finally:
            if tmp.exists():
                tmp.unlink()
        self.fault("after_reserve_publish")
        return intent, True

    def append(self, intent: str, to: str, actor: str, detail: dict[str, Any] | None = None,
               attempt_id: str | None = None) -> dict[str, Any]:
        detail = dict(detail or {})
        if to == RESERVED or not self.path(intent).exists():
            raise IllegalTransition("only reserve() creates a journal; append() needs an existing reservation")
        with _Locked(self.path(intent)):
            evs = self.events(intent)
            why = _admit(intent, evs, to, actor, detail,
                         attempt_id if attempt_id is not None else (evs[-1]["attempt_id"] if evs else None))
            if why:
                raise IllegalTransition(why)
            if to == ATTESTED:
                self._check_attestation(evs, detail)
            ev = self._event(intent, evs, to, actor, detail, attempt_id)
            self.fault(f"before_append:{to}")
            with open(self.path(intent), "ab") as fh:
                fh.write(_canon(ev) + b"\n")
                fh.flush()
                os.fsync(fh.fileno())
            self.fault(f"after_append:{to}")
            return ev

    def _check_attestation(self, evs: list[dict[str, Any]], detail: dict[str, Any]) -> None:
        if self.verify is None:
            raise IllegalTransition("EFFECT_ATTESTED needs a receipt verifier; none is configured")
        ctx = next((e["detail"].get("context") for e in reversed(evs) if e["to"] == DISPATCHED), None)
        receipt = detail.get("receipt")
        if ctx is None or receipt is None:
            raise IllegalTransition("EFFECT_ATTESTED needs a receipt and a dispatched attempt to bind it to")
        attested, _, reasons = self.verify(receipt, ctx)
        if not attested:
            raise IllegalTransition(f"EFFECT_ATTESTED refused: receipt does not attest this attempt: {reasons}")

    def intents(self) -> list[str]:
        return sorted(p.stem for p in self.dir.glob("*.jsonl"))


class ExecutionCoordinator:
    """reserve -> decide -> durable DISPATCHED -> execute -> receipt -> (observe). Never re-dispatches an intent that has
    reached DISPATCHED in its current attempt; recovery moves such an intent to EFFECT_UNCONFIRMED instead.

    decide(command) -> (decision, reasons); executor.execute(command, context) -> receipt dict or None (may raise);
    verify(receipt, expected) -> (attested, status, reasons); observer(command, context) -> True | False | None."""

    def __init__(self, journal: ExecutionJournal, *, decide: Callable, executor: Any, verify: Callable,
                 observer: Callable | None = None, actor: str = "coordinator", policy_version: str = "unversioned",
                 observer_id: str = "observer:independent",
                 fault: Callable[[str], None] | None = None) -> None:
        self.j, self.decide, self.executor, self.verify = journal, decide, executor, verify
        self.observer, self.actor, self.policy_version, self.observer_id = observer, actor, policy_version, observer_id
        self.fault = fault or journal.fault
        if self.j.verify is None:
            self.j.verify = verify

    def _context(self, intent: str, attempt: str, command: Any, authorization_digest: str) -> dict[str, str]:
        return {"record_id": intent, "attempt_id": attempt, "command_digest": digest(command),
                "authorization_digest": authorization_digest}

    def submit(self, domain: str, principal: str, key: str, command: Any, authorization_digest: str) -> str:
        intent, _ = self.j.reserve(domain, principal, key, command, self.actor)
        state = self.j.state(intent)
        if state in (DISPATCHED, ACKNOWLEDGED):
            return self.recover(intent)
        if state not in (RESERVED, DEFERRED, AUTHORIZED, NO_EFFECT):
            return state  # REFUSED, uncertain or terminal: nothing is dispatched
        decision, reasons = self.decide(command)
        attempt = secrets.token_hex(8)
        to = {"ALLOW": AUTHORIZED, "DEFER": DEFERRED}.get(decision, REFUSED)
        self.j.append(intent, to, self.actor, {"decision": decision, "reasons": list(reasons),
                                               "policy_version": self.policy_version,
                                               "authorization_digest": authorization_digest},
                      attempt_id=attempt if to == AUTHORIZED else None)
        if to != AUTHORIZED:
            return to
        self.fault("after_authorize")
        ctx = self._context(intent, attempt, command, authorization_digest)
        self.j.append(intent, DISPATCHED, self.actor, {"context": ctx})  # write-ahead: durable before the executor runs
        self.fault("before_execute")
        try:
            receipt = self.executor.execute(command, ctx)
        except Exception as exc:  # a failure report is not evidence that nothing happened
            self.j.append(intent, UNCONFIRMED, self.actor, {"why": f"executor raised {type(exc).__name__}: {exc}"})
            return UNCONFIRMED
        self.fault("after_execute")
        if receipt is None:
            self.j.append(intent, UNCONFIRMED, self.actor, {"why": "no receipt"})
            return UNCONFIRMED
        self.j.append(intent, ACKNOWLEDGED, self.actor, {"receipt": receipt})
        self.fault("after_ack")
        state = self._attest(intent, receipt, ctx)
        self.fault("after_attest")
        return self._observe(intent, command, ctx, state)

    def _attest(self, intent: str, receipt: Any, ctx: dict[str, str]) -> str:
        attested, status, reasons = self.verify(receipt, ctx)
        if attested:
            self.j.append(intent, ATTESTED, self.actor, {"receipt": receipt})
            return ATTESTED
        self.j.append(intent, UNCONFIRMED, self.actor, {"receipt_check": reasons})
        return UNCONFIRMED

    def _observe(self, intent: str, command: Any, ctx: dict[str, str], state: str) -> str:
        if self.observer is None:
            return state
        seen = self.observer(command, ctx)
        if seen is True:
            self.j.append(intent, CONFIRMED, self.observer_id, {"basis": "independent observer saw the effect"})
            return CONFIRMED
        if seen is False and state == ATTESTED:
            self.j.append(intent, DISPUTED, self.observer_id, {"basis": "receipt attests, independent observer saw no effect"})
            return DISPUTED
        return state  # not seen on an unconfirmed intent stays unconfirmed: the effect may still land

    def recover(self, intent: str) -> str:
        """After a crash: DISPATCHED means the executor may have run; ACKNOWLEDGED has a receipt to check."""
        evs = self.j.events(intent)
        state = evs[-1]["to"] if evs else None
        if state == DISPATCHED:
            self.j.append(intent, UNCONFIRMED, self.actor, {"why": "recovered after DISPATCHED: effect unknown"})
            return UNCONFIRMED
        if state == ACKNOWLEDGED:  # events() guarantees the receipt and the dispatched context (_admit)
            ctx = next(e["detail"]["context"] for e in reversed(evs) if e["to"] == DISPATCHED)
            return self._attest(intent, evs[-1]["detail"]["receipt"], ctx)
        return state

    def accept_receipt(self, intent: str, receipt: Any) -> str:
        """A receipt arriving late, duplicated or replayed. Never changes a terminal or confirmed state (I9)."""
        evs = self.j.events(intent)
        state = evs[-1]["to"] if evs else None
        if state != UNCONFIRMED:
            return state
        ctx = next((e["detail"]["context"] for e in reversed(evs) if e["to"] == DISPATCHED), None)
        if ctx is None:
            return state
        attested, _, reasons = self.verify(receipt, ctx)
        if attested:
            self.j.append(intent, ATTESTED, self.actor, {"late_receipt": True, "receipt": receipt})
            return ATTESTED
        return state

    def reconcile_no_effect(self, intent: str, actor: str, basis: str) -> str:
        """A person (or an observer they trust) states that the effect did not happen. The only way back to a new attempt."""
        self.j.append(intent, NO_EFFECT, actor, {"basis": basis})
        return NO_EFFECT
