"""H1 scoring: the registered verdicts are pinned to the frozen raw rows, a partial run can
never be scored, and the one boundary verdict (H1-P5) is shown to depend on its boundary."""
import _path
import copy, os, unittest
import analyze, score_h1

RES = analyze.analyze("container_h1", os.path.join("heldout", "cases_h1.jsonl"))[0]
PINNED = {"H1-P1": "CONFIRMED", "H1-P2": "CONFIRMED", "H1-P3": "CONFIRMED", "H1-P4": "CONFIRMED",
          "H1-P5": "CONFIRMED", "H1-P6": "REFUTED", "H1-P7": "CONFIRMED", "H1-P8": "CONFIRMED",
          "H1-P9": "UNRUN", "H1-P10": "UNRUN", "H1-V1": "CONFIRMED", "H1-V2": "CONFIRMED",
          "H1-V3": "CONFIRMED", "V invariant": "HOLDS"}


class H1Scoring(unittest.TestCase):
    def test_registered_verdicts_from_the_frozen_rows(self):
        self.assertEqual({r["id"]: r["verdict"] for r in score_h1.evaluate(RES)}, PINNED)

    def test_a_partial_run_is_pending_never_scored(self):
        res = copy.deepcopy(RES)
        res["runs"][f"decomposed_a3/{score_h1.Q4}"]["n"] = 109
        v = {r["id"]: r["verdict"] for r in score_h1.evaluate(res)}
        self.assertEqual(v["H1-P7"], "PENDING")

    def test_p5_sits_on_its_boundary(self):
        """Lower Qwen2.5-1.5B's registered upper accuracy bound by one case and H1-P5 flips."""
        real = score_h1._sim
        def nudged():
            sim = copy.deepcopy(real())
            sim["Qwen2.5-1.5B"]["acc"]["p95"] = 68 / 110
            return sim
        score_h1._sim = nudged
        try:
            v = {r["id"]: r["verdict"] for r in score_h1.evaluate(RES)}
        finally:
            score_h1._sim = real
        self.assertEqual(v["H1-P5"], "REFUTED")

    def test_findings_text_is_generated_without_error(self):
        text = score_h1.findings()
        self.assertIn("H1-P6 REFUTED", text)
        self.assertIn("H1-CF-04, H1-CF-07, H1-CF-10", text)


if __name__ == "__main__":
    unittest.main()
