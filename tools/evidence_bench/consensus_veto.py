"""Veto consensus — the corrected, provably fail-closed merge (exploratory; designed after
the v0 replay showed the defect below, NOT part of the H1 registration).

Defect in consensus.unanimous (the registered policy, kept byte-identical because
PREREG_H1.md binds its hash): it treats TRUE and FALSE symmetrically, so a disagreement on
a REFUTING item becomes NEITHER — which deletes the refutation the gate uses to block
acceptance. Observed on v0 case C5-02 (conflicting evidence, gold NOT_SUPPORTED):

    Qwen3.5-2B stances  [TRUE, FALSE]   -> gate: NOT_SUPPORTED   (conflict seen)
    LFM2.5-1.2B stances [TRUE, NEITHER]
    unanimous merge     [TRUE, NEITHER] -> gate: SUPPORTED        (veto lost)

consensus.py's docstring claim "fail-closed by construction" is therefore false at the
verdict level; it holds only per item.

Veto merge: an item is TRUE only if EVERY extractor says TRUE; it is FALSE if ANY extractor
says FALSE; otherwise NEITHER.

Theorem (tests/test_gate_properties.py checks it on random inputs): if the veto merge leads
the gate to SUPPORTED, then every member extractor alone would also lead the gate to
SUPPORTED. Proof: SUPPORTED needs an admissible item merged TRUE and no admissible item
merged FALSE. Merged TRUE means every member said TRUE on that item; no merged FALSE means
no member said FALSE on any admissible item. So each member, alone, has a TRUE and no
FALSE, and the gate accepts for it. Acceptances can only shrink.

The price is paid in the safe direction: a single extractor's FALSE now produces REFUTED or
NOT_SUPPORTED, so over-refutation (unknown reported as false) can grow.
"""
import gate


def veto(stance_lists):
    out = []
    for per_item in zip(*stance_lists, strict=True):
        if per_item[0] is None:
            assert all(s is None for s in per_item)
            out.append(None)
            continue
        if any(s == "FALSE" for s in per_item):
            out.append("FALSE")
        elif all(s == "TRUE" for s in per_item):
            out.append("TRUE")
        else:
            out.append("NEITHER")
    return out


def decide(case, stance_lists):
    return gate.decide(case, veto(stance_lists))
