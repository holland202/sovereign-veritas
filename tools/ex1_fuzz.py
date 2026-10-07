#!/usr/bin/env python3
"""ex1_fuzz.py - EX-1 X7: state-machine fuzzing of the execution journal and coordinator (docs/EX1_PREREG.md).

Random sequences of operations (submit with ALLOW/DEFER/REFUSE and an honest, raising, silent or lying executor; crash at
a random fault point and restart; late, duplicated and foreign receipts; honest human reconciliation; illegal raw appends;
journal tampering and replayed events) run against one journal directory. Invariants I1-I10 are checked after every
operation against the journal on disk and the world file (ground truth the coordinator never reads). A failing sequence is
minimized by delta debugging.

  python tools/ex1_fuzz.py [--sequences N] [--seed S]   # exit 0 iff no violation
  python tools/ex1_fuzz.py --forge                       # also well-formed adversarial direct appends (fix 3's class)
  python tools/ex1_fuzz.py --sabotage                    # as registered: the coordinator dispatches on REFUSE, plus an
                                                         # illegal REFUSED->DISPATCHED edge; must be caught and minimized
  python tools/ex1_fuzz.py --sabotage-deep               # deviation 3: the same, with fix 3's DISPATCHED binding rule removed
  python tools/ex1_fuzz.py --forge --plant RULE          # anti-vacuity for --forge: remove one fix-3 rule (dispatch-binding,
                                                         # attempt-reuse, attest-binding); the fuzzer must find it

Receipts are checked by the real receipts.problems() and binding rules with an HMAC standing in for the ssh signature (a
named stand-in, for speed; tools/ex1_campaign.py uses real ssh signatures).

Oracles: I1-I10 are computed from the journal's events and the world file. The raw-append legality check reads the
implementation's own transition table (ex.TRANSITIONS, ex.NEEDS_BASIS), so it only checks that append() enforces that table
plus the receipt rule: a derived oracle, not evidence that the table is right.

Deviation 2 (2026-10-07, docs/EX1_RESULTS.md): the legality model omitted I5's receipt condition, and minimization accepted
any violation, so a printed violation could belong to the unminimized sequence. Both corrected; outputs before the correction
are kept in results/ex1/. Deviation 3: after fix 3 the registered sabotage (an illegal edge) is stopped by a second rule (a
dispatch must bind the authorization just before it), so --sabotage-deep removes that rule too, to show the I1 check works.
"""
import hashlib
import hmac
import json
import os
import random
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.dont_write_bytecode = True

from sovereign_veritas import execution as ex  # noqa: E402
from sovereign_veritas.receipts import BINDING, body_bytes, problems  # noqa: E402

SECRET = b"ex1-fuzz-stand-in"
CMD = {"op": "transfer", "amount": 100}
ADMITS_EFFECT = {ex.DISPATCHED, ex.ACKNOWLEDGED, ex.ATTESTED, ex.UNCONFIRMED, ex.CONFIRMED, ex.DISPUTED, ex.FINALIZED}
FAULT_POINTS = ["before_append:AUTHORIZED", "after_authorize", "before_append:DISPATCHED", "after_append:DISPATCHED",
                "before_execute", "after_execute", "after_ack", "before_append:EFFECT_ATTESTED", "after_attest"]


OTHER_CMD = {"op": "transfer", "amount": 999999}
FORGE = ["authorize_fresh", "authorize_reused", "dispatch_bound", "dispatch_other_command", "dispatch_other_record",
         "ack_receipt", "attest_valid", "attest_foreign", "attest_other_attempt"]
# A raw append carries no decision, dispatch context or receipt (deviation 2; extended with fix 3)
NEEDS_EVIDENCE = frozenset({ex.AUTHORIZED, ex.DISPATCHED, ex.ACKNOWLEDGED, ex.ATTESTED})


class Crash(BaseException):
    """Simulated process death: unwinds the coordinator; only what is on disk survives."""


