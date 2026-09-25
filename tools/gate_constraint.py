#!/usr/bin/env python3
"""gate_constraint.py - is the Sovereign Veritas gate boringly constrained?

One invariant: the set of inputs the gate ALLOWs must equal the set a
fail-closed spec allows. Integration may shrink that set, never widen it.

Spec sources (not the code under test):
  DOC   decision classes and REFUSE ordering (ARCHITECTURE / handoff s14),
        DEFER reasons accumulate, REFUTED keeps a distinct reason.
  RULE  "missing input means deny": a missing, unrecognized, mistyped or
        explicitly negative input must never reach ALLOW.
  KNOWN RULE cases that leak by declared design (opt-in constraints). Each is
        listed with its reason. A KNOWN case that stops leaking also fails, so
        the list cannot go stale; a leak not on the list fails.

Exit: 0 looked, clean | 1 looked, found | 2 could not look.
  python tools/gate_constraint.py --target .            gate + workflow checks
  python tools/gate_constraint.py --target . --mutants  the instrument's killer
Stdlib only. Writes nothing into the target; mutant copies go under $HOME
and are removed afterwards.
"""
import argparse, hashlib, inspect, itertools, json, os, platform, shutil, subprocess, sys, tempfile

sys.dont_write_bytecode = True
VERSION = "gate_constraint v2"
MISSING, NOVERIF = object(), object()
GOOD_DIGEST = hashlib.sha256(b"baseline-input").hexdigest()
STRICT = {"ALLOW": 0, "DEFER": 1, "REFUSE": 2}

KNOWN_OPT_IN = {
    "single:digest='x' malformed": "digest presence is checked, not its format",
    "single:action.capability missing": "action/capability binding is opt-in",
    "single:action missing": "no action proposal means no binding or policy check",
    "single:step_count missing": "max_steps is advisory unless step_count is supplied",
    "single:policy absent": "policy is optional",
    "wf:wf_identity_unbound": "workflow does not check the verifier object is the one registered",
    "wf:wf_no_registry": "verifier provenance is opt-in: no registry, no verifier_id",
}


def could_not_look(msg):
    print(f"COULD NOT LOOK: {msg}")
    sys.exit(2)


class SV:  # the code under test, resolved from --target and nowhere else
    pass


def load(target):
    target = os.path.realpath(target)
    pkg = os.path.join(target, "sovereign_veritas")
    if not os.path.isdir(pkg):
        could_not_look(f"no sovereign_veritas/ under {target}")
    sys.path.insert(0, target)
    try:
        import sovereign_veritas
        from sovereign_veritas.decision import Gate
        from sovereign_veritas.capability import Capability, CapabilityRegistry
        from sovereign_veritas.evidence import EvidenceRecord
        from sovereign_veritas.runtime import RuntimeState
        from sovereign_veritas.verifier_registry import VerifierRegistry
        from sovereign_veritas.workflow import EvidenceWorkflow
        from sovereign_veritas.interfaces.contracts import ActionProposal, Prediction
    except Exception as exc:
        could_not_look(f"{type(exc).__name__}: {exc}")
    got = os.path.realpath(os.path.dirname(sovereign_veritas.__file__))
    if got != os.path.realpath(pkg):
        could_not_look(f"imported {got}, not {pkg} - an installed copy shadows the target")
    if "registry" not in inspect.signature(Gate.evaluate).parameters or \
            "verifier_id" not in inspect.signature(EvidenceWorkflow.run).parameters:
        could_not_look("not the integrated API (Gate.evaluate(registry=), run(verifier_id=))")
    sv = SV()
    for k, v in dict(Gate=Gate, Capability=Capability, CapabilityRegistry=CapabilityRegistry,
                     EvidenceRecord=EvidenceRecord, RuntimeState=RuntimeState,
                     VerifierRegistry=VerifierRegistry, EvidenceWorkflow=EvidenceWorkflow,
                     ActionProposal=ActionProposal, Prediction=Prediction).items():
        setattr(sv, k, v)
    sv.pkg = pkg
    return sv


def cap_registry(sv):
    reg = sv.CapabilityRegistry()
    reg.register(sv.Capability("root-on", authorized=True))
    reg.register(sv.Capability("root-off", authorized=False))
    reg.register(sv.Capability("root-str", authorized="false"))
    return reg


BASE = dict(digest=GOOD_DIGEST, status="PASS", action=True, binding="read_sensor",
            requested="read_sensor", cap=True, authorized=True, parent=None, capreg=True,
            thermal="normal", compute="available", power="stable", evidence=True,
            quality=0.9, steps=1, policy=["read_sensor"])


