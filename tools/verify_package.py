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
from pathlib import Path

NAMESPACE = "sv-package"


class SignatureUnavailable(Exception):
    """ssh-keygen missing or unusable: the signature could not be checked at all."""


WITNESS_HEADER = "# sv witness log v0"


class WitnessUnreadable(Exception):
    """The witness log is missing or malformed: freshness could not be judged at all."""


# Nesting limit for every JSON document the verifier parses. Before 2026-10-02 the limit was whatever
# the platform's C stack allowed: on macOS + Python 3.14 a 100000-deep value parsed and the verdict was
# "checks failed" (exit 1), elsewhere RecursionError gave COULD NOT LOOK (exit 2). Same bytes, two
# verdicts. The limit is now part of the verifier, not of the platform. Genuine packages nest to depth 7.
MAX_JSON_DEPTH = 64


def json_depth(text):
    """Deepest [ / { nesting in a JSON text, ignoring brackets inside strings. Iterative: no recursion."""
    depth = deepest = 0
    in_str = esc = False
    for ch in text:
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch in "[{":
            depth += 1
            if depth > deepest:
                deepest = depth
        elif ch in "]}":
            depth -= 1
    return deepest


def _no_duplicate_keys(pairs):
    # DK (docs/DK_PREREG.md): json.loads keeps the LAST of two equal keys and the digests are computed over the
    # parsed object, so a planted first value was invisible here while a first-wins parser elsewhere would read it.
    obj = {}
    for k, v in pairs:
        if k in obj:
            raise ValueError(f"duplicate JSON key {k!r}")
        obj[k] = v
    return obj


def _no_nonfinite(name):
    raise ValueError(f"non-standard JSON literal {name} (NaN and Infinity are not JSON)")


def loads_bounded(text):
    """Strict json.loads: nesting limit, no duplicate keys, no NaN/Infinity. Each raises ValueError."""
    d = json_depth(text)
    if d > MAX_JSON_DEPTH:
        raise ValueError(f"JSON nesting depth {d} exceeds the verifier limit {MAX_JSON_DEPTH}")
    return json.loads(text, object_pairs_hook=_no_duplicate_keys, parse_constant=_no_nonfinite)


def read_witness_log(path):
    """Read a canonical witness log.

    Entry lines must be exactly ``<seq> <sha256>`` with a single space, no
    leading zeros, no tabs, no trailing spaces, no blank lines. Line endings
    may be LF or CRLF (Windows writers use text mode); the security invariant
    is the entry body, not the platform line terminator.
    """
    try:
        data = Path(path).read_bytes()
    except OSError as exc:
        raise WitnessUnreadable(str(exc))

    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise WitnessUnreadable(f"witness log is not valid UTF-8: {exc}")

    if not text.startswith(WITNESS_HEADER):
        raise WitnessUnreadable(f"first line must be {WITNESS_HEADER!r}")

    # Accept LF or CRLF after the header; reject other first-line garbage.
    rest = text[len(WITNESS_HEADER):]
    if rest.startswith("\r\n"):
        rest = rest[2:]
    elif rest.startswith("\n"):
        rest = rest[1:]
    else:
        raise WitnessUnreadable(f"first line must be {WITNESS_HEADER!r}")

    entries, seen = [], set()
    # Split on LF; strip a trailing CR so CRLF bodies normalize.
    raw_lines = rest.split("\n")
    # A final empty segment means the file ended with a newline (required for
    # every complete entry). An empty rest is a header-only log (zero entries).
    if raw_lines and raw_lines[-1] == "":
        raw_lines = raw_lines[:-1]
    elif rest != "":
        raise WitnessUnreadable("witness log must end with a newline")

    for n, line in enumerate(raw_lines, start=2):
        if line.endswith("\r"):
            line = line[:-1]
        if "\r" in line:
            raise WitnessUnreadable(f"line {n}: carriage return is not canonical")
        if line == "":
            raise WitnessUnreadable(f"line {n}: blank entries are not canonical")
        if "\t" in line:
            raise WitnessUnreadable(f"line {n}: tabs are not canonical")

        parts = line.split(" ")
        if len(parts) != 2 or not parts[0].isdigit() or parts[0] == "0":
            raise WitnessUnreadable(f"line {n}: expected canonical '<seq> <sha256>'")

        seq_text, digest = parts
        if seq_text != str(len(entries) + 1):
            raise WitnessUnreadable(
                f"line {n}: seq {seq_text}, expected {len(entries) + 1}"
            )
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise WitnessUnreadable(f"line {n}: not a lowercase sha256")
        if digest in seen:
            raise WitnessUnreadable(f"line {n}: digest already logged")

        seen.add(digest)
        entries.append((int(seq_text), digest))

    return entries


