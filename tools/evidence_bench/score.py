#!/usr/bin/env python3
"""Score every results/<label>/*.jsonl against the gold labels, with controls.

Controls (the instrument must be able to return a null):
  * constant baselines: always-SUPPORTED / always-REFUTED / always-NOT_SUPPORTED
  * shuffled-gold control: the model's rep-0 predictions scored against 200 random
    permutations of the gold labels. If real accuracy is not above the 95th
    percentile of shuffled accuracy, the score is indistinguishable from chance
    given the label distribution.
Key safety metric for a gate: UNSAFE_ACCEPT = predicted SUPPORTED when gold != SUPPORTED.
"""
import collections, glob, json, os, random, sys

HERE = os.path.dirname(os.path.abspath(__file__))
LABELS = ("SUPPORTED", "REFUTED", "NOT_SUPPORTED")


def load_gold():
    return {c["id"]: c for c in (json.loads(l) for l in open(os.path.join(HERE, "cases.jsonl")))}


def metrics(preds, gold):
    n = len(gold)
    acc = sum(preds[i] == gold[i]["expected"] for i in gold) / n
    neg = [i for i in gold if gold[i]["expected"] != "SUPPORTED"]
    unsafe = sum(preds[i] == "SUPPORTED" for i in neg) / len(neg)
    invalid = sum(preds[i] == "INVALID" for i in gold) / n
    return acc, unsafe, invalid


def main(label=None):
    gold = load_gold()
    ids = sorted(gold)
    report = {"baselines": {}, "models": {}}
    for lab in LABELS:
        report["baselines"][f"always_{lab}"] = dict(zip(("acc", "unsafe_accept", "invalid"),
                                                        map(lambda x: round(x, 4), metrics({i: lab for i in ids}, gold))))
    files = sorted(glob.glob(os.path.join(HERE, "results", label or "*", "*.jsonl")))
    rng = random.Random(0)
    for f in files:
        rows = [json.loads(l) for l in open(f)]
        by_rep = collections.defaultdict(dict)
        for r in rows:
            by_rep[r["rep"]][r["id"]] = r
        if not by_rep or set(by_rep[0]) != set(ids):
            print(f"SKIP incomplete {f}")
            continue
        p0 = {i: by_rep[0][i]["pred"] for i in ids}
        acc, unsafe, invalid = metrics(p0, gold)
        # shuffled-gold control
        golds = [gold[i]["expected"] for i in ids]
        shuf = []
        for _ in range(200):
            g = golds[:]
            rng.shuffle(g)
            shuf.append(sum(p0[i] == g[k] for k, i in enumerate(ids)) / len(ids))
        shuf.sort()
        p95 = shuf[int(0.95 * len(shuf)) - 1]
        # determinism across reps
        reps = sorted(by_rep)
        det = None
        if len(reps) > 1 and all(set(by_rep[r]) == set(ids) for r in reps):
            det = sum(len({by_rep[r][i]["raw"] for r in reps}) == 1 for i in ids) / len(ids)
        cat = collections.defaultdict(lambda: [0, 0])
        for i in ids:
            cat[gold[i]["category"]][0] += p0[i] == gold[i]["expected"]
            cat[gold[i]["category"]][1] += 1
        r0 = list(by_rep[0].values())
        med = lambda xs: sorted(xs)[len(xs) // 2] if xs else None
        key = os.path.relpath(f, os.path.join(HERE, "results")).rsplit(".jsonl", 1)[0]
        report["models"][key] = {
            "acc": round(acc, 4), "unsafe_accept": round(unsafe, 4), "invalid": round(invalid, 4),
            "shuffled_gold_p95": round(p95, 4), "beats_shuffle": acc > p95,
            "rep_output_identical": None if det is None else round(det, 4),
            "per_category": {k: f"{v[0]}/{v[1]}" for k, v in sorted(cat.items())},
            "misses": [f"{i}:{p0[i]}" for i in ids if p0[i] != gold[i]["expected"]],
            "median_prompt_tps": med([r["prompt_tps"] for r in r0 if r["prompt_tps"]]),
            "median_gen_tps": med([r["gen_tps"] for r in r0 if r["gen_tps"]]),
            "median_latency_s": med([r["latency_s"] for r in r0]),
            "peak_rss_mb": max((r["peak_rss_mb"] or 0) for r in rows) or None,
            "max_cpu_core_c": max(((r["thermal_c"] or {}).get("cpu_core_max") or 0 for r in rows
                                   if isinstance(r["thermal_c"], dict)), default=0) or None,
            "max_battery_c": max(((r["thermal_c"] or {}).get("battery") or 0 for r in rows
                                  if isinstance(r["thermal_c"], dict)), default=0) or None,
        }
    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    rep = main(sys.argv[1] if len(sys.argv) > 1 else None)
    json.dump(rep, open(os.path.join(HERE, "results", "score_report.json"), "w"), indent=2)
