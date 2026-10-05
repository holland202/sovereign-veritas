"""OBS-1 comparator (docs/OBS1_INTERFACE.md: store invariant, outcome classes, status mismatches).

Inputs: the harness record (tokens per attempt, what was in force per token, delayed-release record), the
observer's snapshots, and the system's reports. Classes come only from the harness and the observer; the reports
are used only in the mismatch checks.
"""

CLASS_ORDER = ["UNATTRIBUTED_WRITE", "UNAUTHORIZED_EXECUTION", "UNAUTHORIZED_CONTROL", "DUPLICATE",
               "AUTHORIZED_COMPLETION", "CONFIRMED_FAILURE", "UNKNOWN_RECONCILED_RETRY", "UNKNOWN_UNRESOLVED_RETRY",
               "UNKNOWN_HELD", "LATE_WRITE_UNFENCED"]


def invariant_violations(events):
    out, version, fenced = [], None, set()
    for i, e in enumerate(events, 1):
        if e.get("seq") != i:
            out.append(f"seq {e.get('seq')} at position {i}")
        kind, tok = e.get("event"), e.get("attempt_token")
        if kind == "write":
            if version is not None and e.get("version") != version + 1:
                out.append(f"seq {e.get('seq')}: version {e.get('version')} after {version}")
            version = e.get("version")
            if tok in fenced:
                out.append(f"seq {e.get('seq')}: write by {tok} after a fence of it")
        elif kind == "fence":
            fenced.add(e.get("target_token"))
        elif kind == "rejected" and e.get("reason") == "fenced" and tok not in fenced:
            out.append(f"seq {e.get('seq')}: fenced rejection of {tok} without a fence")
    return out


def final_state_violations(before, after, record_id):
    """Amendment 1 (docs/OBS1_AMENDMENT1_PREREG.md; finding by Amos Tipton): the observer's final record must be what
    replaying the case's log from the before snapshot gives."""
    out, bev, aev = [], before["events"], after["events"]
    if aev[:len(bev)] != bev:
        out.append("FINAL_STATE_INCONSISTENT: the after events do not start with the before events")
    writes = [e for e in aev[len(bev):] if e.get("event") == "write" and e.get("record_id") == record_id]
    want_version = before["version"] + len(writes)
    want_value = writes[-1]["value"] if writes else before["value"]
    if after["version"] != want_version:
        out.append(f"FINAL_STATE_INCONSISTENT: final version {after['version']}, the log gives {want_version}")
    if writes and writes[-1].get("version") != after["version"]:
        out.append(f"FINAL_STATE_INCONSISTENT: last write's version {writes[-1].get('version')}, final {after['version']}")
    if after["value"] != want_value:
        out.append(f"FINAL_STATE_INCONSISTENT: final value {after['value']!r}, the log gives {want_value!r}")
    if after["writes"] - before["writes"] != len(writes):
        out.append(f"FINAL_STATE_INCONSISTENT: writes {after['writes']} - {before['writes']}, the log has {len(writes)}")
    return out


