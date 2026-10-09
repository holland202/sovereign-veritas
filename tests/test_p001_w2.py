"""P-001 W2: sv.package/1 is bound to the locally trusted Gate contract; legacy v0 stays as it was.

Implements cases B01-B08 of coordination/p001/ACCEPTANCE.md, frozen by the owner at commit
1c16e661d8a2db44bbc60a589b2348bfd8ccc936 (sha256 dc54e8c1...b4d28d). Case ids are in the test names.
"""
import copy
import hashlib
import importlib.util
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

import pytest

from sovereign_veritas import package as kernel_package
from p001_support import ROOT, Kit, accept, needs_ssh, no_traceback, reseal, state_bytes, verify_cli, vp, \
    write_log, write_pkg
from test_package import make

TRUSTED = "44823d0ff707213ae8bc310ed8b21e135f8e742fd8834e8f9474743d3a250628"
MANIFEST = ROOT / "tests" / "p001" / "legacy_manifest_709da9e.sha256"
LEGACY_SIGNED = ROOT / "evidence" / "sv_package_7548237bceca.json"  # latest entry of witness/packages.log
LEGACY_UNSIGNED = ROOT / "runs" / "vehicle_sitl_v13" / "sv_package_a911244dfcf7.json"


def failed(pkg, legacy=False):
    return sorted(n for n, ok, _ in vp.verify(pkg, legacy=legacy) if not ok)


def detail(pkg, name):
    return next(d for n, ok, d in vp.verify(pkg) if n == name)


# ---- B01 ---------------------------------------------------------------------------------------------

def test_b01_new_packages_are_v1_with_exactly_the_contract_binding():
    pkg = make()
    assert pkg["schema"] == "sv.package/1"
    assert pkg["contract"] == {"id": "sv.gate/0", "conformance_digest": TRUSTED}
    assert "version" not in pkg["contract"]
    assert failed(pkg) == []
    # Both fields are inside the canonical body: changing either changes package_sha256.
    for field, value in (("id", "sv.gate/1"), ("conformance_digest", "0" * 64)):
        other = copy.deepcopy(pkg)
        other["contract"][field] = value
        assert reseal(other)["package_sha256"] != pkg["package_sha256"], field


def test_b01_verifier_trust_anchor_is_local_and_matches_the_kernel():
    assert vp.TRUSTED_CONTRACTS == {"sv.gate/0": TRUSTED}
    assert kernel_package.CONTRACT == {"id": "sv.gate/0", "conformance_digest": TRUSTED}


@needs_ssh
def test_b01_the_signature_covers_the_contract_bytes(tmp_path):
    k = Kit(tmp_path)
    pkg, sig = k.pkg("pkg.json")
    assert verify_cli(pkg, "--signature", sig, "--allowed-signers", k.signers, "--identity", "chad").returncode == 0
    swapped = json.loads(pkg.read_text(encoding="utf-8"))
    swapped["contract"]["id"] = "sv.gate/1"
    other = write_pkg(tmp_path / "other.json", pkg=reseal(swapped))
    r = verify_cli(other, "--signature", sig, "--allowed-signers", k.signers, "--identity", "chad")
    assert r.returncode == 1 and "FAIL  signature" in r.stdout


# ---- B02 ---------------------------------------------------------------------------------------------

def _mutations():
    def drop(p):
        del p["contract"]

    def set_(path, value):
        def f(p):
            p["contract"][path] = value
        return f

    def delete(key):
        def f(p):
            del p["contract"][key]
        return f

    return {
        "contract missing": drop,
        "contract not an object": lambda p: p.__setitem__("contract", "sv.gate/0"),
        "contract.id missing": delete("id"),
        "contract.id malformed": set_("id", 0),
        "contract.id empty": set_("id", ""),
        "contract.conformance_digest missing": delete("conformance_digest"),
        "contract.conformance_digest malformed": set_("conformance_digest", ["x"]),
        "separate contract.version": set_("version", "0"),
        "unknown top-level key": lambda p: p.__setitem__("contract_version", "0"),
        "unsupported schema": lambda p: p.__setitem__("schema", "sv.package/2"),
    }


@pytest.mark.parametrize("name", list(_mutations()))
def test_b02_closed_schema_fails_closed(name):
    good = make()
    assert failed(good) == []
    bad = copy.deepcopy(good)
    _mutations()[name](bad)
    assert failed(reseal(bad)), name


