"""The answer key and the case sets. Is the oracle right? Is the held-out set exactly what
the preregistration bound? Can the label audit actually catch a wrong label?"""
import _path
import copy, json, os, unittest
from collections import Counter
import label_audit, oracle, simulate_cases, taxonomy

V0 = _path.load_jsonl("cases.jsonl")
H1 = _path.load_jsonl("heldout", "cases_h1.jsonl")
WRONG = {"support": ("refute", "neutral"), "refute": ("support", "neutral"), "neutral": ("support", "refute")}


class Oracle(unittest.TestCase):
    def test_oracle_reproduces_every_label(self):
        for name, cases, n in (("v0", V0, 39), ("H1", H1, 110)):
            self.assertEqual(len(cases), n)
            for c in cases:
                self.assertEqual(oracle.oracle(c), c["expected"], (name, c["id"]))

    def test_h1_label_mix(self):
        self.assertEqual(Counter(c["expected"] for c in H1), {"SUPPORTED": 27, "REFUTED": 36, "NOT_SUPPORTED": 47})
        self.assertEqual(Counter(c["category"] for c in H1), {k: 10 for k in simulate_cases.PLAN})

    def test_pushes_always_point_at_a_wrong_answer(self):
        """An injection or requester push toward the right answer would test nothing."""
        for c in H1:
            if c["category"] == "injection":
                self.assertNotEqual(c["expected"], c["injected_label"], c["id"])
            if c["category"] == "asserted_conclusion":
                self.assertNotEqual(c["expected"], c["pushed_label"], c["id"])
                self.assertTrue(c["framing"], c["id"])

    def test_framing_never_changes_the_answer_key(self):
        for c in V0 + H1:
            self.assertEqual(oracle.oracle(dict(c, framing="")), c["expected"], c["id"])


class LabelAudit(unittest.TestCase):
    def test_every_item_is_rederived_from_its_text(self):
        rows, bad, unparsed = label_audit.audit(H1)
        self.assertEqual(len(rows), 132)
        self.assertEqual(Counter(r[4] for r in rows), {"FULL": 125, "PREDICATE": 7})
        self.assertEqual((bad, unparsed), ([], []))

    def test_every_single_label_flip_is_caught(self):
        """Anti-vacuity: an audit that cannot fail is a log line. Each item's hidden label is
        corrupted to each of the two wrong values, one at a time; all 264 must be reported."""
        caught = total = 0
        for c in H1:
            for i, it in enumerate(c["evidence"]):
                for wrong in WRONG[it["stance"]]:
                    bad_case = copy.deepcopy(c)
                    bad_case["evidence"][i]["stance"] = wrong
                    total += 1
                    _, bad, _ = label_audit.audit([bad_case])
                    caught += any(b[1] == i for b in bad)
        self.assertEqual((caught, total), (264, 264))


class Generator(unittest.TestCase):
    def test_regenerates_the_bound_file_byte_for_byte(self):
        text = "".join(json.dumps(c, ensure_ascii=False, sort_keys=True) + "\n"
                       for c in simulate_cases.generate(20261002, 10))
        with open(os.path.join(_path.BENCH, "heldout", "cases_h1.jsonl"), encoding="utf-8") as fh:
            self.assertEqual(text, fh.read())

    def test_a_different_seed_gives_different_cases(self):
        a = [c["proposition"] for c in simulate_cases.generate(20261002, 10)]
        b = [c["proposition"] for c in simulate_cases.generate(7, 10)]
        self.assertNotEqual(a, b)

    def test_manifest_matches_the_case_file(self):
        with open(os.path.join(_path.BENCH, "heldout", "MANIFEST_H1.json")) as fh:
            m = json.load(fh)
        self.assertEqual(m["case_set_digest"], taxonomy.case_set_digest(H1))
        self.assertEqual(m["categories"], dict(Counter(c["category"] for c in H1)))

    def test_held_out_text_never_appears_in_v0(self):
        seen = {c["proposition"] for c in V0} | {it["text"] for c in V0 for it in c["evidence"]}
        for c in H1:
            self.assertNotIn(c["proposition"], seen, c["id"])
            for it in c["evidence"]:
                self.assertNotIn(it["text"], seen, c["id"])


if __name__ == "__main__":
    unittest.main()
