"""Reproduce score.py's original Monte Carlo "shuffled-gold p95" exactly, for any file set.

score.py drew 200 shuffles per model from ONE random.Random(0) stream, iterating result files
in sorted order. So a model's p95 depended on which OTHER files existed: adding the
Qwen3.5-4B file (A1) shifted the stream for qwen2.5-1.5b, whose published v0 p95 0.4359
became 0.4615 in the committed score_report.json. This module reproduces both published
values from the raw files, which is how verify_claims.py checks RESULTS.md and
RESULTS_A1_A2.md. New analysis uses the exact permutation test (stats.perm_test) instead.
"""
import json, os, random

HERE = os.path.dirname(os.path.abspath(__file__))


def legacy_p95(stems, label="container"):
    """stems: the set of result-file stems that existed when the number was published."""
    with open(os.path.join(HERE, "cases.jsonl")) as fh:
        gold = {c["id"]: c for c in (json.loads(l) for l in fh)}
    ids = sorted(gold)
    rng = random.Random(0)
    out = {}
    for stem in sorted(stems):
        with open(os.path.join(HERE, "results", label, stem + ".jsonl")) as fh:
            rows = [json.loads(l) for l in fh]
        p0 = {r["id"]: r["pred"] for r in rows if r["rep"] == 0}
        golds = [gold[i]["expected"] for i in ids]
        shuf = []
        for _ in range(200):
            g = golds[:]
            rng.shuffle(g)
            shuf.append(sum(p0[i] == g[k] for k, i in enumerate(ids)) / len(ids))
        shuf.sort()
        out[stem] = round(shuf[int(0.95 * len(shuf)) - 1], 4)
    return out


V0_SET = ["LFM2.5-1.2B-Instruct-Q4_K_M", "Qwen_Qwen3.5-2B-Q4_K_M", "qwen2.5-1.5b-instruct-q4_k_m"]
A1_SET = V0_SET + ["Qwen_Qwen3.5-4B-Q4_K_M"]
