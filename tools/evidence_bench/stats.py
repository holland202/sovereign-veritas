"""Exact small-sample statistics, stdlib only (runs in Termux without scipy).

Every rate in this bench has a denominator between 4 and 110, so normal approximations are
wrong where it matters. Everything here is exact:

  clopper_pearson(k, n)      exact binomial confidence interval
  mcnemar_exact(b, c)        paired test on discordant counts (two-sided)
  perm_null_matches(p, g)    EXACT permutation distribution of #matches when the gold labels
                             are randomly re-assigned to cases (replaces the 200-draw Monte
                             Carlo "shuffled-gold p95", whose value depended on which other
                             result files existed — see STATS.md)
  cohen_kappa / fleiss_kappa agreement between extractors
  holm(pvals)                family-wise multiplicity adjustment

tests/test_stats.py cross-checks these against scipy when scipy is installed.
"""
from functools import lru_cache
from math import comb, lgamma, exp, log


def _binom_cdf(k, n, p):
    if p <= 0:
        return 1.0
    if p >= 1:
        return 1.0 if k >= n else 0.0
    s = 0.0
    lp, lq = log(p), log(1 - p)
    for i in range(0, k + 1):
        s += exp(lgamma(n + 1) - lgamma(i + 1) - lgamma(n - i + 1) + i * lp + (n - i) * lq)
    return min(1.0, s)


def clopper_pearson(k, n, alpha=0.05):
    """Exact (conservative) two-sided CI for a binomial proportion k/n."""
    if n == 0:
        return (0.0, 1.0)

    def solve(f, target):  # f increasing in p
        lo, hi = 0.0, 1.0
        for _ in range(100):
            mid = (lo + hi) / 2
            if f(mid) < target:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2

    lower = 0.0 if k == 0 else solve(lambda p: 1 - _binom_cdf(k - 1, n, p), alpha / 2)
    upper = 1.0 if k == n else solve(lambda p: 1 - _binom_cdf(k, n, p), 1 - alpha / 2)
    return (lower, upper)


def mcnemar_exact(b, c):
    """Two-sided exact McNemar p-value. b = #(A right, B wrong), c = #(A wrong, B right)."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(comb(n, i) for i in range(0, k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def perm_null_matches(preds, golds):
    """Exact distribution of the number of positions where pred == gold when the gold vector
    is uniformly permuted. Returns {matches: probability}. Exact integer arithmetic.

    Positions are grouped by predicted label (sizes a_i); the gold multiset has counts b_j.
    The number of distinct gold arrangements giving table n_ij is prod_i a_i!/prod_j n_ij!,
    out of n!/prod_j b_j! equally likely arrangements."""
    labels = sorted(set(golds) | set(preds))
    a = [sum(1 for p in preds if p == l) for l in labels]
    b = tuple(sum(1 for g in golds if g == l) for l in labels)
    n = len(preds)
    assert n == len(golds) and sum(b) == n

    def compositions(total, caps):
        if len(caps) == 1:
            if total <= caps[0]:
                yield (total,)
            return
        for x in range(0, min(total, caps[0]) + 1):
            for rest in compositions(total - x, caps[1:]):
                yield (x,) + rest

    @lru_cache(maxsize=None)
    def f(i, rem):
        if i == len(labels):
            return {0: 1}
        out = {}
        fact_ai = _fact(a[i])
        for k in compositions(a[i], rem):
            ways = fact_ai
            for kj in k:
                ways //= _fact(kj)
            nxt = tuple(r - kj for r, kj in zip(rem, k))
            for m, cnt in f(i + 1, nxt).items():
                mm = m + k[i]  # gold label == this pred label lands on the diagonal
                out[mm] = out.get(mm, 0) + ways * cnt
        return out

    dist = f(0, b)
    total = _fact(n)
    for bj in b:
        total //= _fact(bj)
    assert sum(dist.values()) == total
    return {m: cnt / total for m, cnt in sorted(dist.items())}


@lru_cache(maxsize=None)
def _fact(k):
    out = 1
    for i in range(2, k + 1):
        out *= i
    return out


def perm_test(preds, golds):
    """(observed matches, exact one-sided p = P(null >= observed), exact 95th percentile of matches)."""
    obs = sum(p == g for p, g in zip(preds, golds))
    dist = perm_null_matches(preds, golds)
    p = sum(pr for m, pr in dist.items() if m >= obs)
    cum, q95 = 0.0, None
    for m, pr in sorted(dist.items()):
        cum += pr
        if cum >= 0.95 and q95 is None:
            q95 = m
    return obs, p, q95


def cohen_kappa(x, y):
    labels = sorted(set(x) | set(y))
    n = len(x)
    po = sum(a == b for a, b in zip(x, y)) / n
    pe = sum((x.count(l) / n) * (y.count(l) / n) for l in labels)
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def fleiss_kappa(rows):
    """rows: list of per-item lists of category labels from k raters."""
    labels = sorted({l for r in rows for l in r})
    N, k = len(rows), len(rows[0])
    P = []
    tot = {l: 0 for l in labels}
    for r in rows:
        cnt = {l: r.count(l) for l in labels}
        for l in labels:
            tot[l] += cnt[l]
        P.append((sum(v * v for v in cnt.values()) - k) / (k * (k - 1)))
    Pbar = sum(P) / N
    pj = [tot[l] / (N * k) for l in labels]
    Pe = sum(p * p for p in pj)
    return (Pbar - Pe) / (1 - Pe) if Pe < 1 else 1.0


def holm(pvals):
    """Holm step-down adjusted p-values, same order as input."""
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i])
    adj = [0.0] * m
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * pvals[i]))
        adj[i] = running
    return adj


def fmt_rate(k, n):
    lo, hi = clopper_pearson(k, n)
    return f"{k}/{n} = {k / n:.3f} [{lo:.3f}, {hi:.3f}]"
