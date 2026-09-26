#!/usr/bin/env python3
"""verify_package.py - challenge an sv.package/0 evidence package without the producer's code.

Stdlib only. Imports nothing from sovereign_veritas: digests, the Gate, runtime vocabulary,
thermal classification and verifier-validation rules are re-implemented here from the
documented contract. Same author as the producer, so this is N-version, not independent.

  python tools/verify_package.py PACKAGE.json [--allow-recorded-only]
      exit 0 all checks pass | 1 a check failed | 2 unreadable

A passing package is internally consistent and its decision is the one the documented Gate
produces from its recorded inputs. It is NOT proven authentic or fresh; see its known_limitations.
"""
import base64, hashlib, json, math, sys

SCHEMA = "sv.package/0"
# v0 packages carry exactly these four statements. Exact match: an appended line could contradict
# one ("authenticity: signed by hardware") while every required prefix is still present.
V0_LIMITATIONS = (
    "freshness: NOT_PROVEN - no external witness; an older valid package is indistinguishable",
    "authenticity: none - no signature; a fully consistent rewrite verifies",
    "verifier identity: the verifier_id is declared by the caller, not bound to the verifier object",
    "resource state: runtime fields are declared by the caller, not derived from thermal zones",
)


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


def quality_of(rec):
    if rec.get("evidence_quality") is not None:
        return float(rec["evidence_quality"])
    q = (rec.get("metadata") or {}).get("evidence_quality")
    if q is not None:
        try:
            return float(q)
        except (TypeError, ValueError):
            return 0.0
    return 0.0


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
    check("limitations_declared", list(lims) == list(V0_LIMITATIONS), "exactly the four v0 statements")
    return checks


def main():
    args = [a for a in sys.argv[1:] if a != "--allow-recorded-only"]
    allow = len(args) != len(sys.argv) - 1
    if len(args) != 1:
        print(__doc__.strip().splitlines()[2])
        sys.exit(2)
    try:
        with open(args[0], encoding="utf-8") as fh:
            pkg = json.load(fh)
        checks = verify(pkg, allow_recorded_only=allow)
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        print(f"COULD NOT LOOK: {type(exc).__name__}: {exc}")
        sys.exit(2)
    for name, ok, detail in checks:
        print(f"{'PASS' if ok else 'FAIL'}  {name:<34} {detail}")
    failed = [c for c in checks if not c[1]]
    print(f"VERDICT  {'CONSISTENT' if not failed else f'{len(failed)} check(s) failed'}"
          f"  freshness={pkg['freshness']['status']}  authenticity=NOT_PROVEN")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