def evaluate(sv, creg, cfg):
    c = dict(BASE, **cfg)
    verification = None
    if c["status"] is not NOVERIF:
        verification = {} if c["status"] is MISSING else {"status": c["status"]}
    action = None
    if c["action"]:
        action = {"requested": c["requested"]}
        if c["binding"] is not MISSING:
            action["capability"] = c["binding"]
    metadata = {}
    for key, name in (("evidence", "calibration"), ("quality", "evidence_quality"),
                      ("steps", "step_count")):
        if c[key] is not MISSING:
            metadata[name] = c[key]
    try:
        record = sv.EvidenceRecord(record_id="gc", input_digest=c["digest"],
                                   verification=verification, action=action, metadata=metadata,
                                   timestamp="2026-01-01T00:00:00+00:00")
    except Exception as exc:  # input rejected before it can become evidence
        return f"REJECTED:{type(exc).__name__}", ()
    cap = (sv.Capability("read_sensor", authorized=c["authorized"],
                         required_evidence=("calibration",), parent=c["parent"],
                         min_evidence_quality=0.5, max_steps=3) if c["cap"] else None)
    runtime = sv.RuntimeState("gate-constraint", "n/a", thermal_status=c["thermal"],
                              compute_budget=c["compute"], power_status=c["power"])
    policy = None if c["policy"] is MISSING else {"allow_only": c["policy"]}
    try:
        d = sv.Gate().evaluate(record, cap, runtime, policy=policy,
                               registry=creg if c["capreg"] else None)
        return d.decision, tuple(d.reasons)
    except Exception as exc:  # a crash is never a verdict
        return f"RAISE:{type(exc).__name__}", ()


S = []  # (id, cfg, expect, tier, reason prefix that must appear)
def case(cid, cfg, expect, tier="DOC", reason=None):
    S.append((cid, cfg, expect, tier, reason))

case("baseline", {}, "ALLOW")
case("thermal=cool", {"thermal": "cool"}, "ALLOW")
case("thermal=warning", {"thermal": "warning"}, "DEFER")
case("compute=constrained", {"compute": "constrained"}, "ALLOW")
case("digest=''", {"digest": ""}, "REFUSE")
case("digest=None", {"digest": None}, "REFUSE")
case("digest='x' malformed", {"digest": "x"}, "NOT_ALLOW", "RULE")
for st in ("FAIL", "NOT_VERIFIED", "UNKNOWN", "pass", "PASS ", True):
    case(f"status={st!r}", {"status": st}, "REFUSE")
case("status=REFUTED", {"status": "REFUTED"}, "REFUSE", reason="verification_refuted")
case("status=INSUFFICIENT", {"status": "INSUFFICIENT_EVIDENCE"}, "DEFER")
case("status missing", {"status": MISSING}, "REFUSE")
case("verification=None", {"status": NOVERIF}, "REFUSE")
case("capability=None", {"cap": False}, "REFUSE")
case("authorized=False", {"authorized": False}, "REFUSE")
case("authorized='false'", {"authorized": "false"}, "NOT_ALLOW", "RULE")
case("authorized='0'", {"authorized": "0"}, "NOT_ALLOW", "RULE")
case("parent authorized", {"parent": "root-on"}, "ALLOW")
case("parent unauthorized", {"parent": "root-off"}, "REFUSE")
case("parent unregistered", {"parent": "root-nope"}, "REFUSE")
case("parent, no registry passed", {"parent": "root-on", "capreg": False}, "REFUSE")
case("parent authorized='false'", {"parent": "root-str"}, "NOT_ALLOW", "RULE")
case("action.capability=other", {"binding": "write_actuator"}, "REFUSE")
case("action.capability missing", {"binding": MISSING}, "NOT_ALLOW", "RULE")
case("action missing", {"action": False}, "NOT_ALLOW", "RULE")
case("thermal=hot", {"thermal": "hot"}, "DEFER")
case("thermal=unknown", {"thermal": "unknown"}, "REFUSE")
case("thermal=''", {"thermal": ""}, "REFUSE")
for field, vals in (("thermal", ("NORMAL", None, ["normal"])),
                    ("compute", ("EXHAUSTED", "depleted", None)),
                    ("power", ("UNSAFE", "critical", None))):
    for v in vals:
        case(f"{field}={v!r}", {field: v}, "NOT_ALLOW", "RULE")
