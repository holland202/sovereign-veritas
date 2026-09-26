"""The published evidence in this repository, checked on every push (R2).

Registered before this code ran: docs/EVIDENCE_PACKAGE.md, "Publishing the measured pair".
Invariants over evidence/ and witness/packages.log:
  - every published package passes every consistency check and has a signature file;
  - its signature verifies as holland202 against keys/allowed_signers (where ssh-keygen exists);
  - every witness entry names a published package (the log claims "made public");
  - the last entry verifies LATEST_WITNESSED, earlier ones STALE, unlogged ones NOT_WITNESSED.
The checker is first run against a synthetic evidence tree, intact and sabotaged, so a green run
on the real tree means something.
"""
import importlib.util
import json
import pathlib
import shutil

import pytest

from sovereign_veritas.evidence import canonical_json
from test_package import make
from test_signature import allowed, keygen, needs_ssh, sign

ROOT = pathlib.Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("verify_package", ROOT / "tools" / "verify_package.py")
vp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vp)
IDENTITY = "holland202"
HAVE_SSH = shutil.which("ssh-keygen") is not None


def problems(evidence, log, signers, check_signatures=HAVE_SSH):
    """Every broken invariant, as text. An empty list means all of them hold."""
    found = []
    packages = []
    for path in sorted(evidence.glob("*.json")):
        data = path.read_bytes()
        packages.append((path, data, json.loads(data.decode("utf-8"))))
    if not packages:
        found.append("no published packages")
    digests = [d for _, d in vp.read_witness_log(str(log))]
    published = {pkg["package_sha256"] for _, _, pkg in packages}
    for path, data, pkg in packages:
        failed = [name for name, ok, _ in vp.verify(pkg) if not ok]
        if failed:
            found.append(f"{path.name}: fails {failed}")
        sig = pathlib.Path(f"{path}.sig")
        if not sig.exists():
            found.append(f"{path.name}: no signature file")
        elif check_signatures:
            ok, detail = vp.check_signature(data, str(sig), str(signers), IDENTITY)
            if not ok:
                found.append(f"{path.name}: signature: {detail}")
        ok, status, detail = vp.check_witness(pkg, str(log))
        digest = pkg["package_sha256"]
        if digest not in digests:
            expected = (False, "NOT_WITNESSED")
        elif digests.index(digest) == len(digests) - 1:
            expected = (True, f"LATEST_WITNESSED({len(digests)})")
        else:
            expected = (False, "STALE")
        if (ok, status) != expected:
            found.append(f"{path.name}: witness {status} ({detail}), expected {expected[1]}")
    for seq, digest in enumerate(digests, start=1):
        if digest not in published:
            found.append(f"witness entry {seq} {digest[:12]}: no published package")
    return found


# ---- the real tree ------------------------------------------------------------------------------
def test_r2_published_evidence_holds():
    assert problems(ROOT / "evidence", ROOT / "witness" / "packages.log",
                    ROOT / "keys" / "allowed_signers") == []


# ---- the checker itself, on a synthetic tree ----------------------------------------------------
@pytest.fixture
def tree(tmp_path):
    """Two signed packages published; the first witnessed, the second not."""
    ev = tmp_path / "evidence"
    ev.mkdir()
    a, b = make({"thermal": "normal"}), make({"thermal": "hot"})
    paths = []
    for name, pkg in (("a.json", a), ("b.json", b)):
        p = ev / name
        p.write_text(canonical_json(pkg), encoding="utf-8")
        paths.append(p)
    log = tmp_path / "packages.log"
    log.write_text(f"{vp.WITNESS_HEADER}\n1 {a['package_sha256']}\n", encoding="utf-8")
    signers = None
    if HAVE_SSH:
        key = keygen(tmp_path, IDENTITY)
        signers = allowed(tmp_path, [(IDENTITY, key, "sv-package")])
        for p in paths:
            sign(key, p)
    else:
        for p in paths:
            pathlib.Path(f"{p}.sig").write_text("unchecked\n")
    return ev, log, signers, paths


def test_checker_passes_an_intact_tree(tree):
    ev, log, signers, _ = tree
    assert problems(ev, log, signers) == []


def test_checker_catches_one_changed_byte(tree):
    ev, log, signers, (a, _) = tree
    data = a.read_bytes()
    a.write_bytes(data.replace(b'"fixture"', b'"fixturf"', 1))
    assert any(p.startswith("a.json: fails") for p in problems(ev, log, signers))


@needs_ssh
def test_checker_catches_swapped_signatures(tree):
    ev, log, signers, (a, b) = tree
    sa, sb = pathlib.Path(f"{a}.sig"), pathlib.Path(f"{b}.sig")
    tmp = sa.read_bytes()
    sa.write_bytes(sb.read_bytes())
    sb.write_bytes(tmp)
    found = problems(ev, log, signers)
    assert any(p.startswith("a.json: signature") for p in found)
    assert any(p.startswith("b.json: signature") for p in found)


def test_checker_catches_a_missing_signature_file(tree):
    ev, log, signers, (a, _) = tree
    pathlib.Path(f"{a}.sig").unlink()
    assert "a.json: no signature file" in problems(ev, log, signers)


def test_checker_catches_a_witness_entry_nobody_can_check(tree):
    ev, log, signers, _ = tree
    with open(log, "a", encoding="utf-8") as fh:
        fh.write(f"2 {'ab' * 32}\n")
    found = problems(ev, log, signers)
    assert found == ["witness entry 2 abababababab: no published package"]


def test_checker_expects_stale_for_an_earlier_entry(tree):
    ev, log, signers, (_, b) = tree
    pkg_b = json.loads(b.read_text(encoding="utf-8"))
    with open(log, "a", encoding="utf-8") as fh:
        fh.write(f"2 {pkg_b['package_sha256']}\n")
    assert problems(ev, log, signers) == []  # a is STALE, b is LATEST_WITNESSED(2): both as expected


def test_checker_catches_a_verifier_that_misreports_freshness(tree, monkeypatch):
    """The witness expectation is computed here, independently of vp.check_witness."""
    ev, log, signers, _ = tree
    monkeypatch.setattr(vp, "check_witness", lambda pkg, path: (True, "LATEST_WITNESSED(1)", "lie"))
    assert problems(ev, log, signers) == [
        "b.json: witness LATEST_WITNESSED(1) (lie), expected NOT_WITNESSED"]
