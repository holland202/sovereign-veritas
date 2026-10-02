"""Frozen inputs stay frozen. The case files, the prompts and every file the H1
preregistration binds must hash to their registered values, and every run manifest must name
the inputs it used. A failure here means the protocol was broken; it is not a test to update.

Not part of mutate.py on purpose: editing gate.py breaks its hash, which would "kill" every
gate mutant for a reason that has nothing to do with behaviour."""
import _path
import glob, hashlib, json, os, re, unittest
import gate, prompt, run_decomposed

B = _path.BENCH
V0_CASES = "76714497fbd7c2fcf0307e49585b4ca304d38311675b754b9bdc1df2b8789e19"
H1_CASES = "f131b458a72ce1e7f14d52a0579d07cd6a07e152ed0b85971cfb236609c5c31c"
V0_PROMPT = "1bee4a93f184a478ee27b96e4373002073f5b0b585e8fbbac5e76d0a7aa550d7"
A2_PROMPT = "6c8e81e79b895070167362104d295bb780bad2af52def7060017ce62990cb1d6"
GATE = "831f99f84b177c555343cc82acb63ea545629620dc9fde5c7ccdbdfe0ac67fb9"


def sha(*p):
    with open(os.path.join(B, *p), "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def manifests(label, sub=""):
    out = []
    for f in sorted(glob.glob(os.path.join(B, "results", label, sub, "*.manifest.json"))):
        with open(f) as fh:
            out.append(json.load(fh))
    return out


class Frozen(unittest.TestCase):
    def test_case_files(self):
        self.assertEqual(sha("cases.jsonl"), V0_CASES)
        self.assertEqual(sha("heldout", "cases_h1.jsonl"), H1_CASES)

    def test_every_manifest_names_the_case_file_it_used(self):
        for sub in ("", "decomposed"):
            ms = manifests("container", sub)
            self.assertEqual(len(ms), 4)
            for m in ms:
                self.assertEqual(m["cases_sha256"], V0_CASES)
        for sub in ("", "decomposed", "decomposed_a3"):
            for m in manifests("container_h1", sub):
                self.assertEqual(m["cases_sha256"], H1_CASES)

    def test_prompt_hashes_recompute_from_source(self):
        cases = _path.load_jsonl("cases.jsonl")
        direct = hashlib.sha256((prompt.SYSTEM + "\n".join(prompt.render_user(c) for c in cases)).encode()).hexdigest()
        a2 = hashlib.sha256((run_decomposed.SYSTEM + "".join(
            run_decomposed.render(c["proposition"], it["text"]) for c in cases for it in c["evidence"]
            if gate.admissible(it))).encode()).hexdigest()
        self.assertEqual((direct, a2), (V0_PROMPT, A2_PROMPT))
        for m in manifests("container"):
            self.assertEqual(m["prompt_set_sha256"], V0_PROMPT)
        for m in manifests("container", "decomposed"):
            self.assertEqual(m["extract_prompt_set_sha256"], A2_PROMPT)

    def test_every_decomposed_run_used_the_registered_gate(self):
        self.assertEqual(sha("gate.py"), GATE)
        for label in ("container", "container_h1"):
            for sub in ("decomposed", "decomposed_a3"):
                for m in manifests(label, sub):
                    self.assertEqual(m["gate_sha256"], GATE)

    def test_files_bound_by_the_h1_preregistration(self):
        with open(os.path.join(B, "PREREG_H1.md")) as fh:
            bound = re.findall(r"^([0-9a-f]{64})  (\S+)$", fh.read(), re.M)
        self.assertEqual(len(bound), 15)
        for digest, path in bound:
            self.assertEqual(sha(path), digest, path)

    def test_sha256sums_matches_the_tree(self):
        with open(os.path.join(B, "SHA256SUMS")) as fh:
            lines = [l.split("  ", 1) for l in fh.read().splitlines() if l.strip()]
        self.assertGreater(len(lines), 30)
        for digest, path in lines:
            self.assertEqual(sha(path), digest, path)


if __name__ == "__main__":
    unittest.main()