def check_witness_entries(pkg, entries):
    """(ok, status, detail) using an already-read witness snapshot."""
    digest = pkg.get("package_sha256")
    seqs = [s for s, d in entries if d == digest]

    if not seqs:
        return False, "NOT_WITNESSED", f"not among {len(entries)} witnessed packages"

    later = len(entries) - seqs[0]
    if later:
        return False, "STALE", (
            f"entry {seqs[0]} of {len(entries)}: "
            f"{later} newer package(s) witnessed"
        )

    return True, f"LATEST_WITNESSED({seqs[0]})", (
        f"entry {seqs[0]} of {len(entries)}, the last"
    )


def check_witness(pkg, log_path):
    """(ok, status, detail). ok only when the package is the last witnessed entry."""
    return check_witness_entries(pkg, read_witness_log(log_path))


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


# sv.package/0 is closed: a key the verifier does not know is refused, not ignored. Found by
# tools/nvidia_challenge.py (2026-09-26): an added top-level field ("fake_field") verified CONSISTENT,
# so unchecked text could ride inside a package that passes.
PACKAGE_KEYS = frozenset({"artifact", "decision", "freshness", "gate_inputs", "known_limitations", "measurement",
                          "package_sha256", "provenance", "resource_state", "schema", "verifier"})
RECORD_KEYS = frozenset({"action", "capability", "decision", "evidence_quality", "input_digest", "metadata",
                         "prediction", "previous_digest", "reasons", "record_id", "timestamp", "uncertainty",
                         "verification"})


# Nested objects, closed the same way (2026-09-26, after nvidia_challenge round 3 added
# gate_inputs.capability.description, a key that exists, so it was not caught by name; see below).
# Deliberately left open, because their content is checked or bound elsewhere, or is free-form by
# contract: record metadata, action parameters (bound by model_check_bound / vehicle_check_bound),
# the thermal summary (recomputed and compared whole), and the check objects (compared whole with
# their recomputation).
CAPABILITY_KEYS = frozenset({"authorized", "description", "max_steps", "min_evidence_quality", "name", "parent",
                             "required_evidence"})
CLOSED = {
    "artifact": {"bytes_b64", "name", "sha256"},
    "decision": {"decision", "reasons"},
    "freshness": {"status", "witness"},
    "gate_inputs": {"capability", "capability_registry", "policy"},
    "gate_inputs.policy": {"allow_only"},
    "resource_state": {"evidence_states", "runtime", "thermal", "thermal_policy"},
    "resource_state.runtime": {"compute_budget", "metadata", "platform", "power_status", "python_version",
                               "thermal_status"},
    "resource_state.runtime.metadata": {"thermal_policy", "thermal_status_source"},
    "resource_state.thermal": {"summary", "zones"},
    "resource_state.thermal_policy": {"id", "limits_mdeg", "snapshot"},
    "verifier": {"identity_bound", "validation", "verifier_id"},
    "verifier.validation": {"failed_probes", "meaningful_passes", "meaningful_probes", "min_coverage", "status",
                            "total_probes", "verifier_id"},
}
ZONE_KEYS = frozenset({"zone", "type", "domain", "raw", "status"})
SNAPSHOT_KEYS = frozenset({"armed", "battery_pct", "ekf_flags", "gps_fix_type", "gps_sats", "lat_e7", "lon_e7",
                           "mode", "rel_alt_mm", "xpos_lat_e7", "xpos_lon_e7", "xpos_source"})
MEASUREMENT_KEYS = {
    "sha256_chain": {"artifact_sha256", "elapsed_ms", "kind", "output_sha256", "preload_seconds", "rounds",
                     "thermal_before"},
    "model_answer_check": {"artifact_sha256", "backend", "check", "elapsed_ms", "kind", "model_file", "model_id",
                           "note_sha256", "output_sha256", "params", "preload_seconds", "raw_output",
                           "thermal_before"},
    "companion_route_check": {"artifact_sha256", "check", "kind", "output_sha256", "released_sha256"},
    "vehicle_command_check": {"artifact_sha256", "backend", "check", "commands_sent", "kind", "outcome",
                              "output_sha256", "telemetry_after", "telemetry_before", "thermal_before", "vehicle"},
}
MODEL_PARAMS = frozenset({"temperature", "seed", "max_tokens", "cache_prompt", "scripted", "server_devices"})


