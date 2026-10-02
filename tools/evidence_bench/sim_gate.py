#!/usr/bin/env python3
"""Bayesian error-propagation simulation: predict how a deterministic gate behaves on a NEW
case set, from how unreliable its extractor was on the OLD one — before running anything.

    python sim_gate.py --train-label container --target heldout/cases_h1.jsonl

Model (stated so it can be wrong):
  * An extractor's stance on an admissible item depends only on the item's gold stance
    (support / refute / neutral) — not on category, wording, injection, or position.
  * Per model and gold row, the stance distribution over {TRUE, FALSE, NEITHER} gets a
    Dirichlet(1,1,1) prior updated with the A2 counts (INVALID counted as NEITHER, as the
    gate does).
  * Items are conditionally independent given gold stance.
  * Consensus, two models: either INDEPENDENT (product of the two marginals) or JOINT
    (Dirichlet(0.5) over the 9 joint outcomes per gold row, counted from the items both
    models labelled) — the gap between the two is the measured cost of correlated errors.

For each of D posterior draws we sample parameters, then sample every admissible item's
stance on the target cases, run the real gate.decide(), and score. The spread across draws
is the posterior predictive interval (parameter uncertainty + finite-sample noise).

If observed held-out results fall outside these intervals, the stance-only model is wrong:
error rates depend on more than the gold stance (for example on item subtype), and the
v0 confusion matrices do not transfer.
"""
import argparse, json, os, random, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gate  # noqa: E402
import consensus  # noqa: E402

S3 = ("TRUE", "FALSE", "NEITHER")
GOLD = ("support", "refute", "neutral")
MODELS = ["qwen2.5-1.5b-instruct-q4_k_m", "LFM2.5-1.2B-Instruct-Q4_K_M",
          "Qwen_Qwen3.5-2B-Q4_K_M", "Qwen_Qwen3.5-4B-Q4_K_M"]
SHORT = {"qwen2.5-1.5b-instruct-q4_k_m": "Qwen2.5-1.5B", "LFM2.5-1.2B-Instruct-Q4_K_M": "LFM2.5-1.2B",
         "Qwen_Qwen3.5-2B-Q4_K_M": "Qwen3.5-2B", "Qwen_Qwen3.5-4B-Q4_K_M": "Qwen3.5-4B"}
PAIRS = [("Qwen_Qwen3.5-2B-Q4_K_M", "LFM2.5-1.2B-Instruct-Q4_K_M"),   # registered primary: cross-family
         ("Qwen_Qwen3.5-2B-Q4_K_M", "Qwen_Qwen3.5-4B-Q4_K_M")]        # same family, exploratory


def norm(s):
    return s if s in ("TRUE", "FALSE") else "NEITHER"


def load_training(label):
    """Per model: list of (case_id, item_index, gold_stance, emitted) for admissible items, rep 0."""
    out = {}
    for m in MODELS:
        rows = []
        for l in open(os.path.join(HERE, "results", label, "decomposed", m + ".jsonl")):
            r = json.loads(l)
            if r["rep"] != 0:
                continue
            for i, (s, g) in enumerate(zip(r["stances"], r["gold_stances"])):
                if s is not None:
                    rows.append((r["id"], i, g, norm(s)))
        out[m] = rows
    return out


def dirichlet(rng, alphas):
    xs = [rng.gammavariate(a, 1.0) for a in alphas]
    t = sum(xs)
    return [x / t for x in xs]


def draw_from(rng, probs, outcomes):
    u, acc = rng.random(), 0.0
    for p, o in zip(probs, outcomes):
        acc += p
        if u < acc:
            return o
    return outcomes[-1]


def score(cases, preds):
    n = len(cases)
    neg = [i for i, c in enumerate(cases) if c["expected"] != "SUPPORTED"]
    ref = [i for i, c in enumerate(cases) if c["expected"] == "REFUTED"]
    return {"acc": sum(p == c["expected"] for p, c in zip(preds, cases)) / n,
            "unsafe_accept": sum(preds[i] == "SUPPORTED" for i in neg) / len(neg),
            "refuted_recall": sum(preds[i] == "REFUTED" for i in ref) / len(ref)}


