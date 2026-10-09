"""Shared fixtures for the P-001 acceptance tests (coordination/p001/ACCEPTANCE.md, frozen at 1c16e66).

Throwaway ed25519 keys made per test with ssh-keygen in a temporary directory; nothing here touches
keys/allowed_signers or any real key. Packages are built by the kernel (sv.package/1) from
tests/test_package.py's fixture, so their contract binding is the real one.
"""
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys

import pytest

from sovereign_veritas.evidence import canonical_json
from test_package import make, vp  # noqa: F401  (vp re-exported for the tests)
from test_signature import allowed, keygen, sign

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONSUMER = ROOT / "tools" / "consumer.py"
VERIFY = ROOT / "tools" / "verify_package.py"
needs_ssh = pytest.mark.skipif(shutil.which("ssh-keygen") is None, reason="ssh-keygen not installed")

__all__ = ["CONSUMER", "VERIFY", "ROOT", "needs_ssh", "keygen", "allowed", "sign", "write_pkg", "write_log",
           "accept", "verify_cli", "state_bytes", "Kit", "reseal", "vp"]


def write_pkg(path, cfg=None, pkg=None):
    """Write a package (default: a fresh kernel-built sv.package/1) as canonical JSON bytes."""
    path = pathlib.Path(path)
    path.write_text(canonical_json(pkg if pkg is not None else make(cfg)), encoding="utf-8")
    return path


def reseal(pkg):
    """Recompute package_sha256 after an edit (what a forger with the code would do)."""
    body = {k: v for k, v in pkg.items() if k != "package_sha256"}
    pkg["package_sha256"] = hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()
    return pkg


def write_log(path, pkgs):
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("# sv witness log v0\n" + "".join(
            f"{i} {json.loads(pathlib.Path(p).read_text(encoding='utf-8'))['package_sha256']}\n"
            for i, p in enumerate(pkgs, 1)))
    return pathlib.Path(path)


def accept(pkg, log, state, sig=None, signers=None, ident=None, extra=(), env=None):
    args = [sys.executable, str(CONSUMER), "accept", str(pkg), "--witness-log", str(log), "--state", str(state)]
    if sig is not None:
        args += ["--signature", str(sig)]
    if signers is not None:
        args += ["--allowed-signers", str(signers)]
    if ident is not None:
        args += ["--identity", ident]
    return subprocess.run(args + list(extra), capture_output=True, text=True, env=env)


def verify_cli(pkg, *extra, env=None):
    return subprocess.run([sys.executable, str(VERIFY), str(pkg), *map(str, extra)],
                          capture_output=True, text=True, env=env)


def state_bytes(state):
    """Exact bytes of the state file, or None when it does not exist (absence is a state too)."""
    state = pathlib.Path(state)
    return state.read_bytes() if state.exists() else None


class Kit:
    """One throwaway signer ("chad") and helpers to sign packages under it."""

    def __init__(self, d):
        self.d = pathlib.Path(d)
        self.key = keygen(self.d, "chad")
        self.signers = allowed(self.d, [("chad", self.key, "sv-package")])

    def pkg(self, name, cfg=None, pkg=None):
        p = write_pkg(self.d / name, cfg, pkg)
        return p, sign(self.key, p)

    def accept(self, pkg, sig, log, state, ident="chad", **kw):
        return accept(pkg, log, state, sig, self.signers, ident, **kw)


def no_traceback(p):
    return "Traceback" not in p.stdout + p.stderr


os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
