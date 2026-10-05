#!/usr/bin/env python3
"""amb1_probe.py - AMB-1: how much of the Gate do the 4,690 contract vectors pin down?

Usage:
  python tools/amb1_probe.py [--sabotage] [--json PATH]

Registration: docs/AMB1_PREREG.md. Stdlib only. Impostors are seeded random-split decision trees that fit every
vector; truth is kernel_gate(); verifier_gate() is the independent cross-check (A4).
--sabotage replaces the impostors with the Gate itself: round-0 unsafe ALLOW is 0, A2 must be refuted, exit 1.
"""
from __future__ import annotations

import collections, copy, hashlib, json, os, pathlib, random, sys

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
import gate_contract as gc  # noqa: E402

RECORDED = None  # pinned in a separate commit after the registered run
ROUNDS, ADD, POOL, SEEDS = 8, 100, 10000, (0, 1, 2, 3, 4)
RANK = {"REFUSE": 0, "DEFER": 1, "ALLOW": 2}  # majority ties go to the lower rank


def flat(o, p=""):
    if isinstance(o, dict) and o:
        for k, v in o.items():
            yield from flat(v, p + "." + k)
    else:
        yield p, json.dumps(o, sort_keys=True)


def setp(o, p, v):
    ks = p.strip(".").split(".")
    for k in ks[:-1]:
        if not isinstance(o.get(k), dict):
            return
        o = o[k]
    o[ks[-1]] = json.loads(v)


def grow(rows, labels, seed):
    """Random-split tree fitting every row. rows: list of frozensets of feature ids."""
    rng = random.Random(seed)
    nodes = []  # ("leaf", label) or ("split", feature, child_with, child_without)

    def build(idx):
        labs = collections.Counter(labels[i] for i in idx)
        me = len(nodes)
        nodes.append(None)
        if len(labs) == 1:
            nodes[me] = ("leaf", next(iter(labs)))
            return me
        cnt = collections.Counter(f for i in idx for f in rows[i])
        cand = sorted(f for f, c in cnt.items() if c < len(idx))
        if not cand:  # identical rows, different labels: majority
            nodes[me] = ("leaf", sorted(labs, key=lambda d: (-labs[d], RANK.get(d, -1)))[0])
            return me
        f = rng.choice(cand)
        a = build([i for i in idx if f in rows[i]])
        b = build([i for i in idx if f not in rows[i]])
        nodes[me] = ("split", f, a, b)
        return me

    sys.setrecursionlimit(max(10000, sys.getrecursionlimit()))
    build(list(range(len(rows))))
    return nodes


def predict(nodes, row):
    n = nodes[0]
    while n[0] == "split":
        n = nodes[n[2]] if n[1] in row else nodes[n[3]]
    return n[1]