case("compute=exhausted", {"compute": "exhausted"}, "DEFER")
case("compute=unavailable", {"compute": "unavailable"}, "REFUSE")
case("power=unsafe", {"power": "unsafe"}, "DEFER")
case("power=unavailable", {"power": "unavailable"}, "REFUSE")
case("evidence missing", {"evidence": MISSING}, "DEFER")
case("evidence=False", {"evidence": False}, "DEFER")
for v in ("FAILED", {"ok": False}, "false"):
    case(f"evidence={v!r}", {"evidence": v}, "NOT_ALLOW", "RULE")
case("quality=0.2", {"quality": 0.2}, "DEFER")
case("quality missing", {"quality": MISSING}, "DEFER")
case("quality='high'", {"quality": "high"}, "DEFER")
for v in (float("nan"), float("inf"), 2.0):
    case(f"quality={v!r}", {"quality": v}, "NOT_ALLOW", "RULE")
case("step_count=5 > max 3", {"steps": 5}, "REFUSE")
case("step_count='x'", {"steps": "x"}, "DEFER")
case("step_count=-5", {"steps": -5}, "NOT_ALLOW", "RULE")
case("step_count=True", {"steps": True}, "NOT_ALLOW", "RULE")
case("step_count missing", {"steps": MISSING}, "NOT_ALLOW", "RULE")
case("policy excludes action", {"policy": ["other"]}, "REFUSE")
case("policy absent", {"policy": MISSING}, "NOT_ALLOW", "RULE")
case("allow_only is a str", {"policy": "read_sensor_raw"}, "NOT_ALLOW", "RULE")


def single_ok(decision, reasons, expect, reason):
    if expect == "NOT_ALLOW":
        ok = decision != "ALLOW" and not decision.startswith("RAISE")
    else:
        ok = decision == expect
    return ok and (reason is None or any(r.startswith(reason) for r in reasons))


class _Verifier:
    def __init__(self, out):
        self.out = out

    def verify(self, observation, prediction):
        return dict(self.out)


def workflow(sv, verifier, registry, verifier_id, explicit_gate=False):
    class Sensor:
        def observe(self):
            return "obs"

    class Predictor:
        def predict(self, observation):
            return sv.Prediction(value="p", uncertainty=0.1, model_id="m")

    class Executor:
        calls = 0

        def execute(self, action):
            Executor.calls += 1
            return {"executed": action.requested}

    class Sink:
        def record(self, record):
            return record

    try:
        wf = sv.EvidenceWorkflow(sensor=Sensor(), predictor=Predictor(), verifier=verifier,
                                 executor=Executor(), evidence_sink=Sink(),
                                 gate=sv.Gate() if explicit_gate else None,
                                 verifier_registry=registry)
        wf.run(record_id="wf", input_digest=GOOD_DIGEST,
               capability=sv.Capability("read_sensor", authorized=True,
                                        required_evidence=("calibration",)),
               runtime=sv.RuntimeState("gate-constraint", "n/a"),
               action=sv.ActionProposal("read_sensor", "read_sensor", {}),
               policy={"allow_only": ["read_sensor"]}, metadata={"calibration": True},
               verifier_id=verifier_id)
    except Exception as exc:
        return f"RAISE:{type(exc).__name__}"
    return "EXECUTED" if Executor.calls else "HELD"


def workflow_cases(sv):
    ok_v = _Verifier({"status": "PASS"})
    failed_v = _Verifier({"status": "PASS"})
    untested_v = _Verifier({"status": "PASS", "verifier_id": "v-ok"})  # output lies about id
    impostor = _Verifier({"status": "PASS"})
    reg = sv.VerifierRegistry(min_coverage=0.5)
    reg.register("v-ok", ok_v)
    reg.record_probe("v-ok", passed=True, meaningful=True)
    reg.register("v-failed", failed_v)
    reg.record_probe("v-failed", passed=False, meaningful=True)
    reg.register("v-untested", untested_v)
    return [  # (id, label, verifier, registry, verifier_id, explicit gate, expect, tier)
        ("wf_liveness", "validated verifier executes", ok_v, reg, "v-ok", False, "EXECUTED", "DOC"),
        ("wf_failed_held", "failed verifier is held", failed_v, reg, "v-failed", False, "HELD", "DOC"),
        ("wf_explicit_gate", "explicit gate keeps registry", failed_v, reg, "v-failed", True, "HELD",
         "DOC"),
        ("wf_output_cannot_claim_id", "verifier output cannot override declared id", untested_v,
         reg, "v-untested", False, "HELD", "DOC"),
        ("wf_id_omitted", "configured registry bypassed by omitting verifier_id", failed_v, reg,
         None, False, "HELD", "RULE"),
        ("wf_identity_unbound", "declared id not bound to the verifier object", impostor, reg,
         "v-ok", False, "HELD", "RULE"),
        ("wf_no_registry", "no registry and no id: provenance unchecked", failed_v, None, None,
         False, "HELD", "RULE"),
    ]


