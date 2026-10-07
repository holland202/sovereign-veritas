"""Metamorphic relations for the verifier and the consumer.

A rewrite that keeps a package's meaning (formatting, key order, unicode escaping, surrounding whitespace) must not change
the verdict. It must change the signature check, because a signature binds bytes, not meaning. It must not let the
consumer act twice on the same package. The negative control is a rewrite that changes meaning, which must change the
verdict; without it, "same verdict" could mean "the comparison sees nothing".
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from test_package import vp

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "runs" / "vehicle_sitl_v13" / "sv_package_a911244dfcf7.json"
VERIFY, CONSUMER = ROOT / "tools" / "verify_package.py", ROOT / "tools" / "consumer.py"
needs_ssh = pytest.mark.skipif(shutil.which("ssh-keygen") is None, reason="ssh-keygen not installed")


def _reversed_keys(v):
    if isinstance(v, dict):
        return {k: _reversed_keys(v[k]) for k in reversed(list(v))}
    if isinstance(v, list):
        return [_reversed_keys(x) for x in v]
    return v


TRANSFORMS = {
    "pretty": lambda o: json.dumps(o, indent=2, ensure_ascii=False) + "\n",
    "key_order": lambda o: json.dumps(_reversed_keys(o), ensure_ascii=False),
    "ascii_escaped": lambda o: json.dumps(o, ensure_ascii=True),
    "whitespace": lambda o: "\n\t " + vp.canon(o) + " \n\n",
}


@pytest.fixture
def base(tmp_path):
    """The stored package with a non-ASCII artifact name (no check binds it), resealed, so unicode escaping matters."""
    pkg = json.loads(BASE.read_text(encoding="utf-8"))
    pkg["artifact"]["name"] = "Ωmega-ü-字"
    pkg["package_sha256"] = vp.sha(vp.canon({k: v for k, v in pkg.items() if k != "package_sha256"}))
    path = tmp_path / "base.json"
    path.write_text(vp.canon(pkg), encoding="utf-8")
    return pkg, path


def verify(path, *extra):
    p = subprocess.run([sys.executable, str(VERIFY), str(path), *extra], capture_output=True, text=True)
    checks = sorted((l[6:].split()[0], l[:4]) for l in p.stdout.splitlines() if l[:4] in ("PASS", "FAIL"))
    verdict = next((l for l in p.stdout.splitlines() if l.startswith("VERDICT")), p.stdout)
    return p.returncode, verdict, checks


def test_the_base_package_verifies(base):
    rc, verdict, _ = verify(base[1])
    assert rc == 0 and "CONSISTENT" in verdict, verdict


@pytest.mark.parametrize("name", sorted(TRANSFORMS))
def test_a_meaning_preserving_rewrite_keeps_the_verdict(base, tmp_path, name):
    pkg, path = base
    out = tmp_path / f"{name}.json"
    out.write_text(TRANSFORMS[name](pkg), encoding="utf-8")
    assert out.read_bytes() != path.read_bytes()
    assert verify(out) == verify(path)


def test_negative_control_a_meaning_changing_rewrite_changes_the_verdict(base, tmp_path):
    pkg, path = base
    bad = json.loads(json.dumps(pkg))
    bad["decision"]["decision"] = "ALLOW" if pkg["decision"]["decision"] != "ALLOW" else "REFUSE"
    out = tmp_path / "bad.json"
    out.write_text(json.dumps(bad, indent=2), encoding="utf-8")
    assert verify(out) != verify(path)


@needs_ssh
@pytest.mark.parametrize("name", sorted(TRANSFORMS))
def test_a_signature_binds_bytes_not_meaning(base, tmp_path, name):
    pkg, path = base
    key = tmp_path / "k"
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "holland202", "-f", str(key)], check=True)
    signers = tmp_path / "signers"
    signers.write_text("holland202 namespaces=\"sv-package\" " + " ".join(Path(str(key) + ".pub").read_text().split()[:2]) + "\n")
    subprocess.run(["ssh-keygen", "-Y", "sign", "-f", str(key), "-n", "sv-package", str(path)], check=True, capture_output=True)
    args = ["--signature", str(path) + ".sig", "--allowed-signers", str(signers), "--identity", "holland202"]
    rc, verdict, _ = verify(path, *args)
    assert rc == 0 and verdict.endswith("authenticity=SIGNED:holland202"), verdict
    out = tmp_path / f"{name}.json"
    out.write_text(TRANSFORMS[name](pkg), encoding="utf-8")
    rc, verdict, checks = verify(out, *args)
    assert rc == 1 and verdict.endswith("authenticity=NOT_PROVEN") and ("signature", "FAIL") in checks
    assert [c for c in checks if c[0] != "signature"] == [c for c in verify(path)[2]]  # consistency is unaffected


@pytest.mark.parametrize("name", sorted(TRANSFORMS))
def test_the_consumer_does_not_act_twice_on_a_rewritten_copy(base, tmp_path, name):
    pkg, path = base
    log, state = tmp_path / "w.log", tmp_path / "s.json"
    log.write_text(f"# sv witness log v0\n1 {pkg['package_sha256']}\n", encoding="utf-8", newline="\n")
    first = subprocess.run([sys.executable, str(CONSUMER), "accept", str(path), "--witness-log", str(log),
                            "--state", str(state)], capture_output=True, text=True)
    assert first.returncode == 0 and "CONSUMER  ACCEPTED" in first.stdout, first.stdout
    out = tmp_path / f"{name}.json"
    out.write_text(TRANSFORMS[name](pkg), encoding="utf-8")
    again = subprocess.run([sys.executable, str(CONSUMER), "accept", str(out), "--witness-log", str(log),
                            "--state", str(state)], capture_output=True, text=True)
    assert again.returncode == 1 and "already acted on this package (replay)" in again.stdout, again.stdout
