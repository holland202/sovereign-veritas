"""Package signatures (ssh-keygen -Y, ed25519). Registered S0-S4 in docs/EVIDENCE_PACKAGE.md.

Skips where ssh-keygen is absent - except S3, which checks that absence is reported, not passed.
"""
import os
import pathlib
import shutil
import subprocess
import sys

import pytest

from sovereign_veritas.evidence import canonical_json
from test_field_sweep import UNBOUND, fs
from test_package import make, thermal_fixture, vp

ROOT = pathlib.Path(__file__).resolve().parents[1]
VERIFY = ROOT / "tools" / "verify_package.py"
SIGN = ROOT / "tools" / "sign_package.py"
needs_ssh = pytest.mark.skipif(shutil.which("ssh-keygen") is None, reason="ssh-keygen not installed")


def keygen(d, name):
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", name, "-f", str(d / name)],
                   check=True)
    return d / name


def allowed(d, entries):
    f = d / "allowed_signers"
    f.write_text("".join(f'{ident} namespaces="{ns}" {" ".join((key.with_suffix(".pub")).read_text().split()[:2])}\n'
                         for ident, key, ns in entries))
    return f


def sign(key, path, ns="sv-package"):
    sig = pathlib.Path(str(path) + ".sig")
    if sig.exists():
        sig.unlink()
    subprocess.run(["ssh-keygen", "-Y", "sign", "-f", str(key), "-n", ns, str(path)],
                   check=True, capture_output=True)
    return sig


def verify(path, sig, signers, ident, env=None):
    p = subprocess.run([sys.executable, str(VERIFY), str(path), "--signature", str(sig),
                        "--allowed-signers", str(signers), "--identity", ident],
                       capture_output=True, text=True, env=env)
    return p.returncode, p.stdout


@pytest.fixture
def signed(tmp_path):
    key = keygen(tmp_path, "chad")
    pkg = tmp_path / "pkg.json"
    (tmp_path / "zones").mkdir()
    pkg.write_text(canonical_json(make(thermal=thermal_fixture(tmp_path / "zones"))), encoding="utf-8")
    return tmp_path, key, pkg, sign(key, pkg), allowed(tmp_path, [("chad", key, "sv-package")])


@needs_ssh
def test_s0_untouched_signed_package_verifies(signed):
    _, _, pkg, sig, signers = signed
    rc, out = verify(pkg, sig, signers, "chad")
    assert rc == 0 and "authenticity=SIGNED:chad" in out


@needs_ssh
def test_s1_no_resealed_rewrite_survives_the_signature(signed):
    _, _, pkg, sig, signers = signed
    import json
    p = json.loads(pkg.read_text(encoding="utf-8"))
    total, unsigned = fs.sweep(vp, p)
    _, with_sig = fs.sweep(vp, p, (str(sig), str(signers), "chad"))
    assert (total, set(unsigned), with_sig) == (119, UNBOUND, {})


@needs_ssh
def test_s2_wrong_key_identity_namespace_or_package_fails(signed):
    d, key, pkg, sig, signers = signed
    other = keygen(d, "mallory")
    assert verify(pkg, sign(other, pkg), signers, "chad")[0] == 1          # key not allowed
    sig = sign(key, pkg)
    two = allowed(d, [("chad", key, "sv-package"), ("graeme", other, "sv-package")])
    assert verify(pkg, sig, two, "graeme")[0] == 1                         # right key, other identity
    assert verify(pkg, sign(key, pkg, ns="other"), signers, "chad")[0] == 1  # wrong namespace
    sig = sign(key, pkg)
    other_pkg = d / "other.json"
    other_pkg.write_text(canonical_json(make({"thermal": "hot"})), encoding="utf-8")
    assert verify(other_pkg, sig, signers, "chad")[0] == 1                 # another package's bytes


@needs_ssh
def test_s3_missing_ssh_keygen_is_could_not_look(signed):
    _, _, pkg, sig, signers = signed
    rc, out = verify(pkg, sig, signers, "chad", env=dict(os.environ, PATH=""))
    assert rc == 2 and "COULD NOT LOOK" in out


def test_s4_unsigned_verification_is_unchanged(tmp_path):
    pkg = tmp_path / "pkg.json"
    pkg.write_text(canonical_json(make()), encoding="utf-8")
    p = subprocess.run([sys.executable, str(VERIFY), str(pkg)], capture_output=True, text=True)
    assert p.returncode == 0 and "authenticity=NOT_PROVEN" in p.stdout


def test_signature_flags_must_come_together(tmp_path):
    pkg = tmp_path / "pkg.json"
    pkg.write_text(canonical_json(make()), encoding="utf-8")
    p = subprocess.run([sys.executable, str(VERIFY), str(pkg), "--signature", "x.sig"],
                       capture_output=True, text=True)
    assert p.returncode == 2


@needs_ssh
def test_sign_tool_keygen_refuses_to_overwrite(tmp_path):
    env = dict(os.environ, SV_SIGNING_KEY=str(tmp_path / "k" / "key"))
    first = subprocess.run([sys.executable, str(SIGN), "keygen", "chad"], capture_output=True, text=True, env=env)
    second = subprocess.run([sys.executable, str(SIGN), "keygen", "chad"], capture_output=True, text=True, env=env)
    line = first.stdout.strip().splitlines()[-1]
    assert first.returncode == 0 and line.startswith('chad namespaces="sv-package" ssh-ed25519 ')
    assert second.returncode == 1 and line in second.stdout
    pkg = tmp_path / "pkg.json"
    pkg.write_text(canonical_json(make()), encoding="utf-8")
    assert subprocess.run([sys.executable, str(SIGN), "sign", str(pkg)], env=env).returncode == 0
    signers = tmp_path / "allowed"
    signers.write_text(line + "\n")
    assert verify(pkg, str(pkg) + ".sig", signers, "chad")[0] == 0