def make_receipt(ctx, result="ATTESTED", **override):
    r = {"schema": "sv.effect-receipt/1", "receipt_id": "r-" + ctx["attempt_id"], "executor_id": "executor-1",
         "executor_key_id": "k1", "effect_type": "transfer/1", "effect_result": result, "effect_reference": "ref",
         "observed_at": {"value": None, "source": "executor", "confidence": "declared"}, "prior_receipt_digest": None,
         **{k: ctx[k] for k in BINDING}}
    r.update(override)
    r["signature"] = hmac.new(SECRET, body_bytes(r), hashlib.sha256).hexdigest()
    return r


def verify(receipt, expected):
    found = problems(receipt)
    if found:
        return False, ex.UNCONFIRMED, found
    if not hmac.compare_digest(receipt["signature"], hmac.new(SECRET, body_bytes(receipt), hashlib.sha256).hexdigest()):
        return False, ex.UNCONFIRMED, ["signature"]
    bad = [k for k in BINDING if receipt[k] != expected.get(k)]
    if bad:
        return False, ex.UNCONFIRMED, [f"{k} does not bind" for k in bad]
    return receipt["effect_result"] == "ATTESTED", ex.ATTESTED if receipt["effect_result"] == "ATTESTED" else ex.UNCONFIRMED, []


class World:
    def __init__(self, path):
        self.path = path

    def effects(self):
        if not os.path.exists(self.path):
            return []
        return [json.loads(l) for l in open(self.path) if l.strip()]

    def add(self, ctx):
        with open(self.path, "a") as fh:
            fh.write(json.dumps({"record_id": ctx["record_id"], "attempt_id": ctx["attempt_id"]}) + "\n")


class Executor:
    def __init__(self, world, mode):
        self.world, self.mode = world, mode

    def execute(self, command, ctx):
        if self.mode == "raise_before":
            raise TimeoutError("no effect, request never left")
        if self.mode != "lie":
            self.world.add(ctx)
        if self.mode == "raise_after":
            raise TimeoutError("effect happened, response lost")
        if self.mode == "silent":
            return None
        if self.mode == "foreign":
            return make_receipt(dict(ctx, command_digest="sha256:" + "0" * 64))
        return make_receipt(ctx)


def plant(rule, orig):
    """An _admit with one of fix 3's rules removed (anti-vacuity for --forge). The table is still enforced."""
    def legal(evs, to):
        return to in ex.TRANSITIONS.get(evs[-1]["to"] if evs else None, frozenset())

    def admit(intent, evs, to, actor, detail, attempt_id):
        if rule == "dispatch-binding" and to == ex.DISPATCHED:
            return None if legal(evs, to) else "illegal"
        if rule == "attempt-reuse" and to == ex.AUTHORIZED and detail.get("decision") == "ALLOW":
            return None if legal(evs, to) else "illegal"
        if rule == "attest-binding" and to == ex.ATTESTED:
            return None if legal(evs, to) else "illegal"
        return orig(intent, evs, to, actor, detail, attempt_id)
    return admit


def coordinator(d, world, op, sabotage):
    fault_point = op.get("crash_at")

    def fault(point):
        if point == fault_point:
            raise Crash(point)

    journal = ex.ExecutionJournal(os.path.join(d, "journal"), fault=fault)
    observer = (lambda c, ctx: any(e["attempt_id"] == ctx["attempt_id"] for e in world.effects())) if op.get("observe") else None
    co = ex.ExecutionCoordinator(journal, decide=lambda c: (op.get("decision", "ALLOW"), []),
                                 executor=Executor(world, op.get("executor", "ok")), verify=verify, observer=observer,
                                 fault=fault)
    if sabotage in (True, "deep"):  # a planted defect: dispatch even on REFUSE (needs the illegal edge too)
        orig = co.submit

        def submit(domain, principal, key, command, auth):
            st = orig(domain, principal, key, command, auth)
            if st == ex.REFUSED:
                intent = journal.intent_id(domain, principal, key)
                ctx = co._context(intent, "sab", command, auth)
                journal.append(intent, ex.DISPATCHED, "sabotage", {"context": ctx}, attempt_id="sab")
                co.executor.execute(command, ctx)
            return st
        co.submit = submit
    return co, journal