AXES = [
    ("digest", [(GOOD_DIGEST, None), ("", ("REFUSE", "evidence_invalid"))]),
    ("status", [("PASS", None), ("INSUFFICIENT_EVIDENCE", ("DEFER", "verification_insufficient")),
                ("FAIL", ("REFUSE", "verification_not_passed"))]),
    ("authorized", [(True, None), (False, ("REFUSE", "capability_not_authorized"))]),
    ("parent", [(None, None), ("root-off", ("REFUSE", "capability_parent_not_authorized"))]),
    ("binding", [("read_sensor", None), ("write_actuator", ("REFUSE", "action_capability_mismatch"))]),
    ("thermal", [("normal", None), ("hot", ("DEFER", "runtime_not_healthy")),
                 ("unknown", ("REFUSE", "runtime_state_unavailable"))]),
    ("compute", [("available", None), ("exhausted", ("DEFER", "runtime_not_healthy"))]),
    ("evidence", [(True, None), (MISSING, ("DEFER", "missing_required_evidence"))]),
    ("quality", [(0.9, None), (0.2, ("DEFER", "evidence_quality_below"))]),
    ("steps", [(1, None), (5, ("REFUSE", "capability_max_steps_exceeded"))]),
    ("policy", [(["read_sensor"], None), (["other"], ("REFUSE", "action_not_permitted"))]),
]
REFUSE_ORDER = ["digest", "status", "authorized", "parent", "binding", "thermal", "steps", "policy"]
PREFIXES = sorted({f[1] for _, vals in AXES for _, f in vals if f}, key=len, reverse=True)


def lattice(sv, creg, recheck):
    points = list(itertools.product(*[range(len(v)) for _, v in AXES]))
    cfg = lambda p: {AXES[i][0]: AXES[i][1][k][0] for i, k in enumerate(p)}
    res = {p: evaluate(sv, creg, cfg(p)) for p in points}
    nondet = sum(evaluate(sv, creg, cfg(p)) != res[p] for p in points) if recheck else 0
    spec_bad, mono_bad = [], 0
    for p in points:
        faults = [(AXES[i][0], AXES[i][1][k][1]) for i, k in enumerate(p) if k]
        refuse = [(n, f[1]) for n, f in faults if f[0] == "REFUSE"]
        if refuse:
            want = ("REFUSE", {min(refuse, key=lambda x: REFUSE_ORDER.index(x[0]))[1]})
        else:
            defer = {f[1] for _, f in faults if f[0] == "DEFER"}
            want = ("DEFER", defer) if defer else ("ALLOW", set())
        dec, reasons = res[p]
        got = {next((x for x in PREFIXES if r.startswith(x)), "UNMAPPED:" + r) for r in reasons}
        if (dec, got) != want:
            spec_bad.append((want[0], dec))
        for i, k in enumerate(p):
            if k == 0:
                for kb in range(1, len(AXES[i][1])):
                    q = p[:i] + (kb,) + p[i + 1:]
                    if STRICT.get(res[q][0], -1) < STRICT.get(dec, 3):
                        mono_bad += 1
    return points, res, spec_bad, mono_bad, nondet


def run_checks(sv, recheck=True):
    creg = cap_registry(sv)
    failing, rows, table = [], [], []
    for cid, cfg, expect, tier, reason in S:
        dec, reasons = evaluate(sv, creg, cfg)
        ok = single_ok(dec, reasons, expect, reason)
        rows.append(("single:" + cid, dec, expect, tier, ok))
        table.append([cid, dec, list(reasons)])
    for wid, label, verifier, reg, vid, explicit, expect, tier in workflow_cases(sv):
        got = workflow(sv, verifier, reg, vid, explicit)
        rows.append(("wf:" + wid, got, expect, tier, got == expect, label))
        table.append([wid, got, []])
    known_hit = []
    for r in rows:
        rid, ok = r[0], r[4]
        if rid in KNOWN_OPT_IN:
            (known_hit.append(rid) if not ok else failing.append("stale-known:" + rid))
        elif not ok:
            failing.append(rid)
    points, res, spec_bad, mono_bad, nondet = lattice(sv, creg, recheck)
    table += [["L" + "".join(map(str, p)), res[p][0], list(res[p][1])] for p in points]
    failing += [n for n, bad in (("lattice:spec", spec_bad), ("lattice:mono", mono_bad),
                                 ("lattice:determinism", nondet)) if bad]
    digest = hashlib.sha256(json.dumps(table, separators=(",", ":")).encode()).hexdigest()
    return failing, rows, known_hit, (len(points), spec_bad, mono_bad, nondet), digest


