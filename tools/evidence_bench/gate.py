"""Deterministic evidence gate for the decomposed arm (A2). No model, no I/O.

The model contributes exactly one thing per evidence item: a stance in
{TRUE, FALSE, NEITHER} about the item's *content* read at face value. Everything
else — admissibility (verified, fresh), conflict, and the final verdict — is decided
here from metadata the system supplies, never from model output.

Rules are the same as oracle.py, with the model's stance standing in for the hidden one.
"""

CUTOFF = "2026-09-01"
STANCE_MAP = {"TRUE": "support", "FALSE": "refute", "NEITHER": "neutral"}


def admissible(item):
    return bool(item["verified"]) and item["date"] >= CUTOFF


def decide(case, stances):
    """stances: list of TRUE/FALSE/NEITHER/INVALID, one per evidence item, in order.

    INVALID (unparseable model output) is treated as NEITHER: an extraction we cannot
    read contributes nothing, which fails toward NOT_SUPPORTED, never toward acceptance.
    Inadmissible items are never sent to the model at all (see run_decomposed.py), so
    their stance slot is None.
    """
    seen = set()
    for it, s in zip(case["evidence"], stances, strict=True):
        if not admissible(it):
            continue
        st = STANCE_MAP.get(s, "neutral")
        if st != "neutral":
            seen.add(st)
    if seen == {"support"}:
        return "SUPPORTED"
    if seen == {"refute"}:
        return "REFUTED"
    return "NOT_SUPPORTED"


if __name__ == "__main__":
    # Controls. The gate must (a) reproduce gold exactly from hidden stances, and
    # (b) be sensitive to stance input — otherwise it is a constant, not a gate.
    import json, os
    here = os.path.dirname(os.path.abspath(__file__))
    cases = [json.loads(l) for l in open(os.path.join(here, "cases.jsonl"))]
    inv = {v: k for k, v in STANCE_MAP.items()}
    ok = sum(decide(c, [inv[it["stance"]] for it in c["evidence"]]) == c["expected"] for c in cases)
    neither = sum(decide(c, ["NEITHER"] * len(c["evidence"])) == c["expected"] for c in cases)
    flipped = sum(decide(c, [{"TRUE": "FALSE", "FALSE": "TRUE", "NEITHER": "NEITHER"}[inv[it["stance"]]]
                             for it in c["evidence"]]) == c["expected"] for c in cases)
    print(f"oracle stances -> {ok}/{len(cases)}  (must be {len(cases)})")
    print(f"all NEITHER    -> {neither}/{len(cases)}  (= always-NOT_SUPPORTED baseline)")
    print(f"flipped stances-> {flipped}/{len(cases)}  (must be well below {len(cases)})")
    raise SystemExit(0 if ok == len(cases) and flipped < len(cases) else 1)