def gen_op(rng, forge=False):
    kinds, weights = ["submit", "receipt", "reconcile", "raw", "tamper", "replay"], [10, 3, 2, 2, 1, 1]
    if forge:  # without --forge the generator draws exactly what the registered one drew
        kinds, weights = kinds + ["forge"], weights + [3]
    kind = rng.choices(kinds, weights)[0]
    op = {"kind": kind}
    if kind == "submit":
        op["decision"] = rng.choice(["ALLOW", "ALLOW", "DEFER", "REFUSE"])
        op["executor"] = rng.choice(["ok", "ok", "raise_before", "raise_after", "silent", "lie", "foreign"])
        op["observe"] = rng.random() < 0.4
        if rng.random() < 0.35:
            op["crash_at"] = rng.choice(FAULT_POINTS)
    elif kind == "receipt":
        op["variant"] = rng.choice(["valid", "other_command", "other_auth", "other_attempt", "failed", "garbage"])
    elif kind == "raw":
        op["to"] = rng.choice(sorted(s for s in ex.TRANSITIONS if s))
    elif kind == "forge":
        op["variant"], op["attempt"] = rng.choice(FORGE), f"f{rng.getrandbits(32):08x}"
    return op


def forge(journal, intent, op):
    """A well-formed direct append, as an orchestrator other than ExecutionCoordinator (or a buggy one) might write it.
    Returns a violation or None. `legal` is the fuzzer's model of fix 3's binding rules (derived from them, like `raw`)."""
    evs = journal.events(intent)
    st, v = evs[-1]["to"], op["variant"]
    auths = [e for e in evs if e["to"] == ex.AUTHORIZED]
    ctx = next((e["detail"].get("context") for e in reversed(evs) if e["to"] == ex.DISPATCHED), None)
    allow = {"decision": "ALLOW", "authorization_digest": "sha256:auth"}
    attempt = None
    if v == "authorize_fresh":
        to, detail, attempt = ex.AUTHORIZED, allow, op["attempt"]
        legal = ex.AUTHORIZED in ex.TRANSITIONS.get(st, frozenset())
    elif v == "authorize_reused":
        if not auths:
            return None
        to, detail, attempt, legal = ex.AUTHORIZED, allow, auths[-1]["attempt_id"], False
    elif v.startswith("dispatch"):
        if not auths:
            return None
        good = {"record_id": intent, "attempt_id": auths[-1]["attempt_id"], "command_digest": evs[0]["detail"]["command_digest"],
                "authorization_digest": auths[-1]["detail"]["authorization_digest"]}
        bad = {"dispatch_bound": good, "dispatch_other_command": dict(good, command_digest=ex.digest(OTHER_CMD)),
               "dispatch_other_record": dict(good, record_id="0" * 64)}[v]
        to, detail = ex.DISPATCHED, {"context": bad}  # no executor is called: a forged dispatch causes no effect
        legal = v == "dispatch_bound" and st == ex.AUTHORIZED
    elif v == "ack_receipt":
        if not isinstance(ctx, dict):
            return None
        to, detail, legal = ex.ACKNOWLEDGED, {"receipt": make_receipt(ctx)}, st == ex.DISPATCHED
    else:  # attest_*: the HMAC stand-in models a forger who holds the executor's key (X6's limit), so a valid receipt attests
        if not isinstance(ctx, dict):
            return None
        receipt = {"attest_valid": lambda: make_receipt(ctx),
                   "attest_foreign": lambda: make_receipt(dict(ctx, command_digest=ex.digest(OTHER_CMD))),
                   "attest_other_attempt": lambda: make_receipt(dict(ctx, attempt_id="ffff"))}[v]()
        to, detail = ex.ATTESTED, {"receipt": receipt}
        legal = v == "attest_valid" and ex.ATTESTED in ex.TRANSITIONS.get(st, frozenset())
    try:
        journal.append(intent, to, "forger", detail, attempt_id=attempt)
        if not legal:
            return f"forged {v}: illegal {st} -> {to} was accepted"
    except ex.IllegalTransition:
        if legal:
            return f"forged {v}: legal {st} -> {to} was refused"
    return None