def md5(path):
    with open(path, "rb") as fh:
        return hashlib.md5(fh.read()).hexdigest()


def report(sv, failing, rows, known_hit, lat, digest):
    print(f"{VERSION} | python {platform.python_version()} {platform.machine()}")
    print(f"target {sv.pkg}")
    for f in ("decision.py", "runtime.py", "verification.py", "workflow.py"):
        print(f"  md5 {md5(os.path.join(sv.pkg, f))}  {f}")
    print(f"LIVENESS  baseline -> {rows[0][1]}  {'ok' if rows[0][4] else 'FAIL (dead gate?)'}")
    doc = [r for r in rows if r[3] == "DOC"]
    doc_bad = [r for r in doc if not r[4]]
    print(f"DOC       {len(doc) - len(doc_bad)}/{len(doc)} documented cases match")
    for r in doc_bad:
        print(f"  MISMATCH {r[0]}: got {r[1]}, want {r[2]}")
    rule = [r for r in rows if r[3] == "RULE"]
    leaks = [r for r in rule if not r[4] and r[0] not in KNOWN_OPT_IN]
    print(f"RULE      {len(leaks)} unexpected of {len(rule)} fail-closed cases:")
    for r in leaks:
        print(f"  {r[1]:<9} {r[0]}")
    print(f"KNOWN     {len(known_hit)}/{len(KNOWN_OPT_IN)} declared opt-ins still leak (listed in KNOWN_OPT_IN)")
    for f in failing:
        if f.startswith("stale-known:"):
            print(f"  STALE    {f[12:]} no longer leaks - remove it from KNOWN_OPT_IN")
    n, spec_bad, mono_bad, nondet = lat
    kinds = {}
    for want, got in spec_bad:
        kinds[f"want {want} got {got}"] = kinds.get(f"want {want} got {got}", 0) + 1
    print(f"LATTICE   {n} points: {len(spec_bad)} spec, {mono_bad} monotonicity, "
          f"{nondet} nondeterministic")
    for k, v in sorted(kinds.items()):
        print(f"  {v:>5}  {k}")
    print(f"DIGEST    {digest}")
    print(f"VERDICT   {'CLEAN' if not failing else f'FOUND {len(failing)} failing checks'}")


