"""Recovery: damaged or half-written packages are never accepted, and a rerun recovers.

Registered before this code ran: docs/EVIDENCE_PACKAGE.md, "Recovery simulation" (R1-R5).
"""
import glob
import hashlib
import json
import os
import pathlib
import random
import subprocess
import sys

from sovereign_veritas.evidence import canonical_json
from sovereign_veritas.package import write_package
from test_package import make, thermal_fixture, vp

ROOT = pathlib.Path(__file__).resolve().parents[1]
VERIFY = ROOT / "tools" / "verify_package.py"

CHILD = r"""
import hashlib, json, os, sys
sys.path.insert(0, sys.argv[1])
from sovereign_veritas.evidence import canonical_json
from sovereign_veritas.package import write_package
pkg = json.load(open(sys.argv[2], encoding="utf-8"))
mode, out = sys.argv[3], sys.argv[4]
if mode == "legacy":  # the pre-fix writer: open the final path and write into it
    data = canonical_json(pkg).encode("utf-8")
    final = os.path.join(out, f"sv_package_{hashlib.md5(data).hexdigest()[:12]}.json")
    with open(final, "wb") as fh:
        fh.write(data[: len(data) // 2]); fh.flush(); os._exit(9)
elif mode == "mid_write":
    write_package(pkg, out, _after_first_half=lambda: os._exit(9))
elif mode == "before_rename":
    os.replace = lambda *a, **k: os._exit(9)
    write_package(pkg, out)
else:
    print(write_package(pkg, out))
"""


def accepted(data: bytes) -> bool:
    try:
        return all(ok for _, ok, _ in vp.verify(json.loads(data.decode("utf-8"))))
    except Exception:
        return False


def verify_exit(path):
    return subprocess.run([sys.executable, str(VERIFY), str(path)], capture_output=True).returncode


def child(tmp_path, mode, pkg):
    src = tmp_path / "src.json"
    src.write_text(canonical_json(pkg), encoding="utf-8")
    out = tmp_path / "out"
    out.mkdir(exist_ok=True)
    rc = subprocess.run([sys.executable, "-c", CHILD, str(ROOT), str(src), mode, str(out)],
                        capture_output=True, text=True).returncode
    finals = sorted(p for p in glob.glob(str(out / "sv_package_*.json")))
    temps = sorted(glob.glob(str(out / "*.tmp-*")))
    return rc, finals, temps


def test_r1_no_strict_prefix_is_accepted(tmp_path):
    data = canonical_json(make(thermal=thermal_fixture(tmp_path))).encode("utf-8")
    assert accepted(data)
    assert [k for k in range(len(data)) if accepted(data[:k])] == []


def test_r2_no_single_bit_flip_is_accepted(tmp_path):
    data = canonical_json(make(thermal=thermal_fixture(tmp_path))).encode("utf-8")
    rng = random.Random(7)
    hits = []
    for _ in range(500):
        b = bytearray(data)
        i = rng.randrange(len(b))
        b[i] ^= 1 << rng.randrange(8)
        if accepted(bytes(b)):
            hits.append(i)
    assert hits == []


def test_r3_legacy_writer_crash_leaves_a_torn_file_under_a_lying_name(tmp_path):
    rc, finals, _ = child(tmp_path, "legacy", make())
    assert rc == 9 and len(finals) == 1
    torn = pathlib.Path(finals[0])
    assert verify_exit(torn) == 2
    assert hashlib.md5(torn.read_bytes()).hexdigest()[:12] not in torn.name


def test_r4_atomic_writer_crash_leaves_nothing_final_and_a_rerun_recovers(tmp_path):
    pkg = make()
    for mode in ("mid_write", "before_rename"):
        rc, finals, temps = child(tmp_path, mode, pkg)
        assert (mode, rc, finals) == (mode, 9, []) and temps
    rc, finals, _ = child(tmp_path, "clean", pkg)
    assert rc == 0 and len(finals) == 1 and verify_exit(finals[0]) == 0


def test_r5_refuse_then_allow_both_verify(tmp_path):
    refused = write_package(make({"thermal": "unknown"}), str(tmp_path))
    allowed = write_package(make({"thermal": "normal"}), str(tmp_path))
    decisions = [json.loads(pathlib.Path(p).read_text(encoding="utf-8"))["decision"]["decision"]
                 for p in (refused, allowed)]
    assert decisions == ["REFUSE", "ALLOW"] and refused != allowed
    assert (verify_exit(refused), verify_exit(allowed)) == (0, 0)
