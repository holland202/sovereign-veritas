"""Rule oracle: derive each case's label from hidden structure; must match the hand label.

Rules (identical to the ones the model is given in prompt.py):
  admissible item = verified AND fresh (dated on/after CUTOFF)
  only support stances among admissible items  -> SUPPORTED
  only refute stances among admissible items   -> REFUTED
  both, or neither                             -> NOT_SUPPORTED
"""
import json, sys

CUTOFF = "2026-09-01"

def oracle(case):
    stances = set()
    for it in case["evidence"]:
        assert it["fresh"] == (it["date"] >= CUTOFF), f"{case['id']}: fresh flag disagrees with date"
        if it["verified"] and it["fresh"] and it["stance"] != "neutral":
            stances.add(it["stance"])
    if stances == {"support"}:
        return "SUPPORTED"
    if stances == {"refute"}:
        return "REFUTED"
    return "NOT_SUPPORTED"

if __name__ == "__main__":
    cases = [json.loads(l) for l in open(sys.argv[1] if len(sys.argv) > 1 else "cases.jsonl")]
    bad = [(c["id"], c["expected"], oracle(c)) for c in cases if oracle(c) != c["expected"]]
    for b in bad:
        print("MISMATCH", *b)
    print(f"oracle agrees on {len(cases) - len(bad)}/{len(cases)}")
    sys.exit(1 if bad else 0)
