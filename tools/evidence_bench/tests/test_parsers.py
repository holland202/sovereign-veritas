"""Hardened parsers fail closed; legacy parsers reproduce every recorded output."""
import _path  # noqa: F401
import glob, json, os, unittest
from parsing import parse, parse_stance, parse_legacy, parse_stance_legacy

BENCH = _path.BENCH


class FailClosed(unittest.TestCase):
    VERDICTS = {"SUPPORTED": "SUPPORTED", "Supported.": "SUPPORTED", "**SUPPORTED**": "SUPPORTED",
                "REFUTED": "REFUTED", "The verdict is REFUTED.": "REFUTED",
                "NOT_SUPPORTED": "NOT_SUPPORTED", "Not supported": "NOT_SUPPORTED", "not-supported": "NOT_SUPPORTED",
                "UNSUPPORTED": "INVALID", "Unsupported.": "INVALID", "NOT REFUTED": "INVALID", "UNREFUTED": "INVALID",
                "It is not REFUTED": "INVALID", "NEVER SUPPORTED": "INVALID",
                "SUPPORTED or REFUTED": "INVALID", "": "INVALID"}
    STANCES = {"TRUE": "TRUE", "True.": "TRUE", "**FALSE**": "FALSE", "NEITHER": "NEITHER",
               "UNTRUE": "INVALID", "NOT TRUE": "INVALID", "Not true.": "INVALID", "It is not false": "INVALID",
               "NEITHER TRUE NOR FALSE": "INVALID", "TRUE or FALSE": "INVALID", "": "INVALID"}

    def test_verdict_table(self):
        for text, want in self.VERDICTS.items():
            self.assertEqual(parse(text), want, text)

    def test_stance_table(self):
        for text, want in self.STANCES.items():
            self.assertEqual(parse_stance(text), want, text)

    def test_a3_vocabulary(self):
        for text, want in {"CONFIRMS": "TRUE", "Contradicts.": "FALSE", "NEITHER": "NEITHER",
                           "does not confirm": "INVALID", "CONFIRMS or CONTRADICTS": "INVALID", "TRUE": "INVALID"}.items():
            self.assertEqual(parse_stance(text, "a3"), want, text)

    def test_affixed_or_negated_labels_never_accept(self):
        for pre in ("UN", "NON", "NOT ", "NO ", "NEVER ", "ISN'T ", "DOESN'T "):
            self.assertNotEqual(parse(pre + "SUPPORTED"), "SUPPORTED", pre)
            self.assertNotEqual(parse_stance(pre + "TRUE"), "TRUE", pre)
            self.assertNotEqual(parse_stance(pre + "CONFIRMS", "a3"), "TRUE", pre)

    def test_legacy_defect_is_documented(self):
        # the reason parsing.py exists; if this ever fails, the legacy reproduction is wrong
        self.assertEqual(parse_legacy("UNSUPPORTED"), "SUPPORTED")
        self.assertEqual(parse_stance_legacy("UNTRUE"), "TRUE")


def jsonl(f):
    with open(f) as fh:
        return [json.loads(l) for l in fh]


class RecordedOutputs(unittest.TestCase):
    def test_hardened_equals_legacy_on_every_recorded_v0_a1_a2_output(self):
        n = 0
        for f in sorted(glob.glob(os.path.join(BENCH, "results", "container", "*.jsonl"))):
            for r in jsonl(f):
                n += 1
                self.assertEqual(parse(r["raw"]), r["pred"], (f, r["id"]))
                self.assertEqual(parse_legacy(r["raw"]), r["pred"], (f, r["id"]))
        for f in sorted(glob.glob(os.path.join(BENCH, "results", "container", "decomposed", "*.jsonl"))):
            for r in jsonl(f):
                for raw, st in zip(r["raw"], r["stances"]):
                    if raw is None:
                        continue
                    n += 1
                    self.assertEqual(parse_stance(raw), st, (f, r["id"]))
                    self.assertEqual(parse_stance_legacy(raw), st, (f, r["id"]))
        # denominator pinned: 312 direct rows + 296 item outputs. An empty results dir must fail, not pass.
        self.assertEqual(n, 608)

    def test_later_runs_reparse_identically(self):
        """Any run made with the hardened parser (H1, S25) must re-parse to its recorded value."""
        for f in glob.glob(os.path.join(BENCH, "results", "*_h1", "*.jsonl")):
            for r in jsonl(f):
                self.assertEqual(parse(r["raw"]), r["pred"], (f, r["id"]))
        for sub, vocab in (("decomposed", "a2"), ("decomposed_a3", "a3")):
            for f in glob.glob(os.path.join(BENCH, "results", "*_h1", sub, "*.jsonl")):
                for r in jsonl(f):
                    for raw, st in zip(r["raw"], r["stances"]):
                        if raw is not None:
                            self.assertEqual(parse_stance(raw, vocab), st, (f, r["id"]))


if __name__ == "__main__":
    unittest.main()
