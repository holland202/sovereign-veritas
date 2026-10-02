"""Exploratory, NOT preregistered: gate.py with fail-closed handling of unreadable answers.

Found 2026-10-02 by tests/test_gate_properties.py, the first time anyone tested the
property "an unreadable extractor answer never creates an acceptance". gate.py treats
INVALID (an answer the parser could not read) exactly like NEITHER, and its docstring says
this "fails toward NOT_SUPPORTED, never toward acceptance". That is true for one item on its
own and false for a case: if the unreadable answer belonged to the item that refutes the
claim, its veto disappears. Smallest counterexample: two admissible items, answers
[TRUE, INVALID] -> gate.decide says SUPPORTED, although the second answer may have been
FALSE (conflict -> NOT_SUPPORTED). Unknown is not the same as irrelevant.

Same root cause as the unanimous-consensus defect (consensus_veto.py): an answer that was
missing or disputed was mapped to "no opinion".

gate.py is bound by hash in PREREG_H1.md and is not edited; every registered number uses it.
This module is the proposed replacement, to be registered before it scores anything.

Rule: an unreadable answer (anything but TRUE/FALSE/NEITHER, including a missing one) on an
ADMISSIBLE item makes the verdict NOT_SUPPORTED. The gate cannot vouch for a claim when part
of the admissible evidence could not be read, and it cannot vouch for a refutation either.
Answers on inadmissible items are ignored, as before. When every admissible answer is
readable, gate_strict.decide == gate.decide (tested).

    python gate_strict.py     # prints the counts quoted in STATS.md
"""
import glob, itertools, json, os
import gate

HERE = os.path.dirname(os.path.abspath(__file__))
LABELS = frozenset(gate.STANCE_MAP)          # TRUE, FALSE, NEITHER


def decide(case, stances):
    for it, s in zip(case["evidence"], stances, strict=True):
        if gate.admissible(it) and s not in LABELS:
            return "NOT_SUPPORTED"
    return gate.decide(case, stances)


def veto(stance_lists):
    """consensus_veto.veto with the same fix. Per item: never asked by anyone -> None;
    FALSE from any extractor -> FALSE; else an unreadable answer from any -> INVALID;
    else TRUE only if all say TRUE; else NEITHER."""
    out = []
    for per_item in zip(*stance_lists, strict=True):
        if all(s is None for s in per_item):
            out.append(None)
        elif "FALSE" in per_item:
            out.append("FALSE")
        elif any(s not in LABELS for s in per_item):
            out.append("INVALID")
        elif all(s == "TRUE" for s in per_item):
            out.append("TRUE")
        else:
            out.append("NEITHER")
    return out


def decide_consensus(case, stance_lists):
    return decide(case, veto(stance_lists))


def corruption_counts(max_items=3):
    """Every pattern of readable answers on 1..max_items admissible items, with one answer
    replaced by INVALID. Counts how often that turns a non-acceptance into an acceptance, or a
    non-refutation into a refutation."""
    gates = (("gate", gate.decide), ("gate_strict", decide))
    res = {"corruptions": 0, **{g: {"new_accept": 0, "new_refute": 0} for g, _ in gates}}
    for n in range(1, max_items + 1):
        case = {"evidence": [{"verified": True, "date": "2026-09-10"}] * n}
        for st in itertools.product(sorted(LABELS), repeat=n):
            for i in range(n):
                bad = list(st)
                bad[i] = "INVALID"
                res["corruptions"] += 1
                for g, f in gates:
                    before, after = f(case, list(st)), f(case, bad)
                    res[g]["new_accept"] += before != "SUPPORTED" and after == "SUPPORTED"
                    res[g]["new_refute"] += before != "REFUTED" and after == "REFUTED"
    return res


def recorded_impact(label="container", cases_path="cases.jsonl"):
    """Unreadable answers on admissible items in every recorded decomposed run of `label`,
    and how many recorded verdicts the strict rule would change."""
    with open(os.path.join(HERE, cases_path)) as fh:
        cases = {c["id"]: c for c in (json.loads(l) for l in fh)}
    rows = answers = unreadable = changed = 0
    for f in sorted(glob.glob(os.path.join(HERE, "results", label, "decomposed*", "*.jsonl"))):
        with open(f) as fh:
            for line in fh:
                r = json.loads(line)
                c = cases[r["id"]]
                rows += 1
                for it, s in zip(c["evidence"], r["stances"], strict=True):
                    if gate.admissible(it):
                        answers += 1
                        unreadable += s not in LABELS
                changed += decide(c, r["stances"]) != gate.decide(c, r["stances"])
    return {"rows": rows, "admissible_answers": answers, "unreadable": unreadable, "verdicts_changed": changed}


if __name__ == "__main__":
    print(json.dumps({"corruption_counts": corruption_counts(),
                      "recorded_v0": recorded_impact("container", "cases.jsonl"),
                      "recorded_h1": recorded_impact("container_h1", os.path.join("heldout", "cases_h1.jsonl"))},
                     indent=2))