def simulate(cases, policies, train, draws, seed):
    rng = random.Random(seed)
    counts = {m: {g: [0, 0, 0] for g in GOLD} for m in MODELS}
    for m, rows in train.items():
        for _, _, g, s in rows:
            counts[m][g][S3.index(s)] += 1
    joint = {}
    for a, b in PAIRS:
        ia = {(cid, i): (g, s) for cid, i, g, s in train[a]}
        ib = {(cid, i): s for cid, i, g, s in train[b]}
        jc = {g: [0] * 9 for g in GOLD}
        for k, (g, s) in ia.items():
            if k in ib:
                jc[g][S3.index(s) * 3 + S3.index(ib[k])] += 1
        joint[(a, b)] = jc
    JOINT_OUT = [(x, y) for x in S3 for y in S3]
    results = defaultdict(lambda: defaultdict(list))
    for _ in range(draws):
        theta = {m: {g: dirichlet(rng, [1 + c for c in counts[m][g]]) for g in GOLD} for m in MODELS}
        theta_j = {p: {g: dirichlet(rng, [0.5 + c for c in joint[p][g]]) for g in GOLD} for p in PAIRS}
        for pol in policies:
            preds = []
            for c in cases:
                adm = [gate.admissible(it) for it in c["evidence"]]
                if pol[0] == "single":
                    st = [draw_from(rng, theta[pol[1]][it["stance"]], S3) if ok else None
                          for it, ok in zip(c["evidence"], adm)]
                    preds.append(gate.decide(c, st))
                elif pol[0] == "unanimous_indep":
                    lists = [[draw_from(rng, theta[m][it["stance"]], S3) if ok else None
                              for it, ok in zip(c["evidence"], adm)] for m in pol[1]]
                    preds.append(consensus.decide(c, lists))
                elif pol[0] == "unanimous_joint":
                    pairs = [draw_from(rng, theta_j[pol[1]][it["stance"]], JOINT_OUT) if ok else (None, None)
                             for it, ok in zip(c["evidence"], adm)]
                    preds.append(consensus.decide(c, [[p[0] for p in pairs], [p[1] for p in pairs]]))
            for k, v in score(cases, preds).items():
                results[pol_name(pol)][k].append(v)
    return results, counts, joint


def pol_name(pol):
    if pol[0] == "single":
        return SHORT[pol[1]]
    names = " ∧ ".join(SHORT[m] for m in pol[1])
    return f"{names} ({'independent' if pol[0] == 'unanimous_indep' else 'joint'} errors)"


def quant(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, max(0, int(round(q * (len(xs) - 1)))))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train-label", default="container")
    ap.add_argument("--target", default=os.path.join(HERE, "heldout", "cases_h1.jsonl"))
    ap.add_argument("--draws", type=int, default=4000)
    ap.add_argument("--seed", type=int, default=20261002)
    ap.add_argument("--out", default=os.path.join(HERE, "results", "sim_h1_predictions.json"))
    a = ap.parse_args()
    cases = [json.loads(l) for l in open(a.target)]
    train = load_training(a.train_label)
    policies = [("single", m) for m in MODELS]
    for p in PAIRS:
        policies += [("unanimous_indep", p), ("unanimous_joint", p)]
    res, counts, joint = simulate(cases, policies, train, a.draws, a.seed)
    table = {}
    for name, mets in res.items():
        table[name] = {k: {"p05": round(quant(v, 0.05), 4), "p50": round(quant(v, 0.5), 4),
                           "p95": round(quant(v, 0.95), 4)} for k, v in mets.items()}
    out = {"target": os.path.relpath(a.target, HERE), "train": f"results/{a.train_label}/decomposed (rep 0)",
           "draws": a.draws, "seed": a.seed, "training_counts": counts,
           "training_joint_counts": {" & ".join(SHORT[m] for m in p): j for p, j in joint.items()},
           "predictions": table}
    json.dump(out, open(a.out, "w"), indent=2, ensure_ascii=False)
    print(markdown(table))


def markdown(table):
    lines = ["| policy (decomposed) | accuracy 90% PI | unsafe accept 90% PI | REFUTED recall 90% PI |",
             "|---|---|---|---|"]
    for name, m in table.items():
        f = lambda k: f"{m[k]['p50']:.3f} [{m[k]['p05']:.3f}, {m[k]['p95']:.3f}]"
        lines.append(f"| {name} | {f('acc')} | {f('unsafe_accept')} | {f('refuted_recall')} |")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
