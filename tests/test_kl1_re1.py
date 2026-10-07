"""KL-1 / RE-1 fixes (docs/KL1_RE1_PREREG.md, docs/KL1_RE1_RESULTS.md): the depth scan stops early, MemoryError is
COULD NOT LOOK in the verifier and the consumer, and a signature that matched only an allowed-signers pattern says so.
Each test fails on the code at 9e52fa2 (the registration commit)."""
import importlib.util
import pathlib
import shutil
import subprocess
import sys

import pytest

from sovereign_veritas.evidence import canonical_json
from test_package import make, thermal_fixture, vp

ROOT = pathlib.Path(__file__).resolve().parents[1]
VERIFY = ROOT / "tools" / "verify_package.py"
needs_ssh = pytest.mark.skipif(shutil.which("ssh-keygen") is None, reason="ssh-keygen not installed")


# --- RE-P3: json_depth stops early -----------------------------------------------------------------------------------

def test_json_depth_stops_as_soon_as_the_limit_is_exceeded():
    assert vp.json_depth("[" * 1_000_000, vp.MAX_JSON_DEPTH) == vp.MAX_JSON_DEPTH + 1
    assert vp.json_depth('[[1, [2]], {"k": [3]}]', vp.MAX_JSON_DEPTH) == 3  # below the limit: the true depth
    assert vp.json_depth("[" * 1000) == 1000  # without stop_above: unchanged


def test_the_depth_refusal_is_unchanged():
    with pytest.raises(ValueError, match="exceeds the verifier limit"):
        vp.loads_bounded("[" * 100_000)


# --- RE-P2 / RE-P5: MemoryError is COULD NOT LOOK ----------------------------------------------------------------------

def test_verifier_reports_memory_exhaustion_as_could_not_look(tmp_path, monkeypatch, capsys):
    pkg = tmp_path / "p.json"
    pkg.write_text("{}", encoding="utf-8")

    def exhausted(text):
        raise MemoryError()
    monkeypatch.setattr(vp, "loads_bounded", exhausted)
    monkeypatch.setattr(sys, "argv", ["verify_package.py", str(pkg)])
    with pytest.raises(SystemExit) as e:
        vp.main()
    assert e.value.code == 2
    assert capsys.readouterr().out.startswith("COULD NOT LOOK: MemoryError")


def _consumer():
    spec = importlib.util.spec_from_file_location("consumer_under_test", ROOT / "tools" / "consumer.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_consumer_reports_memory_exhaustion_as_could_not_look_and_releases_its_lock(tmp_path, monkeypatch, capsys):
    consumer = _consumer()
    real = consumer.load_verifier()

    def exhausted(path):
        raise MemoryError()
    monkeypatch.setattr(real, "read_witness_log", exhausted)
    monkeypatch.setattr(consumer, "load_verifier", lambda: real)
    (tmp_path / "zones").mkdir()
    pkg = tmp_path / "p.json"
    pkg.write_text(canonical_json(make(thermal=thermal_fixture(tmp_path / "zones"))), encoding="utf-8")
    state = tmp_path / "state.json"
    argv = ["consumer.py", "accept", str(pkg), "--witness-log", str(tmp_path / "w.log"), "--state", str(state)]
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(SystemExit) as e:
        consumer.main()
    assert e.value.code == 2
    assert "COULD NOT LOOK: MemoryError" in capsys.readouterr().out
    assert not state.exists()
    lock = consumer._acquire_lock(str(state) + ".lock")  # released: a second consumer can take it at once
    consumer._release_lock(lock)


# --- KL-P5: how the identity matched -----------------------------------------------------------------------------------

def _keygen(d, name):
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", name, "-f", str(d / name)], check=True)
    return d / name


def _pub(key):
    return " ".join((key.parent / (key.name + ".pub")).read_text().split()[:2])


@pytest.fixture
def signed(tmp_path):
    key, other = _keygen(tmp_path, "signer"), _keygen(tmp_path, "other")
    (tmp_path / "zones").mkdir()
    pkg = tmp_path / "pkg.json"
    pkg.write_text(canonical_json(make(thermal=thermal_fixture(tmp_path / "zones"))), encoding="utf-8")
    subprocess.run(["ssh-keygen", "-Y", "sign", "-f", str(key), "-n", "sv-package", str(pkg)], check=True,
                   capture_output=True)
    return tmp_path, key, other, pkg, pathlib.Path(str(pkg) + ".sig")


def _listing(d, pkg, sig, lines):
    f = d / "allowed"
    f.write_text("".join(l + "\n" for l in lines))
    found = []
    ok, detail = vp.check_signature(pkg.read_bytes(), str(sig), str(f), "holland202", listing=found)
    return ok, detail, found


NS = 'namespaces="sv-package"'


@needs_ssh
@pytest.mark.parametrize("lines,expected", [
    (lambda k, o: [f"holland202 {NS} {_pub(k)}"], "literal"),
    (lambda k, o: [f"ops,holland202 {NS} {_pub(k)}"], "literal"),
    (lambda k, o: [f"* {NS} {_pub(k)}"], "*"),
    (lambda k, o: [f"h*202 {NS} {_pub(k)}"], "h*202"),
    (lambda k, o: [f"holland202 {NS} {_pub(o)}", f"* {NS} {_pub(k)}"], "*"),
    (lambda k, o: [f"* {NS} {_pub(k)}", f"holland202 {NS} {_pub(k)}"], "literal"),
    # listed by name only for another namespace, by pattern for this one (find-principals alone ignores namespaces)
    (lambda k, o: [f'holland202 namespaces="sv-other" {_pub(k)}', f"* {NS} {_pub(k)}"], "*"),
    # listed by name but expired, and by pattern without expiry: the name did not verify
    (lambda k, o: [f'holland202 {NS},valid-before="20200101" {_pub(k)}', f"* {NS} {_pub(k)}"], "*"),
])
def test_the_signature_listing_says_how_the_identity_matched(signed, lines, expected):
    """The namespace case is the one ssh-keygen -Y find-principals got wrong (it reported 'holland202', from the line valid
    only for sv-other): each line is now checked alone, with its own options."""
    d, key, other, pkg, sig = signed
    ok, detail, found = _listing(d, pkg, sig, lines(key, other))
    assert ok and found == [expected], (detail, found)
    assert ("pattern" in detail) == (expected != "literal")


@needs_ssh
@pytest.mark.parametrize("line,token", [
    ("holland202 {ns} {pub}", "authenticity=SIGNED:holland202"),
    ("* {ns} {pub}", "authenticity=SIGNED:holland202[pattern:*]"),
])
def test_the_verdict_names_the_pattern(signed, line, token):
    d, key, _, pkg, sig = signed
    f = d / "allowed"
    f.write_text(line.format(ns=NS, pub=_pub(key)) + "\n")
    p = subprocess.run([sys.executable, str(VERIFY), str(pkg), "--signature", str(sig), "--allowed-signers", str(f),
                        "--identity", "holland202"], capture_output=True, text=True)
    verdict = [l for l in p.stdout.splitlines() if l.startswith("VERDICT")][0]
    assert p.returncode == 0 and verdict.split()[-1] == token, p.stdout
