#!/usr/bin/env python3
"""verify_package.py - challenge an sv.package/0 evidence package without the producer's code.

Stdlib only. Imports nothing from sovereign_veritas: digests, the Gate, runtime vocabulary,
thermal classification and verifier-validation rules are re-implemented here from the
documented contract. Same author as the producer, so this is N-version, not independent.

  python tools/verify_package.py PACKAGE.json [--allow-recorded-only]
         [--signature PACKAGE.json.sig --allowed-signers FILE --identity ID]
         [--witness-log witness/packages.log]
      exit 0 all checks pass | 1 a check failed | 2 unreadable, or a signature or witness check
      could not run

A passing package is internally consistent and its decision is the one the documented Gate
produces from its recorded inputs. Without --signature it is NOT proven authentic. With it, the
package file's exact bytes must carry a valid ssh-keygen signature (namespace "sv-package") from
ID's key in the allowed-signers file. With --witness-log, the package must be the LAST entry of an
append-only witness log that you pulled yourself (a log handed to you by the producer proves
nothing). That shows it is the newest package the author made public - order, not time, and not
packages the author never logged. The VERDICT line reports each layer separately: authenticity is
SIGNED whenever the signature check passed, even if another check failed.
"""
import base64, hashlib, json, math, os, shutil, subprocess, sys, tempfile

NAMESPACE = "sv-package"


class SignatureUnavailable(Exception):
    """ssh-keygen missing or unusable: the signature could not be checked at all."""


WITNESS_HEADER = "# sv witness log v0"


class WitnessUnreadable(Exception):
    """The witness log is missing or malformed: freshness could not be judged at all."""


def read_witness_log(path):
    """[(seq, sha256)] with seq 1..n strictly increasing and unique 64-hex digests."""
    try:
        with open(path, encoding="utf-8") as fh:
            lines = [l.rstrip("\n") for l in fh]
    except OSError as exc:
        raise WitnessUnreadable(str(exc))
    if not lines or lines[0] != WITNESS_HEADER:
        raise WitnessUnreadable(f"first line must be {WITNESS_HEADER!r}")
    entries, seen = [], set()
    for n, line in enumerate(lines[1:], start=2):
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) != 2 or not parts[0].isdigit():
            raise WitnessUnreadable(f"line {n}: expected '<seq> <sha256>'")
        seq, digest = int(parts[0]), parts[1]
        if seq != len(entries) + 1:
            raise WitnessUnreadable(f"line {n}: seq {seq}, expected {len(entries) + 1}")
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise WitnessUnreadable(f"line {n}: not a lowercase sha256")
        if digest in seen:
            raise WitnessUnreadable(f"line {n}: digest already logged")
        seen.add(digest)
        entries.append((seq, digest))
    return entries


def check_witness(pkg, log_path):
    """(ok, status, detail). ok only when the package is the last witnessed entry."""
    entries = read_witness_log(log_path)
    digest = pkg.get("package_sha256")
    seqs = [s for s, d in entries if d == digest]
    if not seqs:
        return False, "NOT_WITNESSED", f"not among {len(entries)} witnessed packages"
    later = len(entries) - seqs[0]
    if later:
        return False, "STALE", f"entry {seqs[0]} of {len(entries)}: {later} newer package(s) witnessed"
    return True, f"LATEST_WITNESSED({seqs[0]})", f"entry {seqs[0]} of {len(entries)}, the last"


