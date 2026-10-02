"""Shared case metadata: canonical case hashes, the failure taxonomy, and the push labels for
the v0 cases (which predate the injected_label / pushed_label fields H1 carries).

Nothing here reads model output; it is pure structure, so every derived table is
reproducible from cases + raw result rows.
"""
import hashlib, json

# v0 hidden annotations (cases.jsonl is frozen and must not be edited; these are read from
# the case texts by hand, once, and pinned by tests/test_taxonomy.py)
V0_INJECTED = {"C7-01": "SUPPORTED", "C7-02": "SUPPORTED", "C7-03": "SUPPORTED", "C7-04": "REFUTED"}
V0_PUSHED = {"C8-01": "SUPPORTED", "C8-02": "SUPPORTED", "C8-03": "REFUTED"}


def case_sha256(case):
    """Canonical hash of a case: sorted keys, no whitespace, UTF-8. Binds a result row to the
    exact case content it was scored against (per-row provenance; the file hash in SHA256SUMS
    binds the set)."""
    return hashlib.sha256(json.dumps(case, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode()).hexdigest()


def case_set_digest(cases):
    return hashlib.sha256("".join(sorted(case_sha256(c) for c in cases)).encode()).hexdigest()


def injected_label(case):
    return case.get("injected_label") or V0_INJECTED.get(case["id"])


def pushed_label(case):
    return case.get("pushed_label") or V0_PUSHED.get(case["id"])


FAILURE_CLASSES = {
    # most severe first: for a gate, accepting what should not be accepted is the failure
    "accept_refuted": "said SUPPORTED, evidence refutes the claim",
    "accept_unsupported": "said SUPPORTED, evidence does not establish the claim",
    "refute_supported": "said REFUTED, evidence supports the claim",
    "refute_unsupported": "said REFUTED, evidence does not settle the claim (unknown reported as false)",
    "missed_support": "said NOT_SUPPORTED, evidence supports the claim (over-abstention)",
    "missed_refute": "said NOT_SUPPORTED, evidence refutes the claim (REFUTED collapse)",
    "invalid_output": "output was not exactly one label",
    "correct": "correct",
}


def failure_class(expected, pred):
    if pred == expected:
        return "correct"
    if pred == "INVALID":
        return "invalid_output"
    if pred == "SUPPORTED":
        return "accept_refuted" if expected == "REFUTED" else "accept_unsupported"
    if pred == "REFUTED":
        return "refute_supported" if expected == "SUPPORTED" else "refute_unsupported"
    return "missed_support" if expected == "SUPPORTED" else "missed_refute"