def check(journal, world, intent):
    """Return a list of invariant violations (strings) for the current disk state."""
    try:
        evs = journal.events(intent)
    except ex.JournalCorrupt:
        return []  # I10: corruption detected is the correct outcome; the op that caused it is checked separately
    v = []
    for prev, e in zip([None] + evs, evs):
        if e["to"] == ex.DISPATCHED and prev and prev["to"] in (ex.REFUSED, ex.DEFERRED):
            v.append(f"I1/I2: DISPATCHED after {prev['to']}")
    disp = [i for i, e in enumerate(evs) if e["to"] == ex.DISPATCHED]
    for a, b in zip(disp, disp[1:]):
        if not any(e["to"] == ex.NO_EFFECT for e in evs[a:b]):
            v.append("I3: two DISPATCHED without RECONCILED_NO_EFFECT between them")
    effects = [w for w in world.effects() if w["record_id"] == intent]
    if len({w["attempt_id"] for w in effects}) > 1 + sum(e["to"] == ex.NO_EFFECT for e in evs):
        v.append(f"I4: {len(effects)} effects")
    # a DISPATCHED event may carry no context (a raw append): it binds nothing (deviation 2b: this line used to raise KeyError)
    contexts = {e["detail"]["context"].get("attempt_id"): e["detail"]["context"] for e in evs
                if e["to"] == ex.DISPATCHED and isinstance(e["detail"].get("context"), dict)}
    for i, e in enumerate(evs):
        if e["to"] == ex.ATTESTED:
            receipt = e["detail"].get("receipt") or next((x["detail"].get("receipt") for x in reversed(evs[:i])
                                                         if x["to"] == ex.ACKNOWLEDGED), None)
            ctx = contexts.get(e["attempt_id"])
            if receipt is None:
                v.append("I5: EFFECT_ATTESTED without a receipt")
            elif ctx is None or any(receipt.get(k) != ctx.get(k) for k in BINDING):
                v.append("I6/I7: EFFECT_ATTESTED by a receipt for another command/authorization/attempt")
    if evs and effects:
        last_attempt = evs[-1]["attempt_id"]
        if any(w["attempt_id"] == last_attempt for w in effects) and evs[-1]["to"] not in ADMITS_EFFECT:
            v.append(f"I8: effect happened, journal ends in {evs[-1]['to']}")
    return v