@pytest.mark.parametrize("text", [
    lambda s: s.replace('"schema":"sv.package/1"', '"schema":"sv.package/1","schema":"sv.package/1"', 1),
    lambda s: s.replace('"elapsed_ms":1.0', '"elapsed_ms":NaN', 1),
], ids=["duplicate key", "non-finite number"])
def test_b02_duplicate_keys_and_nonfinite_numbers_fail_closed(tmp_path, text):
    from sovereign_veritas.evidence import canonical_json
    raw = canonical_json(make())
    bad = text(raw)
    assert bad != raw
    with pytest.raises(ValueError):
        vp.loads_bounded(bad)
    f = tmp_path / "bad.json"
    f.write_text(bad, encoding="utf-8")
    r = verify_cli(f)
    assert r.returncode == 2 and "COULD NOT LOOK" in r.stdout and no_traceback(r)


# ---- B03 ---------------------------------------------------------------------------------------------

SUBSTITUTIONS = {
    "a wrong digest, trusted id": ({"id": "sv.gate/0", "conformance_digest": "ab" * 32}, "contract.conformance_digest"),
    "an unrelated id, same digest": ({"id": "acme.gate/7", "conformance_digest": TRUSTED}, "contract.id"),
    "id sv.gate/1, same digest": ({"id": "sv.gate/1", "conformance_digest": TRUSTED}, "contract.id"),
}


@needs_ssh
@pytest.mark.parametrize("name", list(SUBSTITUTIONS))
def test_b03_contract_substitution_fails_even_when_resealed_and_validly_signed(tmp_path, name):
    contract, field = SUBSTITUTIONS[name]
    k = Kit(tmp_path)
    forged = make()
    forged["contract"] = dict(contract)
    pkg, sig = k.pkg("forged.json", pkg=reseal(forged))
    r = verify_cli(pkg, "--signature", sig, "--allowed-signers", k.signers, "--identity", "chad")
    assert r.returncode == 1
    lines = r.stdout.splitlines()
    assert any(l.startswith("PASS  package_digest") for l in lines)   # integrity passes
    assert any(l.startswith("PASS  signature") for l in lines)        # authenticity passes
    binding = next(l for l in lines if "contract_binding" in l)
    assert binding.startswith("FAIL") and field in binding, binding  # the reason names the field
    assert "contract=UNBOUND" in r.stdout
    st = tmp_path / "state.json"
    c = k.accept(pkg, sig, write_log(tmp_path / "w.log", [pkg]), st)
    assert c.returncode == 1 and state_bytes(st) is None


# ---- B04 ---------------------------------------------------------------------------------------------

@needs_ssh
def test_b04_the_trusted_pair_passes_the_full_verifier(tmp_path):
    k = Kit(tmp_path)
    pkg, sig = k.pkg("pkg.json")
    log = write_log(tmp_path / "w.log", [pkg])
    r = verify_cli(pkg, "--signature", sig, "--allowed-signers", k.signers, "--identity", "chad",
                   "--witness-log", log)
    assert r.returncode == 0, r.stdout
    assert "PASS  contract_binding" in r.stdout
    assert "VERDICT  CONSISTENT" in r.stdout and "authenticity=SIGNED:chad" in r.stdout
    assert "contract=BOUND:sv.gate/0" in r.stdout


def test_b04_trusted_digest_equals_the_one_recomputed_from_the_shipped_vectors():
    spec = importlib.util.spec_from_file_location("gc_p001", ROOT / "tools" / "gate_contract.py")
    gc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gc)
    vectors = gc.read_vectors()
    recomputed = gc.conformance_digest([(v["id"], v["expect"]["decision"], v["expect"]["reasons"]) for v in vectors])
    assert len(vectors) == 4690
    assert recomputed == vp.TRUSTED_CONTRACTS[gc.CONTRACT] == TRUSTED


def test_b04_self_attestation_never_counts():
    # A package whose contract equals itself but not the local anchor must still fail.
    pkg = make()
    pkg["contract"] = {"id": "sv.gate/0", "conformance_digest": pkg["package_sha256"]}
    assert "contract_binding" in failed(reseal(pkg))


# ---- B05 ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize("impl", ["kernel", "verifier"])
def test_b05_gate_decisions_unchanged_on_all_4690_vectors(impl):
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "gate_contract.py"), "--check", impl],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout
    assert "| 4690 vectors" in r.stdout and "VERDICT  CONFORMS" in r.stdout
    assert f"conformance digest {TRUSTED}  (expected {TRUSTED})" in r.stdout