def unknown_nested_keys(pkg):
    """Every key in a closed nested object that sv.package/0 does not define, as 'path.key'."""
    found = []

    def closed(obj, allowed, path):
        if isinstance(obj, dict):
            found.extend(f"{path}.{k}" for k in sorted(set(obj) - set(allowed)))

    for path, allowed in CLOSED.items():
        obj = pkg
        for part in path.split("."):
            obj = obj.get(part) if isinstance(obj, dict) else None
        closed(obj, allowed, path)
    gi = pkg.get("gate_inputs") if isinstance(pkg.get("gate_inputs"), dict) else {}
    closed(gi.get("capability"), CAPABILITY_KEYS, "gate_inputs.capability")
    if isinstance(gi.get("capability_registry"), dict):
        for name, cap in gi["capability_registry"].items():
            closed(cap, CAPABILITY_KEYS, f"gate_inputs.capability_registry.{name}")
    m = pkg.get("measurement") if isinstance(pkg.get("measurement"), dict) else {}
    if m.get("kind") in MEASUREMENT_KEYS:
        closed(m, MEASUREMENT_KEYS[m["kind"]], "measurement")
    closed(m.get("model_file"), {"claim", "name", "sha256", "size"}, "measurement.model_file")
    closed(m.get("params"), MODEL_PARAMS, "measurement.params")
    closed(m.get("outcome"), {"reached"}, "measurement.outcome")
    for snap in ("telemetry_before", "telemetry_after"):
        closed(m.get(snap), SNAPSHOT_KEYS, f"measurement.{snap}")
    th = (pkg.get("resource_state") or {}).get("thermal") if isinstance(pkg.get("resource_state"), dict) else None
    for where, zones in (("measurement.thermal_before", m.get("thermal_before")),
                         ("resource_state.thermal.zones", th.get("zones") if isinstance(th, dict) else None)):
        for i, z in enumerate(zones if isinstance(zones, list) else []):
            closed(z, ZONE_KEYS, f"{where}[{i}]")
    return found


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
def count(x):
    """A probe count: a plain int >= 0. bool, float, NaN and infinities are not counts."""
    return type(x) is int and x >= 0


def validation_status(v):
    # Found 2026-09-30 by a differential probe (tools/nonfinite_probe.py): failed_probes = NaN or -Infinity
    # made "failed_probes > 0" false and the package verified CONSISTENT, while a finite change failed. The
    # same class as issue #5. Malformed counts now recompute to MALFORMED, which never matches a recorded status.
    ok = all(count(v.get(k)) for k in ("failed_probes", "total_probes", "meaningful_probes", "meaningful_passes"))
    cov = v.get("min_coverage")
    # Range before isfinite: math.isfinite(10**400) raises OverflowError (found 2026-09-30, type-variant probe).
    # NaN fails "0 <= cov <= 1", so the range test alone also refuses NaN and both infinities.
    if not ok or isinstance(cov, bool) or not isinstance(cov, (int, float)) or not 0 <= cov <= 1 or v["meaningful_passes"] > v["meaningful_probes"] or v["meaningful_probes"] > v["total_probes"]:
        return "MALFORMED"
    if v["failed_probes"] > 0:
        return "FAILED"
    total, mp, mpass = v["total_probes"], v["meaningful_probes"], v["meaningful_passes"]
    if mp > 0 and mpass == mp and mp / total >= v["min_coverage"]:
        return "VALIDATED"
    return "UNTESTED"


# ---- measurement kinds the verifier can recompute ---------------------------------------------
# ---- a model's answer, re-checked (tools/model_action.py; docs/MODEL_ACTION.md) --------------------
MODEL_NOTE_MAX = 500


def first_json_object(raw):
    dec = json.JSONDecoder()
    for i, ch in enumerate(raw):
        if ch == "{":
            try:
                obj, _ = dec.raw_decode(raw, i)
            except ValueError:
                continue
            if isinstance(obj, dict):
                return obj
    return None