def check_signature(data, sig_path, allowed_signers, identity):
    """(ok, detail) for a detached ssh-keygen signature over `data` (bytes)."""
    exe = shutil.which("ssh-keygen")
    if exe is None:
        raise SignatureUnavailable("ssh-keygen not found (Termux: pkg install openssh)")
    try:
        p = subprocess.run([exe, "-Y", "verify", "-f", allowed_signers, "-I", identity,
                            "-n", NAMESPACE, "-s", sig_path], input=data, capture_output=True,
                           timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        raise SignatureUnavailable(str(exc))
    if p.returncode == 0:
        return True, f"valid {NAMESPACE} signature by {identity}"
    msg = (p.stderr or p.stdout).decode("utf-8", "replace").strip().splitlines()
    return False, msg[0] if msg else f"ssh-keygen exit {p.returncode}"

SCHEMA = "sv.package/0"
# v0 packages carry exactly these four statements. Exact match: an appended line could contradict
# one ("authenticity: signed by hardware") while every required prefix is still present.
V0_LIMITATIONS = (
    "freshness: NOT_PROVEN - no external witness; an older valid package is indistinguishable",
    "authenticity: none - no signature; a fully consistent rewrite verifies",
    "verifier identity: the verifier_id is declared by the caller, not bound to the verifier object",
    "resource state: runtime fields are declared by the caller, not derived from thermal zones",
)
# A package whose runtime says thermal_status_source == "measured" states this as its fourth line
# instead, and must pass thermal_status_derived: the status is recomputed here, not trusted.
MEASURED_RESOURCE_STATEMENT = (
    "resource state: thermal_status derived from measurement.thermal_before under the uncalibrated "
    "per-domain limits named in resource_state.thermal_policy; compute_budget and power_status "
    "declared by the caller")


def canon(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha(text_or_bytes):
    data = text_or_bytes.encode("utf-8") if isinstance(text_or_bytes, str) else text_or_bytes
    return hashlib.sha256(data).hexdigest()


# ---- Gate, re-implemented from the documented contract -------------------------------------
STATUSES = {"PASS", "FAIL", "REFUTED", "INSUFFICIENT_EVIDENCE", "NOT_VERIFIED", "UNKNOWN"}
REFUSE_STATUS = {"FAIL": "verification_not_passed", "NOT_VERIFIED": "verification_not_passed",
                 "UNKNOWN": "verification_not_passed", "REFUTED": "verification_refuted"}
VOCAB = {
    "thermal_status": ({"normal", "cool"}, {"warning", "high", "hot", "critical", "unsafe"}),
    "compute_budget": ({"available", "constrained", "low"}, {"exhausted"}),
    "power_status": ({"stable"}, {"unsafe"}),
}


def coerce_status(value):
    if value is None:
        return "NOT_VERIFIED"
    s = str(value)
    return s if s in STATUSES else "UNKNOWN"


def runtime_available(rt):
    return all(isinstance(rt.get(f), str) and (rt[f] in ok or rt[f] in bad)
               for f, (ok, bad) in VOCAB.items())


def runtime_healthy(rt):
    return all(isinstance(rt.get(f), str) and rt[f] in ok for f, (ok, _) in VOCAB.items())


def as_quality(value):
    """A JSON number as a float; None for anything else (booleans and strings included)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        return float(value)
    except OverflowError:
        return math.inf if value > 0 else -math.inf


def quality_of(rec):
    """Top-level evidence_quality if present (not a number: 0.0), else metadata's, else 0.0."""
    if rec.get("evidence_quality") is not None:
        q = as_quality(rec["evidence_quality"])
        return 0.0 if q is None else q
    q = as_quality((rec.get("metadata") or {}).get("evidence_quality"))
    return 0.0 if q is None else q


def replay_gate(rec, cap, registry, runtime, policy):
    policy = policy or {}
    reasons = []
    if not rec.get("input_digest"):
        return "REFUSE", ["evidence_invalid:missing_input_digest"]
    ver = rec.get("verification")
    status = coerce_status(None if ver is None else ver.get("status"))
    if status in REFUSE_STATUS:
        return "REFUSE", [REFUSE_STATUS[status]]
    if status == "INSUFFICIENT_EVIDENCE":
        reasons.append("verification_insufficient_evidence")
    elif status != "PASS":
        return "REFUSE", ["verification_not_passed"]
    if cap is None:
        return "REFUSE", ["capability_missing"]
    if cap.get("authorized") is not True:
        return "REFUSE", ["capability_not_authorized"]
    parent = cap.get("parent")
    if parent:
        if registry is None:
            return "REFUSE", ["capability_parent_requires_registry"]
        pcap = registry.get(parent)
        if pcap is None:
            return "REFUSE", [f"capability_parent_missing:{parent}"]
        if pcap.get("authorized") is not True:
            return "REFUSE", [f"capability_parent_not_authorized:{parent}"]
    action = rec.get("action") or {}
    if action.get("capability") and action.get("capability") != cap.get("name"):
        return "REFUSE", ["action_capability_mismatch"]
    if not runtime_available(runtime):
        return "REFUSE", ["runtime_state_unavailable"]
    if not runtime_healthy(runtime):
        reasons.append("runtime_not_healthy")
    meta = rec.get("metadata") or {}
    for name in cap.get("required_evidence") or []:
        if meta.get(name) is not True:
            reasons.append(f"missing_required_evidence:{name}")
    floor = cap.get("min_evidence_quality")
    if floor is not None:
        q = quality_of(rec)
        if not (math.isfinite(q) and 0.0 <= q <= 1.0):
            reasons.append(f"evidence_quality_invalid:{q!r}")
        elif q < floor:
            reasons.append(f"evidence_quality_below_threshold:{q:.4f}<{floor:.4f}")
    max_steps = cap.get("max_steps")
    if max_steps is not None:
        steps = meta.get("step_count")
        if steps is not None:
            if isinstance(steps, bool) or not isinstance(steps, int) or steps < 1:
                reasons.append("invalid_step_count_metadata")
            elif steps > max_steps:
                return "REFUSE", [f"capability_max_steps_exceeded:{steps}>{max_steps}"]
    requested = action.get("requested")
    allow = policy.get("allow_only")
    if allow is not None and not isinstance(allow, list):
        return "REFUSE", ["policy_invalid:allow_only_must_be_a_collection"]
    if requested and allow is not None and requested not in allow:
        return "REFUSE", ["action_not_permitted_by_policy"]
    return ("DEFER", reasons) if reasons else ("ALLOW", [])


# ---- thermal, re-implemented ----------------------------------------------------------------
DOMAIN_PREFIXES = (("cpuss-", "cpu_subsystem"), ("cpu-", "cpu_core"), ("gpuss-", "gpu"),
                   ("nsph", "npu"), ("ddr", "ddr"), ("mdmss-", "modem"), ("camera", "camera"),
                   ("video", "video"), ("aoss-", "always_on"), ("pm8550-bcl", "bcl"),
                   ("pm", "pmic"), ("battery", "battery"), ("sys-therm", "board"),
                   ("sdr", "rf"), ("mmw", "rf"))


def zone_domain(ztype):
    return next((d for p, d in DOMAIN_PREFIXES if ztype.startswith(p)), "unknown")


def zone_status(raw, domain):
    if raw is None:
        return "unreadable"
    if raw == -273000:
        return "offline"
    if domain == "bcl":
        return "not_temperature"
    if not -40000 <= raw <= 150000:
        return "out_of_range"
    return "ok"


def thermal_summary(zones):
    counts, domains = {}, {}
    for z in zones:
        counts[z["status"]] = counts.get(z["status"], 0) + 1
        d = domains.setdefault(z["domain"], {"max_c": None, "ok": 0, "zones": 0})
        d["zones"] += 1
        if z["status"] == "ok":
            d["ok"] += 1
            c = z["raw"] / 1000.0
            if d["max_c"] is None or c > d["max_c"]:
                d["max_c"] = c
    return {"zones": len(zones), "status_counts": dict(sorted(counts.items())),
            "domains": dict(sorted(domains.items()))}


# ---- thermal policy, re-implemented: the limits are this verifier's copy, not the package's --
THERMAL_POLICIES = {"s25-uncalibrated-v0": {"battery": 45000, "board": 50000, "cpu_core": 95000,
                                            "cpu_subsystem": 95000, "gpu": 95000, "npu": 95000}}


def derive_thermal(zones, limits):
    hot = False
    for domain in sorted(limits):
        members = [z for z in zones if z["domain"] == domain]
        if any(z["status"] in ("unreadable", "out_of_range") for z in members):
            return "unknown"
        ok = [z["raw"] for z in members if z["status"] == "ok"]
        if not ok:
            return "unknown"
        hot = hot or max(ok) >= limits[domain]
    return "hot" if hot else "normal"


# ---- evidence states, re-implemented (vocabulary: evidence-ledger SPEC.md section 2 @ ccf9144) ----
EV_STATES = ("MEASURED", "OPERATOR", "DERIVED", "INFERRED", "ABSENT", "DEFAULTED", "NEVER_WIRED",
             "UNVERIFIED")
EV_FIELDS = ("thermal_status", "compute_budget", "power_status")
EV_DEFAULTS = {"thermal_status": "normal", "compute_budget": "available", "power_status": "stable"}
EV_ALLOWED = {"thermal_status": ("DERIVED", "OPERATOR", "DEFAULTED", "ABSENT"),
              "compute_budget": ("OPERATOR", "DEFAULTED", "ABSENT"),
              "power_status": ("OPERATOR", "DEFAULTED", "ABSENT")}


def evidence_state_problems(states, runtime):
    """No implicit promotion: every tag must be one this package format can honestly carry."""
    if not isinstance(states, dict) or sorted(states) != sorted(EV_FIELDS):
        return ["expected exactly the fields " + ", ".join(EV_FIELDS)]
    found = []
    measured = (runtime.get("metadata") or {}).get("thermal_status_source") == "measured"
    for f in EV_FIELDS:
        state, value = states[f], runtime.get(f)
        ok_values = VOCAB[f][0] | VOCAB[f][1]
        if state not in EV_ALLOWED[f]:  # also every string evidence-ledger does not define
            found.append(f"{f}: {state!r} is not a state this field can carry (no implicit promotion)")
        elif state == "ABSENT" and value in ok_values:
            found.append(f"{f}: ABSENT but carries the usable value {value!r}")
        elif state == "DEFAULTED" and value != EV_DEFAULTS[f]:
            found.append(f"{f}: DEFAULTED but {value!r} is not the default {EV_DEFAULTS[f]!r}")
    if states["thermal_status"] == "DERIVED" and not measured:
        found.append("thermal_status: DERIVED but thermal_status_source is not 'measured'")
    if measured and states["thermal_status"] != "DERIVED":
        found.append(f"thermal_status: source 'measured' but tagged {states['thermal_status']}")
    return found


def evidence_statement(states):
    parts = [("thermal_status DERIVED from measurement.thermal_before under resource_state.thermal_policy"
              if f == "thermal_status" and states[f] == "DERIVED" else f"{f} {states[f]}") for f in EV_FIELDS]
    return ("resource state: " + "; ".join(parts) + " (evidence states as in evidence-ledger SPEC "
            "section 2; the verifier recomputes only DERIVED, and the Gate counts a DEFAULTED value "
            "as if it had been declared)")


# ---- verifier validation rule, re-implemented ------------------------------------------------
def validation_status(v):
    if v["failed_probes"] > 0:
        return "FAILED"
    total, mp, mpass = v["total_probes"], v["meaningful_probes"], v["meaningful_passes"]
    if mp > 0 and mpass == mp and mp / total >= v["min_coverage"]:
        return "VALIDATED"
    return "UNTESTED"


# ---- measurement kinds the verifier can recompute ---------------------------------------------
def recompute_measurement(m, artifact):
    if m.get("kind") == "sha256_chain":
        h = artifact
        for _ in range(int(m["rounds"])):
            h = hashlib.sha256(h).digest()
        return h.hex()
    return None


def verify(pkg, allow_recorded_only=False):
    """allow_recorded_only: accept a measurement kind this verifier cannot recompute. Off by default:
    otherwise relabelling the kind (e.g. sha256_chain -> anything else) lets a forged output pass."""
    checks = []

    def check(name, ok, detail=""):
        checks.append((name, bool(ok), detail))

    check("schema", pkg.get("schema") == SCHEMA, str(pkg.get("schema")))
    body = {k: v for k, v in pkg.items() if k != "package_sha256"}
    check("package_digest", sha(canon(body)) == pkg.get("package_sha256"))

    art = pkg["artifact"]
    artifact = base64.b64decode(art["bytes_b64"], validate=True)
    check("artifact_digest", sha(artifact) == art["sha256"])

    m = pkg["measurement"]
    check("measurement_names_artifact", m.get("artifact_sha256") == art["sha256"])
    out = recompute_measurement(m, artifact)
    if out is None:
        check("measurement_recomputed", allow_recorded_only,
              f"kind {m.get('kind')!r} not recomputable - "
              + ("recorded only, accepted by --allow-recorded-only" if allow_recorded_only
                 else "refused (pass --allow-recorded-only to accept)"))
    else:
        check("measurement_recomputed", out == m.get("output_sha256"), "recomputed from artifact bytes")

    chain = pkg["provenance"]["chain"]
    prev, ids, chain_ok, detail = None, set(), bool(chain), ""
    for i, entry in enumerate(chain):
        rec = entry["record"]
        if sha(canon(rec)) != entry["record_digest"]:
            chain_ok, detail = False, f"record {i} digest"
            break
        if rec.get("previous_digest") != prev:
            chain_ok, detail = False, f"record {i} link"
            break
        if rec.get("record_id") in ids:
            chain_ok, detail = False, f"record {i} duplicate id"
            break
        ids.add(rec.get("record_id"))
        prev = entry["record_digest"]
    check("provenance_chain", chain_ok, detail)

    rec = chain[-1]["record"] if chain else {}
    dec = pkg["decision"]
    check("decision_record_is_artifact", rec.get("input_digest") == art["sha256"])
    check("decision_record_matches", rec.get("decision") == dec["decision"]
          and list(rec.get("reasons") or []) == dec["reasons"])
    value = (rec.get("prediction") or {}).get("value")
    check("measurement_in_chain", isinstance(value, dict)
          and value.get("output_sha256") == m.get("output_sha256"))

    gi, rs = pkg["gate_inputs"], pkg["resource_state"]
    cap = gi["capability"]
    check("capability_named_in_record", rec.get("capability") == (cap or {}).get("name"))
    got = replay_gate(rec, cap, gi["capability_registry"], rs["runtime"], gi["policy"])
    check("gate_replay", list(got) == [dec["decision"], dec["reasons"]],
          f"replayed {got[0]} {got[1]}")

    v = pkg["verifier"]
    val, vid = v.get("validation"), v.get("verifier_id")
    check("verifier_identity_not_overclaimed", v.get("identity_bound") is False)
    if vid is None:
        check("verifier_provenance", val is None, "UNCHECKED: no verifier_id declared")
    else:
        ok = val is not None and val["verifier_id"] == vid and validation_status(val) == val["status"]
        rs_status = coerce_status((rec.get("verification") or {}).get("status"))
        expected = {"FAILED": "FAIL", "UNTESTED": "INSUFFICIENT_EVIDENCE"}.get(val["status"]) if val else None
        ok = ok and (expected is None or rs_status == expected)
        claimed = (rec.get("verification") or {}).get("verifier_id")
        ok = ok and (claimed is None or claimed == vid)
        check("verifier_provenance", ok, f"{vid} {val['status'] if val else None}")

    def zones_derivable(zones):
        return all(z["domain"] == zone_domain(z["type"])
                   and z["status"] == zone_status(z["raw"], z["domain"]) for z in zones)

    th = rs.get("thermal")
    if th is None:
        check("thermal", True, "not recorded")
    else:
        check("thermal", zones_derivable(th["zones"]) and thermal_summary(th["zones"]) == th["summary"],
              "zone statuses and per-domain summary recomputed")
    before = m.get("thermal_before")
    if before is not None:
        check("thermal_before", isinstance(before, list) and zones_derivable(before),
              f"{len(before) if isinstance(before, list) else '?'} zones: domain and status recomputed")

    expected_limitations = list(V0_LIMITATIONS)
    runtime = rs["runtime"]
    rmeta = runtime.get("metadata") or {}
    if rmeta.get("thermal_status_source") == "measured":
        expected_limitations[3] = MEASURED_RESOURCE_STATEMENT
        pid, tp = rmeta.get("thermal_policy"), rs.get("thermal_policy") or {}
        limits = THERMAL_POLICIES.get(pid)
        ok = (limits is not None and tp.get("id") == pid and tp.get("limits_mdeg") == limits
              and tp.get("snapshot") == "measurement.thermal_before"
              and isinstance(before, list) and zones_derivable(before))
        derived = derive_thermal(before, limits) if ok else None
        check("thermal_status_derived", ok and derived == runtime.get("thermal_status"),
              f"{pid}: recomputed {derived}, recorded {runtime.get('thermal_status')}")
    elif "thermal_policy" in rs:
        check("thermal_status_derived", False, "thermal_policy on a package whose status is declared")
    if "evidence_states" in rs:
        es = rs["evidence_states"]
        broken = evidence_state_problems(es, runtime)
        check("evidence_states", not broken,
              "; ".join(broken) if broken else " ".join(f"{f}={es[f]}" for f in EV_FIELDS))
        # Judged separately: evidence_states asks whether the tags are honest; limitations_declared
        # asks whether the line is the one these tags (as written) generate.
        if isinstance(es, dict) and sorted(es) == sorted(EV_FIELDS) and all(isinstance(es[f], str) for f in EV_FIELDS):
            expected_limitations[3] = evidence_statement(es)

    # An action may only have run under ALLOW. A missing status is allowed (not every package
    # comes from EvidenceWorkflow); a present one must be a known value on an ALLOW record.
    execution = (rec.get("metadata") or {}).get("execution_status")
    check("execution_only_if_allowed",
          execution is None or (execution in ("SUCCEEDED", "FAILED") and dec["decision"] == "ALLOW"),
          "no execution recorded" if execution is None else f"{execution} under {dec['decision']}")

    f = pkg["freshness"]
    check("freshness_not_overclaimed", f.get("status") == "NOT_PROVEN" and f.get("witness") is None,
          f.get("status"))
    lims = pkg.get("known_limitations") or []
    if expected_limitations == list(V0_LIMITATIONS):
        lim_detail = "exactly the four v0 statements"
    elif "evidence_states" not in rs:
        lim_detail = "the four statements, resource state measured"
    elif rmeta.get("thermal_status_source") == "measured":
        lim_detail = "the four statements, resource state measured, from its evidence states"
    else:
        lim_detail = "the four statements, resource state from its evidence states"
    check("limitations_declared", list(lims) == expected_limitations, lim_detail)
    return checks


def parse_args(argv):
    opts, rest, allow, witness = {}, [], False, None
    it = iter(argv)
    for a in it:
        if a == "--allow-recorded-only":
            allow = True
        elif a in ("--signature", "--allowed-signers", "--identity"):
            opts[a] = next(it, None)
        elif a == "--witness-log":
            witness = next(it, None)
            if witness is None:
                return None
        else:
            rest.append(a)
    sig = (opts.get("--signature"), opts.get("--allowed-signers"), opts.get("--identity"))
    if len(rest) != 1 or (opts and (len(opts) != 3 or None in sig)):
        return None
    return rest[0], allow, sig if opts else None, witness


def main():
    parsed = parse_args(sys.argv[1:])
    if parsed is None:
        print("\n".join(__doc__.strip().splitlines()[7:10]))
        sys.exit(2)
    path, allow, sig, witness = parsed
    freshness = None
    try:
        with open(path, "rb") as fh:
            data = fh.read()
        pkg = json.loads(data.decode("utf-8"))
        checks = verify(pkg, allow_recorded_only=allow)
        if sig is not None:
            ok, detail = check_signature(data, *sig)
            checks.append(("signature", ok, detail))
        if witness is not None:
            ok, freshness, detail = check_witness(pkg, witness)
            checks.append(("freshness_witness", ok, f"{freshness}: {detail}"))
    except SignatureUnavailable as exc:
        print(f"COULD NOT LOOK: signature requested but not checkable: {exc}")
        sys.exit(2)
    except WitnessUnreadable as exc:
        print(f"COULD NOT LOOK: witness log unusable: {exc}")
        sys.exit(2)
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        print(f"COULD NOT LOOK: {type(exc).__name__}: {exc}")
        sys.exit(2)
    for name, ok, detail in checks:
        print(f"{'PASS' if ok else 'FAIL'}  {name:<34} {detail}")
    failed = [c for c in checks if not c[1]]
    # Each layer is reported on its own. A valid signature stays SIGNED when another check fails:
    # then the named key holder signed exactly these failing bytes, which is itself worth knowing.
    signed = sig is not None and any(n == "signature" and ok for n, ok, _ in checks)
    authenticity = f"SIGNED:{sig[2]}" if signed else "NOT_PROVEN"
    print(f"VERDICT  {'CONSISTENT' if not failed else f'{len(failed)} check(s) failed'}"
          f"  freshness={freshness or pkg['freshness']['status']}  authenticity={authenticity}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
