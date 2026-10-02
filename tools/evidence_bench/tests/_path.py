"""Shared by every test module: puts the bench directory on sys.path. Run the suite with
    python -m unittest discover -s tests -v      (from the evidence_bench directory)"""
import json, os, sys
BENCH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BENCH not in sys.path:
    sys.path.insert(0, BENCH)


def load_jsonl(*parts):
    with open(os.path.join(BENCH, *parts)) as fh:
        return [json.loads(line) for line in fh]
