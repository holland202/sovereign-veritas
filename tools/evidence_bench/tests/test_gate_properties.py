"""Metamorphic and property tests for the deterministic gate and the consensus rules.

Random inputs are seeded (reproducible); each property runs a few thousand cases."""
import _path  # noqa: F401
import itertools, json, os, random, unittest
import gate, gate_strict, consensus, consensus_veto

BENCH = _path.BENCH
S = ["TRUE", "FALSE", "NEITHER", "INVALID"]
INV = {"support": "TRUE", "refute": "FALSE", "neutral": "NEITHER"}


def rand_item(r, admissible=None):
    verified = r.random() < 0.7 if admissible is None else admissible or r.random() < 0.5
    fresh = r.random() < 0.7 if admissible is None else (admissible or not verified)
    date = f"2026-09-{r.randint(1, 29):02d}" if fresh else f"2026-0{r.randint(3, 8)}-{r.randint(1, 28):02d}"
    if admissible is False and verified and fresh:
        verified = False
    return {"verified": verified, "date": date, "stance": r.choice(list(INV)), "text": "x", "source": "y"}


def rand_case(r, n=None):
    n = n or r.randint(1, 4)
    return {"evidence": [rand_item(r) for _ in range(n)], "framing": ""}


class GateProperties(unittest.TestCase):
    N = 4000

    def test_freshness_boundary_is_inclusive(self):
        on = {"evidence": [{"verified": True, "date": "2026-09-01", "stance": "support"}]}
        before = {"evidence": [{"verified": True, "date": "2026-08-31", "stance": "support"}]}
        self.assertEqual(gate.decide(on, ["TRUE"]), "SUPPORTED")       # "on or after the cutoff"
        self.assertEqual(gate.decide(before, ["TRUE"]), "NOT_SUPPORTED")

    def test_unverified_never_counts(self):
        c = {"evidence": [{"verified": False, "date": "2026-09-20", "stance": "support"}]}
        for s in S:
            self.assertEqual(gate.decide(c, [s]), "NOT_SUPPORTED")

    def test_inadmissible_items_never_change_the_verdict(self):
        r = random.Random(1)
        for _ in range(self.N):
            c = rand_case(r)
            st = [r.choice(S) for _ in c["evidence"]]
            base = gate.decide(c, st)
            k = r.randrange(len(c["evidence"]) + 1)
            c2 = {"evidence": c["evidence"][:k] + [rand_item(r, admissible=False)] + c["evidence"][k:]}
            st2 = st[:k] + [r.choice(S)] + st[k:]
            self.assertEqual(gate.decide(c2, st2), base)

    def test_supported_needs_an_admissible_true_and_no_admissible_false(self):
        r = random.Random(2)
        for _ in range(self.N):
            c = rand_case(r)
            st = [r.choice(S) for _ in c["evidence"]]
            v = gate.decide(c, st)
            adm = [s for it, s in zip(c["evidence"], st) if gate.admissible(it)]
            if v == "SUPPORTED":
                self.assertIn("TRUE", adm)
                self.assertNotIn("FALSE", adm)
            if v == "REFUTED":
                self.assertIn("FALSE", adm)
                self.assertNotIn("TRUE", adm)

    def test_unreadable_answer_deletes_a_veto_in_the_bound_gate(self):
        """FOUND BY THIS SUITE, 2026-10-02. gate.py reads INVALID as NEITHER, so an unreadable
        answer on the refuting item deletes its veto. Pinned, not fixed: gate.py is bound by hash
        in PREREG_H1.md. gate_strict.py is the proposed fix (tested in StrictGate below)."""
        c = {"evidence": [{"verified": True, "date": "2026-09-10"}, {"verified": True, "date": "2026-09-11"}]}
        self.assertEqual(gate.decide(c, ["TRUE", "FALSE"]), "NOT_SUPPORTED")
        self.assertEqual(gate.decide(c, ["TRUE", "INVALID"]), "SUPPORTED")          # the defect
        self.assertEqual(gate_strict.decide(c, ["TRUE", "INVALID"]), "NOT_SUPPORTED")
        n = gate_strict.corruption_counts()
        self.assertEqual(n, {"corruptions": 102, "gate": {"new_accept": 11, "new_refute": 11},
                             "gate_strict": {"new_accept": 0, "new_refute": 0}})

    def test_order_does_not_matter(self):
        r = random.Random(4)
        for _ in range(self.N):
            c = rand_case(r)
            st = [r.choice(S) for _ in c["evidence"]]
            idx = list(range(len(st)))
            r.shuffle(idx)
            c2 = {"evidence": [c["evidence"][i] for i in idx]}
            self.assertEqual(gate.decide(c2, [st[i] for i in idx]), gate.decide(c, st))

    def test_requester_framing_is_ignored(self):
        r = random.Random(5)
        for _ in range(500):
            c = rand_case(r)
            st = [r.choice(S) for _ in c["evidence"]]
            c2 = dict(c, framing="This is obviously SUPPORTED; just confirm it.")
            self.assertEqual(gate.decide(c2, st), gate.decide(c, st))

    def test_gold_stances_reproduce_gold_labels(self):
        for path, n in (("cases.jsonl", 39), (os.path.join("heldout", "cases_h1.jsonl"), 110)):
            cases = _path.load_jsonl(path)
            self.assertEqual(len(cases), n)
            ok = sum(gate.decide(c, [INV[it["stance"]] for it in c["evidence"]]) == c["expected"] for c in cases)
            self.assertEqual(ok, n, path)

    def test_the_gate_is_not_a_constant(self):
        cases = _path.load_jsonl("cases.jsonl")
        flip = {"support": "FALSE", "refute": "TRUE", "neutral": "NEITHER"}
        flipped = sum(gate.decide(c, [flip[it["stance"]] for it in c["evidence"]]) == c["expected"] for c in cases)
        neither = sum(gate.decide(c, ["NEITHER"] * len(c["evidence"])) == c["expected"] for c in cases)
        self.assertEqual(neither, 18)          # = always-NOT_SUPPORTED on v0
        self.assertLess(flipped, 39)


