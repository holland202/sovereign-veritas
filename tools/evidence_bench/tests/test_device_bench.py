"""device_bench.py (instrument for H1-P10), tested without a phone: a fake llama-bench."""
import _path
import contextlib, io, os, shutil, sys, tempfile, unittest
import device_bench as db

FAKE_OK = r'''#!/usr/bin/env python3
import json, sys
a = sys.argv
pp, tg = int(a[a.index("-p") + 1]), int(a[a.index("-n") + 1])
print(json.dumps([{"n_prompt": pp, "n_gen": 0, "avg_ts": 50.0, "build_commit": "fake", "n_threads": 4},
                  {"n_prompt": 0, "n_gen": tg, "avg_ts": 8.0, "build_commit": "fake", "n_threads": 4}]))
'''
FAKE_FAIL = "#!/bin/sh\necho boom >&2\nexit 3\n"


class DeviceBench(unittest.TestCase):
    def fake(self, body):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        p = os.path.join(d, "llama-bench")
        with open(p, "w") as fh:
            fh.write(body)
        os.chmod(p, 0o755)
        return p

    def test_selftest_passes(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(db.selftest(), 0)

    def test_the_bar_is_inclusive(self):
        at = [{"t": t, "tg_tps": 10.0 if t <= 300 else 7.0} for t in range(0, 1201, 30)]
        under = [{"t": t, "tg_tps": 10.0 if t <= 300 else 6.99} for t in range(0, 1201, 30)]
        self.assertEqual(db.verdict(at)["status"], "CONFIRMED")
        self.assertEqual(db.verdict(under)["status"], "REFUTED")

    def test_run_once_reads_llama_bench_json(self):
        r = db.run_once(self.fake(FAKE_OK), "m.gguf", 512, 128, 0)
        self.assertEqual((r["pp_tps"], r["tg_tps"], r["build_commit"]), (50.0, 8.0, "fake"))

    def test_a_failing_instrument_raises(self):
        with self.assertRaises(RuntimeError):
            db.run_once(self.fake(FAKE_FAIL), "m.gguf", 512, 128, 0)

    def test_a_short_run_end_to_end_gives_no_verdict(self):
        """About a second of fake data: rows reach disk as they happen, exit code 2 (INSUFFICIENT)."""
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        model = os.path.join(d, "fake-model.gguf")
        open(model, "w").close()
        label = f"_test_{os.getpid()}"
        self.addCleanup(shutil.rmtree, os.path.join(_path.BENCH, "results", label), True)
        argv = sys.argv
        sys.argv = ["device_bench.py", "--model", model, "--minutes", "0.02", "--bench-bin", self.fake(FAKE_OK), "--label", label]
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                rc = db.main()
        finally:
            sys.argv = argv
        self.assertEqual(rc, 2)
        rows = _path.load_jsonl("results", label, "device_bench_fake-model.jsonl")
        self.assertGreaterEqual(len(rows), 1)
        self.assertEqual({r["tg_tps"] for r in rows}, {8.0})


if __name__ == "__main__":
    unittest.main()