def run_sequence(ops, sabotage=False):
    """Run one sequence in a fresh directory. Returns (violation or None, step index)."""
    d = tempfile.mkdtemp()
    world = World(os.path.join(d, "world.jsonl"))
    saved, saved_admit, saved_check = ex.TRANSITIONS[ex.REFUSED], ex._admit, ex.ExecutionJournal._check_attestation
    if isinstance(sabotage, str) and sabotage.startswith("plant:"):
        ex._admit = plant(sabotage[6:], saved_admit)
        if sabotage == "plant:attest-binding":  # the signature check too, or the verifier still refuses
            ex.ExecutionJournal._check_attestation = lambda self, evs, detail: None
    elif sabotage:
        ex.TRANSITIONS[ex.REFUSED] = frozenset({ex.DISPATCHED})
    if sabotage == "deep":  # deviation 3: also remove fix 3's rule that a dispatch binds the authorization before it
        ex._admit = lambda intent, evs, to, *rest: None if to == ex.DISPATCHED else saved_admit(intent, evs, to, *rest)
    try:
        intent = ex.ExecutionJournal.intent_id("payments", "client:alice", "invoice-7")
        for i, op in enumerate(ops):
            co, journal = coordinator(d, world, op, sabotage)
            try:
                if op["kind"] == "submit":
                    co.submit("payments", "client:alice", "invoice-7", CMD, "sha256:auth")
                elif op["kind"] == "receipt" and os.path.exists(journal.path(intent)):
                    evs = journal.events(intent)
                    ctx = next((e["detail"].get("context") for e in reversed(evs) if e["to"] == ex.DISPATCHED), None)
                    if isinstance(ctx, dict) and all(isinstance(ctx.get(k), str) for k in BINDING):
                        r = {"valid": lambda: make_receipt(ctx),
                             "other_command": lambda: make_receipt(dict(ctx, command_digest="sha256:" + "1" * 64)),
                             "other_auth": lambda: make_receipt(dict(ctx, authorization_digest="sha256:other")),
                             "other_attempt": lambda: make_receipt(dict(ctx, attempt_id="ffff")),
                             "failed": lambda: make_receipt(ctx, "FAILED"),
                             "garbage": lambda: {"schema": "nope"}}[op["variant"]]()
                        before = journal.state(intent)
                        after = co.accept_receipt(intent, r)
                        if before in (ex.ATTESTED, ex.CONFIRMED, ex.FINALIZED, ex.DISPUTED, ex.REFUSED) and after != before:
                            return f"I9: a receipt changed terminal/settled state {before} -> {after}", i
                        if op["variant"] != "valid" and after == ex.ATTESTED and before != ex.ATTESTED:
                            return f"I6/I7: a {op['variant']} receipt attested", i
                elif op["kind"] == "reconcile" and os.path.exists(journal.path(intent)):
                    evs = journal.events(intent)
                    if evs and evs[-1]["to"] in (ex.UNCONFIRMED, ex.DISPUTED):
                        attempt = evs[-1]["attempt_id"]
                        if not any(w["attempt_id"] == attempt for w in world.effects()):  # an honest person
                            co.reconcile_no_effect(intent, "human:operator", "checked the bank: no transfer")
                elif op["kind"] == "raw" and os.path.exists(journal.path(intent)):
                    st = journal.state(intent)
                    # the raw caller is unprivileged ("fuzz") and carries no decision, context or receipt: claims about the
                    # world (NEEDS_BASIS) and transitions that need evidence (NEEDS_EVIDENCE) are not legal for it
                    # (deviation 2 added EFFECT_ATTESTED, I5; fix 3 added AUTHORIZED, DISPATCHED, EXECUTOR_ACKNOWLEDGED)
                    legal = (op["to"] in ex.TRANSITIONS.get(st, frozenset()) and op["to"] not in ex.NEEDS_BASIS
                             and op["to"] not in NEEDS_EVIDENCE)
                    try:
                        journal.append(intent, op["to"], "fuzz", {"basis": "fuzz"})
                        if not legal:
                            return f"illegal transition {st} -> {op['to']} was accepted", i
                    except ex.IllegalTransition:
                        if legal:
                            return f"legal transition {st} -> {op['to']} was refused", i
                    if op["to"] == ex.DISPATCHED and legal:
                        pass  # a raw DISPATCHED without an executor call: no effect; allowed by the table
                elif op["kind"] == "forge" and os.path.exists(journal.path(intent)):
                    found = forge(journal, intent, op)
                    if found:
                        return found, i
                elif op["kind"] in ("tamper", "replay") and os.path.exists(journal.path(intent)):
                    path = journal.path(intent)
                    raw = path.read_bytes()
                    if op["kind"] == "tamper":
                        path.write_bytes(raw.replace(b'"actor":"', b'"actor":"x', 1))
                    else:
                        lines = raw.splitlines(keepends=True)
                        path.write_bytes(raw + lines[-1])
                    try:
                        journal.events(intent)
                        return f"I10: a {op['kind']}ed journal was read as valid", i
                    except ex.JournalCorrupt:
                        path.write_bytes(raw)  # restore, so the sequence continues on a valid journal
            except Crash:
                pass  # restart: the next op builds a fresh coordinator over the same directory
            except (ex.IllegalTransition, ex.ConflictingIntent):
                pass
            except Exception as exc:  # the code under test raised something it does not declare: a finding, not a pass
                return f"unhandled {type(exc).__name__} in the code under test: {exc!r}", i
            violations = check(ex.ExecutionJournal(os.path.join(d, "journal")), world, intent)
            if violations:
                return violations[0], i
        return None, None
    finally:
        ex.TRANSITIONS[ex.REFUSED], ex._admit, ex.ExecutionJournal._check_attestation = saved, saved_admit, saved_check
        shutil.rmtree(d, ignore_errors=True)