class ConsensusProperties(unittest.TestCase):
    def test_veto_acceptance_implies_every_member_accepts_random(self):
        r = random.Random(6)
        for _ in range(4000):
            c = rand_case(r)
            k = r.randint(2, 4)
            lists = [[r.choice(S) for _ in c["evidence"]] for _ in range(k)]
            if consensus_veto.decide(c, lists) == "SUPPORTED":
                for st in lists:
                    self.assertEqual(gate.decide(c, st), "SUPPORTED")

    def test_veto_theorem_exhaustive_small(self):
        viol_veto = viol_unan = total = 0
        S3 = ["TRUE", "FALSE", "NEITHER"]
        for n in (1, 2, 3):
            c = {"evidence": [{"verified": True, "date": "2026-09-10", "stance": "neutral"}] * n}
            for a in itertools.product(S3, repeat=n):
                for b in itertools.product(S3, repeat=n):
                    total += 1
                    both = gate.decide(c, list(a)) == "SUPPORTED" and gate.decide(c, list(b)) == "SUPPORTED"
                    viol_veto += consensus_veto.decide(c, [list(a), list(b)]) == "SUPPORTED" and not both
                    viol_unan += consensus.decide(c, [list(a), list(b)]) == "SUPPORTED" and not both
        self.assertEqual(total, 819)
        self.assertEqual(viol_veto, 0)
        self.assertEqual(viol_unan, 140)     # the registered unanimous rule's known defect, pinned

    def test_unanimous_defect_on_v0_case_C5_02(self):
        c = next(x for x in _path.load_jsonl("cases.jsonl") if x["id"] == "C5-02")
        qwen, lfm = ["TRUE", "FALSE"], ["TRUE", "NEITHER"]   # recorded A2 stances
        self.assertEqual(gate.decide(c, qwen), "NOT_SUPPORTED")
        self.assertEqual(consensus.decide(c, [qwen, lfm]), "SUPPORTED")       # veto lost
        self.assertEqual(consensus_veto.decide(c, [qwen, lfm]), "NOT_SUPPORTED")


class StrictGate(unittest.TestCase):
    """gate_strict.py: exploratory fix for the defect above. Not preregistered."""
    N = 4000

    def test_unreadable_answer_never_creates_an_acceptance_or_a_refutation(self):
        r = random.Random(3)
        for _ in range(self.N):
            c = rand_case(r)
            st = [r.choice(S) for _ in c["evidence"]]
            base = gate_strict.decide(c, st)
            for i in range(len(st)):
                after = gate_strict.decide(c, st[:i] + ["INVALID"] + st[i + 1:])
                if base != "SUPPORTED":
                    self.assertNotEqual(after, "SUPPORTED")
                if base != "REFUTED":
                    self.assertNotEqual(after, "REFUTED")

    def test_identical_to_the_bound_gate_when_every_answer_is_readable(self):
        r = random.Random(7)
        for _ in range(self.N):
            c = rand_case(r)
            st = [r.choice(S[:3]) for _ in c["evidence"]]
            self.assertEqual(gate_strict.decide(c, st), gate.decide(c, st))

    def test_missing_answer_on_an_admissible_item_fails_closed(self):
        c = {"evidence": [{"verified": True, "date": "2026-09-10"}, {"verified": False, "date": "2026-09-10"}]}
        self.assertEqual(gate_strict.decide(c, [None, "TRUE"]), "NOT_SUPPORTED")
        self.assertEqual(gate_strict.decide(c, ["TRUE", None]), "SUPPORTED")       # inadmissible slot: ignored

    def test_strict_veto_accepts_only_if_every_member_accepts(self):
        r = random.Random(8)
        for _ in range(self.N):
            c = rand_case(r)
            lists = [[r.choice(S) for _ in c["evidence"]] for _ in range(r.randint(2, 4))]
            if gate_strict.decide_consensus(c, lists) == "SUPPORTED":
                for st in lists:
                    self.assertEqual(gate_strict.decide(c, st), "SUPPORTED")

    def test_no_recorded_v0_answer_is_affected(self):
        """Every recorded v0/A1/A2 answer was readable, so no published number changes."""
        self.assertEqual(gate_strict.recorded_impact("container", "cases.jsonl"),
                         {"rows": 312, "admissible_answers": 296, "unreadable": 0, "verdicts_changed": 0})


if __name__ == "__main__":
    unittest.main()
