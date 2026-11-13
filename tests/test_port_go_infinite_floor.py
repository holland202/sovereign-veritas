"""OVF-1 (Go): the Go port must print an infinite quality floor as `inf`, as the kernel does (docs/OVF1_GO_PREREG.md).

Uses the binary in SVGATE_GO_BIN if set (the port-go CI job sets it, so a missing binary fails there), else builds
ports/go with `go` if it is installed, else skips.
"""
import copy
import importlib.util
import json
import os
import pathlib
import shutil
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("gate_contract", ROOT / "tools" / "gate_contract.py")
gct = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gct)


@pytest.fixture(scope="module")
def go_bin(tmp_path_factory):
    env = os.environ.get("SVGATE_GO_BIN")
    if env:
        path = pathlib.Path(env).resolve()
        assert path.is_file(), f"SVGATE_GO_BIN={env} does not exist"
        return str(path)
    if shutil.which("go") is None:
        pytest.skip("go not installed and SVGATE_GO_BIN not set")
    out = tmp_path_factory.mktemp("go") / "svgate"
    subprocess.run(["go", "build", "-o", str(out), "."], cwd=ROOT / "ports" / "go", check=True)
    return str(out)


def base_input(floor):
    for v in gct.read_vectors():
        if v["expect"]["decision"] == "ALLOW":
            inp = copy.deepcopy(v["input"])
            inp["record"]["evidence_quality"] = 0.2
            inp["capability"]["min_evidence_quality"] = floor
            return inp
    raise AssertionError("no ALLOW vector")


def go_decide(binary, floor):
    line = gct.canon({"id": "probe", "input": base_input(floor)}) + "\n"
    p = subprocess.run([binary], input=line, capture_output=True, text=True, timeout=60, check=True)
    o = json.loads(p.stdout)
    return o["decision"], o["reasons"]


@pytest.mark.parametrize("floor", [10 ** 400, 2 ** 1024], ids=["10**400", "2**1024"])
def test_infinite_floor_prints_inf_like_the_kernel(go_bin, floor):
    expected = gct.kernel_gate()(base_input(floor))
    assert expected == ("DEFER", ["evidence_quality_below_threshold:0.2000<inf"])
    assert go_decide(go_bin, floor) == expected


def test_negative_infinite_floor_adds_no_reason(go_bin):
    assert go_decide(go_bin, -(10 ** 400)) == ("ALLOW", [])