def vclass(violation):
    """The invariant a violation names (I5, I6/I7, ...) or its kind ('legal transition', 'illegal transition')."""
    head = violation.split(":", 1)[0]
    return head if head[:1] == "I" and head[1:2].isdigit() else " ".join(violation.split()[:2])


def minimize(ops, sabotage, cls):
    """Delta debugging: drop ops while the sequence still fails with the same class of violation (deviation 2: it used to
    accept any violation, so the printed minimized sequence could fail for a different reason than the one printed)."""
    changed = True
    while changed:
        changed = False
        for i in range(len(ops)):
            trial = ops[:i] + ops[i + 1:]
            got = run_sequence(trial, sabotage)[0] if trial else None
            if got and vclass(got) == cls:
                ops, changed = trial, True
                break
    return ops


def main(argv):
    n, seed, forge_ops = 2000, 20261007, "--forge" in argv
    sabotage = "deep" if "--sabotage-deep" in argv else "--sabotage" in argv
    if "--plant" in argv:
        rule = argv[argv.index("--plant") + 1]
        if rule not in ("dispatch-binding", "attempt-reuse", "attest-binding"):
            print(f"unknown --plant {rule!r}")
            return 2
        sabotage = "plant:" + rule
    if "--sequences" in argv:
        n = int(argv[argv.index("--sequences") + 1])
    if "--seed" in argv:
        seed = int(argv[argv.index("--seed") + 1])
    rng = random.Random(seed)
    from collections import Counter
    ops_count, found = Counter(), None
    for s in range(n):
        ops = [gen_op(rng, forge_ops) for _ in range(rng.randint(1, 12))]
        ops_count.update(o["kind"] for o in ops)
        violation, step = run_sequence(ops, sabotage)
        if violation:
            found = (s, violation, ops[:step + 1])
            break
    mode = ({False: "registered", True: "SABOTAGE", "deep": "SABOTAGE-DEEP (deviation 3)"}.get(sabotage)
            or f"PLANTED {sabotage[6:]} (anti-vacuity)") + (" +forge" if forge_ops else "")
    print(f"ex1_fuzz | {n} sequences (seed {seed}) | ops tried: {dict(ops_count)}")
    if found is None:
        print(f"mode: {mode}")
        print(f"VERDICT  0 violations in {n} sequences")
        return 0
    s, violation, ops = found
    small = minimize(ops, sabotage, vclass(violation))
    print(f"  VIOLATION in sequence {s}: {violation}")
    print(f"  minimized to {len(small)} op(s) of the same class ({vclass(violation)}): {json.dumps(small)}")
    print(f"  the minimized sequence reports: {run_sequence(small, sabotage)[0]}")
    print(f"mode: {mode}")
    print("VERDICT  violation found")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
