"""Attacks that only one verifier guard stops.

Added 2026-09-26 because tools/verifier_mutants.py found two guards no test depended on:
switching off artifact_digest or provenance_chain left every test passing (docs/INTEGRATION.md, I1).
Each case below is caught by exactly one guard, so switching that guard off must fail this file.
"""
import base64
import copy

from test_package import ROUNDS, chain_hex, failed, make, reseal, roundtrip, vp


def test_artifact_bytes_swapped_under_the_old_digest():
    """Different bytes, the claimed sha256 kept, the measurement recomputed from the new bytes."""
    p = copy.deepcopy(roundtrip(make()))
    new = b"a different artifact entirely" * 8
    p["artifact"]["bytes_b64"] = base64.b64encode(new).decode("ascii")
    out = chain_hex(new, ROUNDS)
    p["measurement"]["output_sha256"] = out
    p["provenance"]["chain"][-1]["record"]["prediction"]["value"]["output_sha256"] = out
    assert failed(reseal(p)) == ["artifact_digest"]


def test_record_edited_and_only_the_package_digest_recomputed():
    p = copy.deepcopy(roundtrip(make()))
    p["provenance"]["chain"][0]["record"]["timestamp"] = "2020-01-01T00:00:00+00:00"
    p["package_sha256"] = vp.sha(vp.canon({k: v for k, v in p.items() if k != "package_sha256"}))
    assert failed(p) == ["provenance_chain"]


def test_duplicate_record_id_after_a_full_reseal():
    p = copy.deepcopy(roundtrip(make()))
    chain = p["provenance"]["chain"]
    chain[0]["record"]["record_id"] = chain[-1]["record"]["record_id"]
    assert failed(reseal(p)) == ["provenance_chain"]
