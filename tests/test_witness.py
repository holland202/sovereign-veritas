"""Freshness witness v0. Registered W0-W6 in docs/EVIDENCE_PACKAGE.md before this code ran."""
import pathlib
import subprocess
import sys

import pytest

from sovereign_veritas.evidence import canonical_json
from test_package import make, roundtrip, reseal
from test_signature import allowed, keygen, needs_ssh, sign

ROOT = pathlib.Path(__file__).resolve().parents[1]
VERIFY = ROOT / "tools" / "verify_package.py"
WITNESS = ROOT / "tools" / "witness.py"


def write(tmp, name, pkg):
    p = tmp / name
    p.write_text(canonical_json(pkg), encoding="utf-8")
    return p


def append(pkg_path, log):
    return subprocess.run([sys.executable, str(WITNESS), "append", str(pkg_path), "--log", str(log)],
                          capture_output=True, text=True)


def verify(pkg_path, *extra):
    p = subprocess.run([sys.executable, str(VERIFY), str(pkg_path), *map(str, extra)],
                       capture_output=True, text=True)
    return p.returncode, p.stdout


@pytest.fixture
def two(tmp_path):
    a = write(tmp_path, "a.json", make({"thermal": "normal"}))
    b = write(tmp_path, "b.json", make({"thermal": "hot"}))
    return tmp_path, a, b, tmp_path / "packages.log"


def test_w0_last_entry_is_latest(two):
    _, a, _, log = two
    assert append(a, log).returncode == 0
    rc, out = verify(a, "--witness-log", log)
    assert rc == 0 and "freshness=LATEST_WITNESSED(1)" in out


def test_w1_earlier_entry_becomes_stale(two):
    _, a, b, log = two
    assert append(a, log).returncode == 0 and append(b, log).returncode == 0
    rc, out = verify(a, "--witness-log", log)
    assert rc == 1 and "STALE" in out and "1 newer package(s)" in out
    assert verify(b, "--witness-log", log)[0] == 0


def test_w2_absent_package_is_not_witnessed(two):
    _, a, b, log = two
    append(a, log)
    rc, out = verify(b, "--witness-log", log)
    assert rc == 1 and "freshness=NOT_WITNESSED" in out


@pytest.mark.parametrize("body", [
    "1 " + "a" * 64 + "\n1 " + "b" * 64 + "\n",   # seq not increasing
    "1 " + "a" * 64 + "\n2 " + "a" * 64 + "\n",   # duplicate digest
    "1 " + "g" * 64 + "\n",                        # not hex
    "2 " + "a" * 64 + "\n",                        # does not start at 1
])
def test_w3_malformed_log_is_could_not_look(two, body):
    _, a, _, log = two
    log.write_text("# sv witness log v0\n" + body)
    rc, out = verify(a, "--witness-log", log)
    assert rc == 2 and "COULD NOT LOOK" in out


def test_w3_missing_header_is_could_not_look(two):
    _, a, _, log = two
    log.write_text("1 " + "a" * 64 + "\n")
    assert verify(a, "--witness-log", log)[0] == 2


def test_w4_without_witness_unchanged(two):
    _, a, _, _ = two
    rc, out = verify(a)
    assert rc == 0 and "freshness=NOT_PROVEN" in out


def test_w5_append_refuses_inconsistent_and_duplicate(two):
    tmp, a, _, log = two
    assert append(a, log).returncode == 0
    dup = append(a, log)
    assert dup.returncode == 1 and "already witnessed" in dup.stdout
    bad = roundtrip(make())
    bad["decision"]["decision"] = "REFUSE"  # inconsistent with its own inputs
    refused = append(write(tmp, "bad.json", reseal(bad)), log)
    assert refused.returncode == 1 and "does not verify" in refused.stdout
    assert log.read_text().count("\n") == 2  # header + one entry


@needs_ssh
def test_w6_rolled_back_signed_package_is_stale(two):
    tmp, a, b, log = two
    key = keygen(tmp, "chad")
    signers = allowed(tmp, [("chad", key, "sv-package")])
    sig_a = sign(key, a)
    append(a, log)
    append(b, log)  # a newer package is witnessed; then someone restores the old one
    rc, out = verify(a, "--signature", sig_a, "--allowed-signers", signers, "--identity", "chad",
                     "--witness-log", log)
    assert rc == 1 and "PASS  signature" in out and "FAIL  freshness_witness" in out and "STALE" in out


def test_committed_log_path_is_not_git_ignored():
    """The first real witness entry never reached GitHub: a *.log rule in .gitignore hid it."""
    if not (ROOT / ".git").exists():
        pytest.skip("not a git checkout")
    p = subprocess.run(["git", "check-ignore", "-q", "witness/packages.log"], cwd=ROOT)
    assert p.returncode == 1  # 1 = not ignored


def test_append_refuses_a_git_ignored_log(two):
    tmp, a, _, _ = two
    subprocess.run(["git", "init", "-q", str(tmp)], check=True)
    (tmp / ".gitignore").write_text("*.log\n")
    r = append(a, tmp / "ignored.log")
    assert r.returncode == 1 and "git ignores" in r.stdout
    assert not (tmp / "ignored.log").exists()