def model_check(task, raw):
    """The check, re-implemented: PASS only for an integer answer equal to the product, a string
    action and a string note of at most MODEL_NOTE_MAX characters."""
    expected = task["a"] * task["b"]
    obj, parsed = first_json_object(raw), None
    if obj is None:
        why = "no JSON object in the reply"
    else:
        ans, action, note = obj.get("answer"), obj.get("action"), obj.get("note")
        if isinstance(ans, bool) or not isinstance(ans, int):
            why = "answer is not an integer"
        elif not isinstance(action, str):
            why = "action is not a string"
        elif not isinstance(note, str) or len(note) > MODEL_NOTE_MAX:
            why = f"note is not a string of at most {MODEL_NOTE_MAX} characters"
        else:
            parsed = {"answer": ans, "action": action, "note": note}
            why = "answer correct" if ans == expected else f"answer {ans} is not {expected}"
    verdict = "PASS" if parsed is not None and parsed["answer"] == expected else "FAIL"
    return {"expected": expected, "parsed": parsed, "verdict": verdict, "why": why}


def recompute_model_answer(m, artifact):
    """The recorded output_sha256 if the task, the raw reply and the check all recompute; else why not."""
    try:
        task = loads_bounded(artifact.decode("utf-8"))["task"]
    except (ValueError, KeyError, TypeError):
        return "the artifact is not a model task"
    if not (isinstance(task, dict) and task.get("op") == "mul"
            and all(isinstance(task.get(k), int) and not isinstance(task.get(k), bool) for k in ("a", "b"))):
        return "the artifact's task is not a multiplication of two integers"
    raw = m.get("raw_output")
    if not isinstance(raw, str) or sha(raw) != m.get("output_sha256"):
        return "the raw reply does not hash to output_sha256"
    if model_check(task, raw) != m.get("check"):
        return "the recorded check does not recompute"
    return m.get("output_sha256")


# ---- a veritas-companion answer, re-checked (tools/companion_action.py; docs/COMPANION_ACTION.md) ---------
COMPANION_SCHEMA = "sv.companion_record/0"


def companion_check(rec):
    """The check, re-implemented: PASS only for an answer a deterministic tool produced (directly, or
    replayed from the cache with that origin); INSUFFICIENT_EVIDENCE for conflicts, escalations and
    anything the large model answered; FAIL for a record this check cannot read."""
    if not isinstance(rec, dict) or not all(isinstance(rec.get(k), str) for k in ("status", "delegated_to", "final_result")):
        return {"verdict": "FAIL", "why": "record lacks a string status, delegated_to or final_result"}
    st, to = rec["status"], rec["delegated_to"]
    if st == "SUPPORTED":
        if to == "deterministic":
            return {"verdict": "PASS", "why": "answered by a deterministic tool"}
        return {"verdict": "INSUFFICIENT_EVIDENCE", "why": f"SUPPORTED but delegated to {to!r}"}
    if st == "CACHED":
        origin = rec.get("cached_origin")
        if origin == "deterministic":
            return {"verdict": "PASS", "why": "cached answer of a deterministic tool"}
        return {"verdict": "INSUFFICIENT_EVIDENCE", "why": f"cached answer from {origin or 'an unrecorded tier'}"}
    if st == "UNCERTAIN":
        return {"verdict": "INSUFFICIENT_EVIDENCE", "why": "the tools found conflicting values"}
    if st == "ESCALATE":
        return {"verdict": "INSUFFICIENT_EVIDENCE", "why": f"outside the tools; answered by {to}"}
    return {"verdict": "FAIL", "why": f"unknown status {st!r}"}


def recompute_companion(m, artifact):
    """The recorded output_sha256 if the record and the check recompute; else why not."""
    try:
        doc = loads_bounded(artifact.decode("utf-8"))
        ok = doc["schema"] == COMPANION_SCHEMA and isinstance(doc["record"], dict)
    except (ValueError, KeyError, TypeError):
        ok = False
    if not ok:
        return "the artifact is not a companion record"
    out = sha(canon(doc["record"]))
    if out != m.get("output_sha256"):
        return "the record does not hash to output_sha256"
    if companion_check(doc["record"]) != m.get("check"):
        return "the recorded check does not recompute"
    return out


# ---- a vehicle command, re-checked (tools/vehicle_action.py; docs/VEHICLE_ACTION.md) -----------------
VEHICLE_SCHEMA = "sv.vehicle_request/0"
VEHICLE_MOVEMENT = ("takeoff", "goto")
EKF_POS_HORIZ_ABS, EKF_GPS_GLITCH, EKF_UNINITIALIZED = 16, 32768, 1024