MUTANTS = [  # (id, description, file, anchor, replacement); anchors must match exactly once
    ("M00", "null mutant (copy only) - must SURVIVE", "decision.py", "", ""),
    ("M01", "control: always ALLOW", "decision.py", "        policy = policy or {}\n",
     "        return Decision(\"ALLOW\")\n        policy = policy or {}\n"),
    ("M02", "control: always REFUSE (dead gate)", "decision.py", "        policy = policy or {}\n",
     "        return Decision(\"REFUSE\", (\"mutant\",))\n        policy = policy or {}\n"),
    ("M03", "drop input-digest check", "decision.py", "if not evidence.input_digest:", "if False:"),
    ("M04", "REFUTED no longer refuses", "verification.py",
     '    VerificationStatus.REFUTED: "verification_refuted",\n', ""),
    ("M05", "authorization by truthiness", "decision.py", "if capability.authorized is not True:",
     "if not capability.authorized:"),
    ("M06", "drop action/capability binding", "decision.py",
     "if requested_capability and requested_capability != capability.name:", "if False:"),
    ("M07", "drop runtime availability check", "decision.py", "if not runtime.is_available():",
     "if False:"),
    ("M08", "INSUFFICIENT short-circuits (masks REFUSE)", "decision.py",
     'reasons.append("verification_insufficient_evidence")',
     'return Decision("DEFER", ("verification_insufficient_evidence",))'),
    ("M09", "unhealthy runtime short-circuits", "decision.py",
     'reasons.append("runtime_not_healthy")', 'return Decision("DEFER", ("runtime_not_healthy",))'),
    ("M10", "INSUFFICIENT_EVIDENCE allows", "decision.py",
     'reasons.append("verification_insufficient_evidence")', "pass"),
    ("M11", "drop policy check", "decision.py",
     "if requested and allow_only is not None and requested not in allow_only:", "if False:"),
    ("M12", "runtime vocabulary accepts any string", "runtime.py",
     "return isinstance(value, str) and any(value in s for s in sets)",
     "return isinstance(value, str)"),
    ("M13", "required evidence by truthiness", "decision.py",
     "if evidence.metadata.get(name) is not True:", "if not evidence.metadata.get(name):"),
    ("M14", "drop quality validity check", "decision.py",
     "if not (math.isfinite(quality) and 0.0 <= quality <= 1.0):", "if False:"),
    ("M15", "drop policy type check", "decision.py",
     "if allow_only is not None and not isinstance(allow_only, (list, tuple, set, frozenset)):",
     "if False:"),
    ("M16", "omitted verifier_id bypasses registry", "workflow.py",
     "if verifier_id is None and self.verifier_registry is not None:", "if False:"),
    ("M17", "max_steps overrun only defers", "decision.py",
     'return Decision("REFUSE", (f"capability_max_steps_exceeded:{step_count}>{capability.max_steps}",))',
     'reasons.append(f"capability_max_steps_exceeded:{step_count}>{capability.max_steps}")'),
    ("M18", "parent authorization by truthiness", "decision.py",
     "if parent.authorized is not True:", "if not parent.authorized:"),
    ("M19", "REFUTED loses its distinct reason", "verification.py",
     'VerificationStatus.REFUTED: "verification_refuted"',
     'VerificationStatus.REFUTED: "verification_not_passed"'),
]


def run_mutants(sv, base_failing, base_digest):
    print("MUTANTS   differential: KILLED = new failing checks vs the unmutated target")
    bad = 0
    for mid, desc, fname, old, new in MUTANTS:
        tmp = tempfile.mkdtemp(prefix="gc_mut_", dir=os.path.expanduser("~"))
        try:
            shutil.copytree(sv.pkg, os.path.join(tmp, "sovereign_veritas"),
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            path = os.path.join(tmp, "sovereign_veritas", fname)
            if old:
                with open(path, encoding="utf-8") as fh:
                    src = fh.read()
                if src.count(old) != 1:
                    print(f"  {mid} INVALID  anchor matched {src.count(old)}x  {desc}")
                    bad = 2
                    continue
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(src.replace(old, new))
            flags = ["--report-json"] + (["--recheck"] if mid == "M00" else [])
            p = subprocess.run([sys.executable, os.path.abspath(__file__), "--target", tmp] + flags,
                               capture_output=True, text=True, timeout=600,
                               env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
            try:
                out = json.loads(p.stdout.strip().splitlines()[-1])
            except Exception:
                print(f"  {mid} ERROR    rc={p.returncode} {p.stdout.strip()[-80:]}  {desc}")
                bad = 2
                continue
            new_fail = sorted(set(out["failing"]) - set(base_failing))
            if mid == "M00":
                same = not new_fail and out["digest"] == base_digest
                print(f"  {mid} {'SURVIVED' if same else 'HARNESS BROKEN'} digest "
                      f"{'identical' if out['digest'] == base_digest else 'DIFFERS'}  {desc}")
                bad = bad if same else max(bad, 1)
            else:
                print(f"  {mid} {'KILLED  ' if new_fail else 'SURVIVED'} +{len(new_fail):<3} {desc}")
                bad = bad if new_fail else max(bad, 1)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    print(f"MUTANT VERDICT  {'instrument can fail both ways' if bad == 0 else 'instrument NOT validated'}"
          f" (exit {bad}; gate findings above are reported, not gated, here)")
    return bad


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--target", default=".")
    ap.add_argument("--mutants", action="store_true")
    ap.add_argument("--report-json", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--recheck", action="store_true", help=argparse.SUPPRESS)
    args = ap.parse_args()
    sv = load(args.target)
    failing, rows, known_hit, lat, digest = run_checks(sv, recheck=not args.report_json or args.recheck)
    if args.report_json:
        print(json.dumps({"failing": failing, "digest": digest}))
        sys.exit(0)
    report(sv, failing, rows, known_hit, lat, digest)
    if args.mutants:
        sys.exit(run_mutants(sv, failing, digest))
    sys.exit(1 if failing else 0)


if __name__ == "__main__":
    main()
