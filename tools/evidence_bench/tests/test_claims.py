"""verify_claims.py is the mechanical form of "numbers in prose must match code output".
It must pass on the real documents and fail when a single number is changed."""
import _path  # noqa: F401
import contextlib, io, unittest
import verify_claims as vc


class Claims(unittest.TestCase):
    def setUp(self):
        vc.FAILS.clear()
        vc.PASSES.clear()

    def run_with(self, doc=None, old=None, new=None):
        real = vc.read

        def tampered(p):
            s = real(p)
            if p == doc and s is not None:
                self.assertIn(old, s, "tamper target missing; the negative control would be vacuous")
                s = s.replace(old, new, 1)
            return s
        vc.read = tampered
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                return vc.main()
        finally:
            vc.read = real

    def test_every_published_number_matches_code_output(self):
        self.assertEqual(self.run_with(), 0, vc.FAILS)
        self.assertGreaterEqual(len(vc.PASSES), 36)

    def test_a_changed_prose_p_value_is_caught(self):
        self.assertEqual(self.run_with("STATS.md", "p = 0.727", "p = 0.721"), 1)
        self.assertTrue(any("4B unsafe McNemar" in f for f in vc.FAILS), vc.FAILS)

    def test_a_changed_historical_table_cell_is_caught(self):
        self.assertEqual(self.run_with("RESULTS_A1_A2.md", "| Qwen3.5-2B | decomposed | 0.7436 |",
                                       "| Qwen3.5-2B | decomposed | 0.7500 |"), 1)

    def test_a_changed_generated_block_is_caught(self):
        self.assertEqual(self.run_with("STATS.md", "<!-- BEGIN:container:main -->\n",
                                       "<!-- BEGIN:container:main -->\nedited by hand\n"), 1)


if __name__ == "__main__":
    unittest.main()