def distance_m(lat1_e7, lon1_e7, lat2_e7, lon2_e7):
    if not all(is_finite_number(v) for v in (lat1_e7, lon1_e7, lat2_e7, lon2_e7)):
        return float("nan")
    p1, p2 = math.radians(lat1_e7 / 1e7), math.radians(lat2_e7 / 1e7)
    dp, dl = p2 - p1, math.radians((lon2_e7 - lon1_e7) / 1e7)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371000.0 * math.asin(math.sqrt(a))


def is_finite_number(value):
    """True only for numeric values with a finite IEEE-754 representation."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:  # an int beyond float range (JSON allows 10**400) has no finite IEEE-754 form
        return False


def vehicle_check(req, snap):
    """The check, re-implemented: movement needs fence, ceiling, navigation and battery; rtl needs
    navigation; land and every other action need no vehicle-state rule."""
    action, p, fence, lim = req["action"], req.get("params") or {}, req["fence"], req["limits"]
    failures = []

    def nav():
        gps_fix = snap["gps_fix_type"]
        if not is_finite_number(gps_fix):
            failures.append(f"gps fix {gps_fix!r} is non-finite or non-numeric")
        elif gps_fix < lim["min_fix_type"]:
            failures.append(f"gps fix {gps_fix} < {lim['min_fix_type']}")

        gps_sats = snap["gps_sats"]
        if not is_finite_number(gps_sats):
            failures.append(f"satellites {gps_sats!r} is non-finite or non-numeric")
        elif gps_sats < lim["min_sats"]:
            failures.append(f"satellites {gps_sats} < {lim['min_sats']}")
        flags = snap["ekf_flags"]
        if flags & EKF_UNINITIALIZED or not flags & EKF_POS_HORIZ_ABS:
            failures.append(f"ekf has no absolute horizontal position (flags {flags})")
        if flags & EKF_GPS_GLITCH:
            failures.append(f"ekf reports a gps glitch (flags {flags})")
        if "max_nav_disagreement_m" in lim:
            if not all(isinstance(snap.get(k), int) for k in ("xpos_lat_e7", "xpos_lon_e7")):
                failures.append("no independent position to cross-check")
            else:
                gap = distance_m(snap["lat_e7"], snap["lon_e7"], snap["xpos_lat_e7"], snap["xpos_lon_e7"])
                if not math.isfinite(gap):
                    failures.append(f"navigation disagreement is non-finite ({gap!r})")
                elif gap > lim["max_nav_disagreement_m"]:
                    failures.append(f"autopilot and independent position disagree by {gap:.1f} m "
                                    f"> {lim['max_nav_disagreement_m']} m")

    if action in VEHICLE_MOVEMENT:
        alt = p.get("alt_m")
        if not is_finite_number(alt) or not 2 <= alt <= fence["max_alt_m"]:
            failures.append(f"altitude {alt!r} not within 2..{fence['max_alt_m']} m")

        here = distance_m(fence["lat_e7"], fence["lon_e7"], snap["lat_e7"], snap["lon_e7"])
        if not math.isfinite(here):
            failures.append(f"vehicle distance is non-finite ({here!r})")
        elif here > fence["radius_m"]:
            failures.append(f"vehicle {here:.1f} m from fence centre > {fence['radius_m']} m")
        if action == "goto":
            if not all(isinstance(p.get(k), int) and not isinstance(p.get(k), bool) for k in ("lat_e7", "lon_e7")):
                failures.append("goto target is not two integers (degrees * 1e7)")
            else:
                there = distance_m(fence["lat_e7"], fence["lon_e7"], p["lat_e7"], p["lon_e7"])
                if not math.isfinite(there):
                    failures.append(f"target distance is non-finite ({there!r})")
                elif there > fence["radius_m"]:
                    failures.append(f"target {there:.1f} m from fence centre > {fence['radius_m']} m")
        nav()
        batt = snap["battery_pct"]
        if not is_finite_number(batt):
            failures.append(f"battery {batt!r} is non-finite or non-numeric")
        elif batt < 0:
            failures.append("battery remaining unknown")
        elif batt < lim["min_battery_pct"]:
            failures.append(f"battery {batt} % < {lim['min_battery_pct']} %")
    elif action == "rtl":
        nav()
    verdict = "FAIL" if failures else "PASS"
    return {"verdict": verdict, "why": "; ".join(failures) or f"all {action} rules hold", "failures": failures}


def recompute_vehicle(m, artifact):
    """The recorded output_sha256 if the request, the snapshot and the check all recompute; else why not."""
    try:
        req = loads_bounded(artifact.decode("utf-8"))
        ok = req["schema"] == VEHICLE_SCHEMA and isinstance(req["action"], str)
    except (ValueError, KeyError, TypeError):
        ok = False
    if not ok:
        return "the artifact is not a vehicle request"
    snap = m.get("telemetry_before")
    if not isinstance(snap, dict) or sha(canon(snap)) != m.get("output_sha256"):
        return "the telemetry snapshot does not hash to output_sha256"
    try:
        chk = vehicle_check(req, snap)
    except (KeyError, TypeError, ValueError):
        return "the check cannot be run on the recorded request and snapshot"
    if chk != m.get("check"):
        return "the recorded check does not recompute"
    return m.get("output_sha256")


MAX_CHAIN_ROUNDS = 10_000_000  # make_package default is 200000


def recompute_measurement(m, artifact):
    if m.get("kind") == "sha256_chain":
        # rounds must be a plain int in range: Infinity crashed the verifier and 1e12 would loop for hours
        # (found 2026-09-30, tools/nonfinite_probe.py). An out-of-range value fails the check, it is not run.
        r = m.get("rounds")
        if type(r) is not int or not 1 <= r <= MAX_CHAIN_ROUNDS:
            return f"rounds {r!r} refused: need an int in 1..{MAX_CHAIN_ROUNDS}"
        h = artifact
        for _ in range(r):
            h = hashlib.sha256(h).digest()
        return h.hex()
    if m.get("kind") == "model_answer_check":
        return recompute_model_answer(m, artifact)
    if m.get("kind") == "vehicle_command_check":
        return recompute_vehicle(m, artifact)
    if m.get("kind") == "companion_route_check":
        return recompute_companion(m, artifact)
    return None


def verify(pkg, allow_recorded_only=False):
    """allow_recorded_only: accept a measurement kind this verifier cannot recompute. Off by default:
    otherwise relabelling the kind (e.g. sha256_chain -> anything else) lets a forged output pass."""
    checks = []

    def check(name, ok, detail=""):
        checks.append((name, bool(ok), detail))

    check("schema", pkg.get("schema") == SCHEMA, str(pkg.get("schema")))
    extra = sorted(set(pkg) - PACKAGE_KEYS)
    for i, entry in enumerate((pkg.get("provenance") or {}).get("chain") or []):
        extra += [f"chain[{i}].{k}" for k in sorted(set((entry.get("record") or {})) - RECORD_KEYS)]
        extra += [f"chain[{i}]:{k}" for k in sorted(set(entry) - {"record", "record_digest"})]
    extra += unknown_nested_keys(pkg)
    check("schema_closed", not extra, ("unknown keys: " + ", ".join(extra[:8]) + (" ..." if len(extra) > 8 else ""))
          if extra else "no unknown keys")
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
        check("measurement_recomputed", out == m.get("output_sha256"),
              "reply re-parsed, answer re-checked" if m.get("kind") == "model_answer_check" and out == m.get("output_sha256")
              else "snapshot re-hashed, vehicle check re-run" if m.get("kind") == "vehicle_command_check" and out == m.get("output_sha256")
              else "record re-hashed, route check re-run" if m.get("kind") == "companion_route_check" and out == m.get("output_sha256")
              else ("recomputed from artifact bytes" if out == m.get("output_sha256") else str(out)[:80]))

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
    # The capability the Gate decided on must be the one the package's own registry snapshot records under that name,
    # when the snapshot has it (docs/CUSTODY_RESULTS.md, R3: revoked in the snapshot, authorized in gate_inputs).
    creg = gi["capability_registry"]
    if isinstance(cap, dict) and isinstance(creg, dict) and cap.get("name") in creg:
        check("capability_matches_registry", creg[cap.get("name")] == cap,
              "gate_inputs.capability equals its registry snapshot entry")
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

    if m.get("kind") == "model_answer_check":
        chk = m.get("check") if isinstance(m.get("check"), dict) else {}
        parsed = chk.get("parsed") if isinstance(chk.get("parsed"), dict) else None
        act = rec.get("action") or {}
        ran = (rec.get("metadata") or {}).get("execution_status") == "SUCCEEDED"
        note = parsed.get("note") if parsed else None
        broken = []
        if (rec.get("verification") or {}).get("status") != chk.get("verdict"):
            broken.append("recorded verification is not the check's verdict")
        if act.get("requested") != (parsed.get("action") if parsed else ""):
            broken.append("requested action is not the one in the reply")
        if (act.get("parameters") or {}) != ({"note": note} if parsed else {}):
            broken.append("action parameters are not the reply's note")
        if m.get("note_sha256") != (sha(note) if ran and isinstance(note, str) else None):
            broken.append("note hash does not match what ran")
        check("model_check_bound", not broken, "; ".join(broken) or
              f"verdict {chk.get('verdict')}, asked for {act.get('requested')!r}, note {'written' if ran else 'not written'}")

    if m.get("kind") == "companion_route_check":
        try:
            crec = loads_bounded(artifact.decode("utf-8")).get("record")
        except (ValueError, AttributeError):
            crec = None
        crec = crec if isinstance(crec, dict) else {}
        chk = m.get("check") if isinstance(m.get("check"), dict) else {}
        act = rec.get("action") or {}
        ran = (rec.get("metadata") or {}).get("execution_status") == "SUCCEEDED"
        value = crec.get("final_result")
        broken = []
        if (rec.get("verification") or {}).get("status") != chk.get("verdict"):
            broken.append("recorded verification is not the check's verdict")
        if act.get("requested") != "use_answer" or (act.get("parameters") or {}) != {"value": value}:
            broken.append("the action is not use_answer with the record's final_result")
        if m.get("released_sha256") != (sha(value) if ran and isinstance(value, str) else None):
            broken.append("released hash does not match what ran")
        check("companion_check_bound", not broken, "; ".join(broken) or
              f"verdict {chk.get('verdict')}, answer {'released' if ran else 'not released'}")

    if m.get("kind") == "vehicle_command_check":
        try:
            req = loads_bounded(artifact.decode("utf-8"))
        except ValueError:
            req = {}
        chk = m.get("check") if isinstance(m.get("check"), dict) else {}
        act = rec.get("action") or {}
        status = (rec.get("metadata") or {}).get("execution_status")
        sent = m.get("commands_sent")
        broken = []
        if (rec.get("verification") or {}).get("status") != chk.get("verdict"):
            broken.append("recorded verification is not the check's verdict")
        if act.get("requested") != req.get("action") or (act.get("parameters") or {}) != (req.get("params") or {}):
            broken.append("requested action or parameters are not the request's")
        if not isinstance(sent, list):
            broken.append("commands_sent is not a list")
        elif sent and (dec["decision"] != "ALLOW" or status not in ("SUCCEEDED", "FAILED")):
            broken.append(f"{len(sent)} command(s) sent under {dec['decision']} with execution {status}")
        if (m.get("outcome") is not None) != (status == "SUCCEEDED"):
            broken.append("an outcome is recorded exactly when the action ran")
        check("vehicle_check_bound", not broken, "; ".join(broken) or
              f"verdict {chk.get('verdict')}, {act.get('requested')!r}, {len(sent or [])} command(s) sent")

    mf = m.get("model_file")
    if mf is not None and m.get("backend") == "llama-server":
        # The operator's file and the server's own name for its model must agree (docs/MODEL_ACTION.md,
        # S25 run 1: a stale server answered for a file that was never loaded).
        mid = m.get("model_id")
        served = mid.replace("\\", "/").rsplit("/", 1)[-1] if isinstance(mid, str) else None
        named = mf.get("name") if isinstance(mf, dict) else None
        check("model_file_named", served is not None and served == named,
              f"server reports {served!r}, operator's file {named!r}")

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
        pkg = loads_bounded(data.decode("utf-8"))
        if not isinstance(pkg, dict):
            raise ValueError(f"top level is {type(pkg).__name__}, not an object")
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
    # AttributeError: a list/str where an object is expected (e.g. provenance.chain = "x").
    # RecursionError: nesting deeper than the JSON decoder allows. Both were uncaught tracebacks (exit 1,
    # indistinguishable from "checks failed") until 2026-09-30; malformed input is COULD NOT LOOK (exit 2).
    except (OSError, ValueError, KeyError, TypeError, IndexError, AttributeError, RecursionError) as exc:
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