def main():
    sabotage = "--sabotage" in sys.argv
    print(f"AMB-1 | {'SABOTAGE: impostors are the Gate itself' if sabotage else 'registered run'} | python "
          f"{sys.version.split()[0]}")
    vectors = [json.loads(ln) for ln in open(REPO / "contract/gate_vectors.jsonl", encoding="utf-8")]
    paths = sorted({p for v in vectors for p, _ in flat(v["input"])})
    vals = collections.defaultdict(set)
    for v in vectors:
        for p, x in flat(v["input"]):
            vals[p].add(x)
    fid = {}
    for p in paths:
        for x in sorted(vals[p] | {"<missing>"}):
            fid[(p, x)] = len(fid)

    def feat(inp):
        d = dict(flat(inp))
        return frozenset(fid[(p, d.get(p, "<missing>"))] for p in paths if (p, d.get(p, "<missing>")) in fid)

    kernel, verifier = gc.kernel_gate(), gc.verifier_gate()

    def run(decide, inp):
        try:
            d, reasons = decide(copy.deepcopy(inp))
            return d, list(reasons)
        except Exception as exc:  # a crash is never a decision
            return f"RAISE:{type(exc).__name__}", []

    rng = random.Random(1)

    def recomb():
        b = copy.deepcopy(rng.choice(vectors)["input"])
        for p in rng.sample(paths, rng.choice([2, 3, 4])):
            setp(b, p, rng.choice(sorted(vals[p])))
        return b

    S = [recomb() for _ in range(POOL)]
    H = [recomb() for _ in range(POOL)]
    k_S, k_H = [run(kernel, i) for i in S], [run(kernel, i) for i in H]
    v_S, v_H = [run(verifier, i) for i in S], [run(verifier, i) for i in H]
    t_S, t_H = [d for d, _ in k_S], [d for d, _ in k_H]
    f_S, f_H = [feat(i) for i in S], [feat(i) for i in H]
    mism = sum(a != b for a, b in zip(k_S + k_H, v_S + v_H))

    X = [feat(v["input"]) for v in vectors]
    y = [v["expect"]["decision"] for v in vectors]
    rng2, used, rounds = random.Random(2), set(), []
    a1 = None
    for rnd in range(ROUNDS + 1):
        trees = [None] * len(SEEDS) if sabotage else [grow(X, y, s) for s in SEEDS]
        if rnd == 0:
            a1 = sabotage or all(predict(t, X[i]) == y[i] for t in trees for i in range(len(vectors)))
        p = (lambda t, f, truth: truth) if sabotage else (lambda t, f, truth: predict(t, f))  # noqa: E731
        unsafe = [sum(p(t, f, g) == "ALLOW" and g != "ALLOW" for f, g in zip(f_H, t_H)) for t in trees]
        row = {"round": rnd, "vectors": len(X), "unsafe_allow_H": unsafe}
        if rnd < ROUNDS:
            cand = [k for k in range(POOL) if k not in used and any(p(t, f_S[k], t_S[k]) != t_S[k] for t in trees)]
            rng2.shuffle(cand)
            for k in cand[:ADD]:
                used.add(k)
                X.append(f_S[k])
                y.append(t_S[k])
            row["added"] = len(cand[:ADD])
        rounds.append(row)
        print(f"  round {rnd}: vectors {len(X) - row.get('added', 0):5d}  unsafe ALLOW on H {unsafe}"
              + (f"  added {row['added']}" if "added" in row else ""))
    r = {"truth_H": dict(sorted(collections.Counter(t_H).items())),
         "truth_S": dict(sorted(collections.Counter(t_S).items())),
         "kernel_verifier_mismatch": mism, "a1_fits_all_vectors": a1, "rounds": rounds}
    print(f"  truth on H {r['truth_H']}  kernel/verifier mismatches on 20000: {mism}")

    m0, m8 = max(rounds[0]["unsafe_allow_H"]), max(rounds[-1]["unsafe_allow_H"])
    v = {"A1": bool(a1), "A2": m0 >= 500, "A3": m8 <= 50 and m8 * 10 <= m0, "A4": mism == 0}
    print()
    for k, x in v.items():
        print(f"  {k}  {'HELD' if x else 'REFUTED'}")
    held = tuple(k for k, x in v.items() if x)
    print(f"VERDICT {len(held)} of {len(v)} as registered (A5 is --sabotage; A6 is the door)")
    dg = hashlib.sha256(json.dumps({"results": r, "verdicts": v}, sort_keys=True).encode()).hexdigest()
    print(f"DIGEST {dg}")
    if "--json" in sys.argv:
        pathlib.Path(sys.argv[sys.argv.index("--json") + 1]).write_text(
            json.dumps({"results": r, "verdicts": v}, sort_keys=True, indent=1) + "\n", encoding="utf-8")
    if sabotage or RECORDED is None:
        return 0 if all(v.values()) else 1
    return 0 if (held, dg) == RECORDED else 1


if __name__ == "__main__":
    sys.exit(main() or 0)
