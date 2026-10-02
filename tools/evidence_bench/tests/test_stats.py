"""Exact statistics: known values, closed forms, brute force, and scipy where installed."""
import _path  # noqa: F401
import itertools, random, unittest
import stats

try:
    import scipy.stats as ss
except ImportError:          # Termux without scipy: the exact tests below still run
    ss = None


class Exact(unittest.TestCase):
    def test_mcnemar_known_values(self):
        self.assertEqual(stats.mcnemar_exact(7, 0), 0.015625)        # 2 / 2**7
        self.assertEqual(stats.mcnemar_exact(0, 7), 0.015625)
        self.assertEqual(stats.mcnemar_exact(5, 3), 0.7265625)       # the withdrawn "4B less safe" claim
        self.assertEqual(stats.mcnemar_exact(4, 4), 1.0)
        self.assertEqual(stats.mcnemar_exact(0, 0), 1.0)

    def test_holm(self):
        self.assertEqual([round(x, 12) for x in stats.holm([0.01, 0.04, 0.03])], [0.03, 0.06, 0.06])
        self.assertEqual(stats.holm([0.6, 0.7]), [1.0, 1.0])

    def test_clopper_pearson_closed_forms_and_symmetry(self):
        lo, hi = stats.clopper_pearson(0, 30)
        self.assertEqual(lo, 0.0)
        self.assertAlmostEqual(hi, 1 - 0.025 ** (1 / 30), places=9)
        for k in range(31):
            lo, hi = stats.clopper_pearson(k, 30)
            lo2, hi2 = stats.clopper_pearson(30 - k, 30)
            self.assertAlmostEqual(lo, 1 - hi2, places=9)
            self.assertTrue(lo <= k / 30 <= hi)

    def test_permutation_null_equals_brute_force(self):
        r = random.Random(11)
        for _ in range(20):
            preds = [r.choice("SRN") for _ in range(6)]
            golds = [r.choice("SRN") for _ in range(6)]
            perms = list(itertools.permutations(golds))       # all 720 orderings, equally likely
            brute = {}
            for g in perms:
                m = sum(p == x for p, x in zip(preds, g))
                brute[m] = brute.get(m, 0) + 1
            dist = stats.perm_null_matches(preds, golds)
            self.assertEqual(sorted(dist), sorted(brute))
            for m, cnt in brute.items():
                self.assertAlmostEqual(dist[m], cnt / len(perms), places=12)

    def test_perm_test_tail(self):
        obs, p, _ = stats.perm_test(["S"] * 3 + ["N"] * 3, ["S"] * 3 + ["N"] * 3)
        self.assertEqual(obs, 6)
        self.assertAlmostEqual(p, 1 / 20)      # one arrangement in C(6,3) = 20 matches all six

    def test_kappas(self):
        self.assertEqual(stats.cohen_kappa(list("ABAB"), list("ABAB")), 1.0)
        self.assertAlmostEqual(stats.cohen_kappa(list("AABB"), list("ABAB")), 0.0)
        self.assertEqual(stats.fleiss_kappa([["A"] * 3, ["B"] * 3, ["A"] * 3]), 1.0)
        # with two raters Fleiss' kappa is Scott's pi: check against an independent computation
        r = random.Random(12)
        x = [r.choice("TFN") for _ in range(40)]
        y = [r.choice("TFN") if r.random() < 0.5 else a for a in x]
        po = sum(a == b for a, b in zip(x, y)) / 40
        pe = sum(((x + y).count(l) / 80) ** 2 for l in "TFN")
        self.assertAlmostEqual(stats.fleiss_kappa([[a, b] for a, b in zip(x, y)]), (po - pe) / (1 - pe), places=12)


@unittest.skipIf(ss is None, "scipy not installed; the exact-value tests above still run")
class AgainstScipy(unittest.TestCase):
    def test_clopper_pearson(self):
        for k, n in [(0, 4), (1, 4), (1, 30), (7, 30), (27, 110), (55, 110), (110, 110)]:
            ci = ss.binomtest(k, n).proportion_ci(confidence_level=0.95, method="exact")
            lo, hi = stats.clopper_pearson(k, n)
            self.assertAlmostEqual(lo, ci.low, places=7)
            self.assertAlmostEqual(hi, ci.high, places=7)

    def test_mcnemar_is_a_two_sided_binomial_test(self):
        for b, c in [(7, 0), (5, 3), (17, 0), (9, 1), (12, 13), (1, 30)]:
            self.assertAlmostEqual(stats.mcnemar_exact(b, c), ss.binomtest(min(b, c), b + c, 0.5).pvalue, places=12)


if __name__ == "__main__":
    unittest.main()
