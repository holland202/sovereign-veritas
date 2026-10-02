"""Consensus gates: several extractors label each admissible item; a deterministic rule merges
their stances BEFORE gate.decide() sees them. Pure functions, no I/O.

unanimous: an item counts as TRUE (or FALSE) only if every extractor says so; any
           disagreement, NEITHER, or INVALID makes it NEITHER. Fail-closed by construction:
           consensus can only remove TRUE stances that a single extractor would have passed.
majority:  strict majority of TRUE / FALSE, else NEITHER (exploratory only).

The point under test: a consensus of k extractors cuts wrong acceptances only to the extent
that their errors are NOT correlated. The joint-error model in sim_gate.py estimates that
correlation from recorded stances instead of assuming independence.
"""
import gate

DIRECTIONAL = ("TRUE", "FALSE")


def _norm(s):
    return s if s in DIRECTIONAL else "NEITHER"


def unanimous(stance_lists):
    """stance_lists: one list per extractor, each aligned to case['evidence'] (None = inadmissible)."""
    out = []
    for per_item in zip(*stance_lists, strict=True):
        if per_item[0] is None:
            assert all(s is None for s in per_item)
            out.append(None)
            continue
        vals = {_norm(s) for s in per_item}
        out.append(vals.pop() if len(vals) == 1 else "NEITHER")
    return out


def majority(stance_lists):
    out = []
    k = len(stance_lists)
    for per_item in zip(*stance_lists, strict=True):
        if per_item[0] is None:
            out.append(None)
            continue
        vals = [_norm(s) for s in per_item]
        win = [d for d in DIRECTIONAL if vals.count(d) * 2 > k]
        out.append(win[0] if win else "NEITHER")
    return out


def decide(case, stance_lists, policy="unanimous"):
    merged = {"unanimous": unanimous, "majority": majority}[policy](stance_lists)
    return gate.decide(case, merged)