def test_b05_all_defaulted_allow_limitation_is_unchanged():
    # W3 is a KNOWN LIMITATION in P-001: an honest all-DEFAULTED package still gets ALLOW. PR-1's
    # registered PR5 pins exactly that; it must still hold, i.e. W2 did not quietly change the Gate.
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "pr1_probe.py")], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-2000:]
    assert re.search(r"^\s*PR5\s+HELD$", r.stdout, re.M), r.stdout[-2000:]


# ---- B06 ---------------------------------------------------------------------------------------------

def _manifest():
    rows = [l.split(None, 1) for l in MANIFEST.read_text(encoding="utf-8").splitlines()
            if l and not l.startswith("#")]
    return {path.strip(): digest for digest, path in rows}


def test_b06_every_archived_file_is_byte_identical():
    man = _manifest()
    assert len(man) == 55  # 46 sv.package/0 JSON + 8 signatures + witness/packages.log
    assert sum(p.endswith(".json") for p in man) == 46 and sum(p.endswith(".sig") for p in man) == 8
    for path, digest in man.items():
        f = ROOT / path
        assert f.exists(), f"archived file vanished: {path}"
        assert hashlib.sha256(f.read_bytes()).hexdigest() == digest, f"archived file changed: {path}"


def test_b06_no_v0_package_was_added_or_removed():
    pat = re.compile(rb'"schema"\s*:\s*"sv\.package/0"')
    found = set()
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in (".git", "__pycache__", "node_modules", ".pytest_cache")]
        for fn in filenames:
            if fn.endswith(".json"):
                p = pathlib.Path(dirpath, fn)
                if pat.search(p.read_bytes()):
                    found.add(p.relative_to(ROOT).as_posix())
    assert found == {p for p in _manifest() if p.endswith(".json")}


@needs_ssh
def test_b06_signed_legacy_keeps_its_original_signature_and_is_legacy_unbound():
    r = verify_cli("--legacy", LEGACY_SIGNED, "--signature", f"{LEGACY_SIGNED}.sig",
                   "--allowed-signers", ROOT / "keys" / "allowed_signers", "--identity", "holland202")
    assert r.returncode == 0, r.stdout
    assert "authenticity=SIGNED:holland202" in r.stdout and "contract=LEGACY_UNBOUND" in r.stdout


def test_b06_unsigned_legacy_is_inspectable_legacy_unbound_and_not_proven():
    r = verify_cli("--legacy", LEGACY_UNSIGNED)
    assert r.returncode == 0, r.stdout
    assert "authenticity=NOT_PROVEN" in r.stdout and "contract=LEGACY_UNBOUND" in r.stdout
    assert "SIGNED" not in r.stdout


# ---- B07 ---------------------------------------------------------------------------------------------

@needs_ssh
def test_b07_consumer_refuses_signed_witnessed_v0(tmp_path):
    st = tmp_path / "state.json"
    r = accept(LEGACY_SIGNED, ROOT / "witness" / "packages.log", st, f"{LEGACY_SIGNED}.sig",
               ROOT / "keys" / "allowed_signers", "holland202")
    assert r.returncode == 1, r.stdout
    assert "PASS  signature" in r.stdout and "PASS  freshness_witness" in r.stdout  # historically valid...
    assert "FAIL  schema_v1_only" in r.stdout and "REFUSED" in r.stdout            # ...and still refused
    assert state_bytes(st) is None


@needs_ssh
def test_b07_consumer_refuses_v0_with_existing_state(tmp_path):
    k = Kit(tmp_path)
    pkg, sig = k.pkg("v1.json")
    st = tmp_path / "state.json"
    assert k.accept(pkg, sig, write_log(tmp_path / "w.log", [pkg]), st).returncode == 0
    before = state_bytes(st)
    legacy = write_pkg(tmp_path / "legacy.json", pkg=json.loads(LEGACY_UNSIGNED.read_text(encoding="utf-8")))
    lsig = k.pkg("legacy_signed.json", pkg=json.loads(legacy.read_text(encoding="utf-8")))[1]
    r = k.accept(tmp_path / "legacy_signed.json", lsig, write_log(tmp_path / "w2.log", [pkg, legacy]), st)
    assert r.returncode == 1 and "FAIL  schema_v1_only" in r.stdout
    assert state_bytes(st) == before