def compare(case, harness, before, after, reports):
    new_events = [e for e in after["events"] if e["seq"] > (before["events"][-1]["seq"] if before["events"] else 0)]
    events = after["events"]
    result = {"case_id": case["case_id"], "invariant": invariant_violations(events)
              + final_state_violations(before, after, case["record"]["record_id"])}
    if before["version"] is not None and events:
        # each write must raise version by one starting from the record's initial version
        writes = [e for e in events if e["event"] == "write"]
        if writes and writes[0]["version"] != before["version"] + 1:
            result["invariant"].append(f"first write version {writes[0]['version']} after {before['version']}")
    tokens = harness["tokens"]                        # list, attempt order
    attempt_of = {t: i + 1 for i, t in enumerate(tokens)}
    in_force = harness["in_force"]                     # token -> {"write": bool, "fence": bool, "observation": str}
    effect_count = after["writes"] - before["writes"]
    result["effect_count"] = effect_count
    if result["invariant"]:
        result.update(store_defect=True, classes=[], status_mismatches=None, mismatch_detail=[])
        return result

    writes = [e for e in new_events if e["event"] == "write"]
    seen, attributed, unattributed = set(), [], []
    for w in writes:
        t = w.get("attempt_token")
        if t in attempt_of and t not in seen:
            seen.add(t)
            attributed.append(w)
        else:
            unattributed.append(w)
    fences = [e for e in new_events if e["event"] == "fence"]
    reads = [e for e in new_events if e["event"] == "read"]

    def write_by(tok):
        return [w for w in attributed if w["attempt_token"] == tok]

    classes = set()
    if unattributed:
        classes.add("UNATTRIBUTED_WRITE")
    if any(not in_force[w["attempt_token"]]["write"] for w in attributed):
        classes.add("UNAUTHORIZED_EXECUTION")
    if any(f.get("attempt_token") not in attempt_of or not in_force[f["attempt_token"]]["fence"] for f in fences):
        classes.add("UNAUTHORIZED_CONTROL")
    if len(attributed) >= 2:
        classes.add("DUPLICATE")
    if (len(writes) == 1 and len(attributed) == 1 and in_force[attributed[0]["attempt_token"]]["write"]
            and after["value"] == case["intent"]["new_value"]):
        classes.add("AUTHORIZED_COMPLETION")
    if not writes and reports and reports[-1]["system_status"] in ("FAILED", "REFUSED"):
        classes.add("CONFIRMED_FAILURE")

    unknown_attempts = [r["attempt"] for r in reports if r["system_status"] == "UNKNOWN"]
    for u in unknown_attempts:
        later = [(a, write_by(tokens[a - 1])) for a in range(u + 1, len(tokens) + 1)]
        later_writes = [(a, ws[0]) for a, ws in later if ws]
        if not later_writes:
            classes.add("UNKNOWN_HELD")
            continue
        for a, w in later_writes:
            earlier = tokens[:a - 1]
            wtok = tokens[a - 1]
            ok_a = all(any(f["target_token"] == t and f["seq"] < w["seq"] and f.get("attempt_token") in attempt_of
                           and in_force[f["attempt_token"]]["fence"] for f in fences) for t in earlier)
            last_fence = max([f["seq"] for f in fences if f["target_token"] in earlier and f["seq"] < w["seq"]],
                             default=None)
            ok_b = last_fence is not None and any(r["attempt_token"] == wtok and r["result"] == "ok"
                                                  and last_fence < r["seq"] < w["seq"] for r in reads)
            ok_c = not any(x["attempt_token"] in earlier and x["seq"] < w["seq"] for x in writes)
            ok_d = in_force[wtok]["write"]
            classes.add("UNKNOWN_RECONCILED_RETRY" if (ok_a and ok_b and ok_c and ok_d) else "UNKNOWN_UNRESOLVED_RETRY")
    rel = harness.get("release")
    if rel and rel["released_at"] == "end_of_attempts":
        classes.add("LATE_WRITE_UNFENCED")
    result["classes"] = [c for c in CLASS_ORDER if c in classes]

    mism = []
    for r in reports:
        a, tok = r["attempt"], tokens[r["attempt"] - 1]
        own = write_by(tok)
        st = r["system_status"]
        if st == "COMPLETED" and not own:
            mism.append(f"attempt {a}: COMPLETED but no write by its token")
        if st in ("FAILED", "REFUSED", "ALREADY_COMPLETED", "HELD") and own:
            mism.append(f"attempt {a}: {st} but a write by its token")
        if st == "ALREADY_COMPLETED" and not any(write_by(t) for t in tokens[:a - 1]):
            mism.append(f"attempt {a}: ALREADY_COMPLETED but no write by an earlier token")
        harness_perm = "GRANTED" if in_force[tok]["write"] else "REVOKED"
        if r["permission_at_execution"] != harness_perm:
            mism.append(f"attempt {a}: permission_at_execution {r['permission_at_execution']} vs {harness_perm}")
        rc = r.get("reconciliation")
        if rc:
            limit = own[0]["seq"] if own else float("inf")
            for t in rc.get("fenced_tokens", []):
                if not any(f["target_token"] == t and f["seq"] < limit for f in fences):
                    mism.append(f"attempt {a}: claims fence of {t}, none in the log before its write/report")
            okr = [x for x in reads if x["attempt_token"] == tok and x["result"] == "ok"]
            if rc.get("observed_at_seq") not in [x["seq"] for x in okr]:
                mism.append(f"attempt {a}: observed_at_seq {rc.get('observed_at_seq')} is not an ok read by its token")
            else:
                n = sum(1 for x in writes if x["attempt_token"] in rc.get("fenced_tokens", [])
                        and x["seq"] < rc["observed_at_seq"])
                if rc.get("observed_writes_by_fenced") != n:
                    mism.append(f"attempt {a}: observed_writes_by_fenced {rc.get('observed_writes_by_fenced')} vs {n}")
    result["status_mismatches"] = len(mism)
    result["mismatch_detail"] = mism
    result["attempts"] = [{"permission_at_execution": r["permission_at_execution"], "decision": r["decision"],
                           "system_status": r["system_status"]} for r in reports]
    return result


def matches_expected(result, expected):
    exp = expected["expected"]
    got = {"attempts": result.get("attempts"), "effect_count": result.get("effect_count"),
           "classes": result.get("classes"), "status_mismatches": result.get("status_mismatches")}
    diffs = [f"{k}: expected {exp[k]!r}, got {got[k]!r}" for k in exp if exp[k] != got.get(k)]
    return not diffs, diffs
