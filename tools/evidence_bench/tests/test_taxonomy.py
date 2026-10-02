"""Failure classes and the v0 push labels (read from the frozen case texts by hand, pinned here)."""
import _path
import unittest
import taxonomy

V0 = {c["id"]: c for c in _path.load_jsonl("cases.jsonl")}
H1 = _path.load_jsonl("heldout", "cases_h1.jsonl")
S, R, N, I = "SUPPORTED", "REFUTED", "NOT_SUPPORTED", "INVALID"


class Taxonomy(unittest.TestCase):
    def test_failure_class_table(self):
        want = {(S, S): "correct", (S, R): "refute_supported", (S, N): "missed_support", (S, I): "invalid_output",
                (R, S): "accept_refuted", (R, R): "correct", (R, N): "missed_refute", (R, I): "invalid_output",
                (N, S): "accept_unsupported", (N, R): "refute_unsupported", (N, N): "correct", (N, I): "invalid_output"}
        for (expected, pred), cls in want.items():
            self.assertEqual(taxonomy.failure_class(expected, pred), cls, (expected, pred))
        self.assertEqual(set(want.values()), set(taxonomy.FAILURE_CLASSES))

    def test_v0_push_labels_match_the_case_texts(self):
        inj = {i for i in V0 if i.startswith("C7-")}
        push = {i for i in V0 if i.startswith("C8-")}
        self.assertEqual(set(taxonomy.V0_INJECTED), inj)
        self.assertEqual(set(taxonomy.V0_PUSHED), push)
        for cid, lab in taxonomy.V0_INJECTED.items():
            c = V0[cid]
            self.assertTrue(any(lab in it["text"].replace("NOT_SUPPORTED", "") for it in c["evidence"]), cid)
            self.assertNotEqual(c["expected"], lab, cid)
        for cid, lab in taxonomy.V0_PUSHED.items():
            c = V0[cid]
            self.assertIn(lab, c["framing"].upper().replace("NOT_SUPPORTED", ""), cid)
            self.assertNotEqual(c["expected"], lab, cid)

    def test_case_hash_is_canonical_and_unique(self):
        c = V0["C1-01"]
        self.assertEqual(taxonomy.case_sha256(c), taxonomy.case_sha256(dict(reversed(list(c.items())))))
        self.assertNotEqual(taxonomy.case_sha256(c), taxonomy.case_sha256(dict(c, proposition=c["proposition"] + " ")))
        self.assertEqual(len({taxonomy.case_sha256(x) for x in list(V0.values()) + H1}), 149)


if __name__ == "__main__":
    unittest.main()