def test_b07_v0_is_never_silently_upgraded():
    v0 = json.loads(LEGACY_UNSIGNED.read_text(encoding="utf-8"))
    r = verify_cli(LEGACY_UNSIGNED)  # the normal path, no --legacy
    assert r.returncode == 1 and "FAIL  contract_binding" in r.stdout and "LEGACY_UNBOUND" in r.stdout
    grafted = copy.deepcopy(v0)  # a v0 that pastes in a binding is not a bound package
    grafted["contract"] = {"id": "sv.gate/0", "conformance_digest": TRUSTED}
    assert "schema_closed" in failed(reseal(grafted), legacy=True)
    assert "schema_closed" in failed(reseal(grafted))


# ---- B08 ---------------------------------------------------------------------------------------------

DOC = ROOT / "docs" / "P001_SIGNED_WORKFLOW.md"
DOC_COMMANDS = [
    "python tools/sign_package.py keygen IDENTITY",
    "python tools/make_package.py --thermal-status normal",
    "python tools/sign_package.py sign PACKAGE.json",
    "python tools/witness.py append PACKAGE.json --log LOG",
    "python tools/verify_package.py PACKAGE.json --signature PACKAGE.json.sig --allowed-signers ALLOWED "
    "--identity IDENTITY --witness-log LOG",
    "python tools/consumer.py accept PACKAGE.json --witness-log LOG --state STATE.json --signature PACKAGE.json.sig "
    "--allowed-signers ALLOWED --identity IDENTITY",
    "python tools/verify_package.py --legacy evidence/sv_package_7548237bceca.json --signature "
    "evidence/sv_package_7548237bceca.json.sig --allowed-signers keys/allowed_signers --identity holland202",
]


def test_b08_documented_commands_are_the_tested_ones():
    text = DOC.read_text(encoding="utf-8")
    for cmd in DOC_COMMANDS:
        assert cmd in text, cmd
    for phrase in ("NOT PRODUCTION-READY", "NOT INDEPENDENTLY SECURITY-VALIDATED", "NOT_TESTED",
                   "LEGACY_UNBOUND", "not durability against power loss"):
        assert phrase in text, phrase


@needs_ssh
def test_b08_documented_commands_run_end_to_end(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    env = dict(os.environ, HOME=str(home), USERPROFILE=str(home), SV_SIGNING_KEY=str(tmp_path / "keys" / "k"))
    subs = {"IDENTITY": "tester", "LOG": str(tmp_path / "w.log"), "STATE.json": str(tmp_path / "state.json"),
            "ALLOWED": str(tmp_path / "allowed_signers")}
    outputs = []

    def run(cmd, pkg=None):
        args = cmd.split()
        args[0] = sys.executable
        out = []
        for a in args:
            for key, val in subs.items():
                if a == key:
                    a = val
            if pkg is not None:
                a = a.replace("PACKAGE.json", pkg)
            out.append(a)
        p = subprocess.run(out, capture_output=True, text=True, env=env, cwd=ROOT)
        outputs.append((" ".join(out), p.returncode, p.stdout + p.stderr))
        return p

    p = run(DOC_COMMANDS[0])
    assert p.returncode == 0, p.stdout + p.stderr
    pathlib.Path(subs["ALLOWED"]).write_text(p.stdout.strip().splitlines()[-1] + "\n")
    p = run(DOC_COMMANDS[1])
    assert p.returncode == 0, p.stdout
    pkg = next(l.split()[1] for l in p.stdout.splitlines() if l.startswith("package "))
    for cmd in DOC_COMMANDS[2:4]:
        p = run(cmd, pkg)
        assert p.returncode == 0, (cmd, p.stdout + p.stderr)
    p = run(DOC_COMMANDS[4], pkg)
    assert p.returncode == 0 and "authenticity=SIGNED:tester" in p.stdout and "contract=BOUND:sv.gate/0" in p.stdout, \
        p.stdout
    p = run(DOC_COMMANDS[5], pkg)
    assert p.returncode == 0 and "CONSUMER  ACCEPTED" in p.stdout, p.stdout
    p = run(DOC_COMMANDS[6])
    assert p.returncode == 0 and "contract=LEGACY_UNBOUND" in p.stdout and "SIGNED:holland202" in p.stdout, p.stdout
    os.remove(pkg)
    out = os.environ.get("P001_B08_TRANSCRIPT")
    if out:  # CI keeps the command lines and outputs (ACCEPTANCE B08)
        with open(out, "w", encoding="utf-8") as fh:
            for cmd, rc, text in outputs:
                fh.write(f"$ {cmd}\n{text}[exit {rc}]\n\n")
