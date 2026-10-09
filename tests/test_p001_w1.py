"""P-001 W1 + A08: the production consumer refuses unauthenticated acceptance.

Implements cases A01-A08 of coordination/p001/ACCEPTANCE.md, frozen by the owner at commit
1c16e661d8a2db44bbc60a589b2348bfd8ccc936 (sha256 dc54e8c1...b4d28d), K6 = A08 now. Case ids are in
the test names. Frozen cases are not edited here; new attacks would be added as new tests.

Every refusal and every could-not-look is checked against the state file's exact bytes (or its
continued absence), never only against printed text.
"""
import importlib.util
import json
import os
import sys

import pytest

from p001_support import CONSUMER, ROOT, Kit, accept, needs_ssh, no_traceback, reseal, sign, state_bytes, \
    verify_cli, write_log, write_pkg

pytestmark = needs_ssh


def load_consumer():
    spec = importlib.util.spec_from_file_location("consumer_p001", CONSUMER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def kit(tmp_path):
    return Kit(tmp_path)


def seeded(kit):
    """A consumer that already accepted one package, plus a second, latest, signed package."""
    first, sig1 = kit.pkg("first.json", {"steps": 1})
    second, sig2 = kit.pkg("second.json", {"steps": 2})
    st = kit.d / "state.json"
    r = kit.accept(first, sig1, write_log(kit.d / "w1.log", [first]), st)
    assert r.returncode == 0, r.stdout + r.stderr
    return second, sig2, write_log(kit.d / "w2.log", [first, second]), st


# ---- A01 ---------------------------------------------------------------------------------------------

def test_a01_signed_bound_v1_is_accepted_once_then_replay_refused(kit):
    pkg, sig = kit.pkg("pkg.json")
    log, st = write_log(kit.d / "w.log", [pkg]), kit.d / "state.json"
    r = kit.accept(pkg, sig, log, st)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "CONSUMER  ACCEPTED  authenticity=SIGNED:chad  contract=BOUND:sv.gate/0" in r.stdout
    cons, digest = load_consumer(), json.loads(pkg.read_text(encoding="utf-8"))["package_sha256"]
    state = json.loads(st.read_text(encoding="utf-8"))
    entries = [(1, digest)]
    assert state == {"consumed": [digest], "anchor": {"entries": 1, "prefix_sha256": cons.prefix_digest(entries)}}
    before = state_bytes(st)
    r2 = kit.accept(pkg, sig, log, st)
    assert r2.returncode == 1 and "REFUSED" in r2.stdout and "replay" in r2.stdout
    assert state_bytes(st) == before


# ---- A02 ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize("omit", ["--signature", "--allowed-signers", "--identity", "only-signature"])
@pytest.mark.parametrize("with_state", [True, False])
def test_a02_every_incomplete_invocation_is_a_usage_error(kit, omit, with_state):
    if with_state:
        pkg, sig, log, st = seeded(kit)
    else:
        pkg, sig = kit.pkg("pkg.json")
        log, st = write_log(kit.d / "w.log", [pkg]), kit.d / "state.json"
    before = state_bytes(st)
    args = {"sig": sig, "signers": kit.signers, "ident": "chad"}
    if omit == "only-signature":  # the exact pre-fix crash: --signature without --allowed-signers (K2)
        args = {"sig": sig}
    else:
        args[{"--signature": "sig", "--allowed-signers": "signers", "--identity": "ident"}[omit]] = None
    r = accept(pkg, log, st, **args)
    assert r.returncode == 2, r.stdout + r.stderr
    assert "usage:" in r.stderr and no_traceback(r)
    assert "REFUSED" not in r.stdout and "ACCEPTED" not in r.stdout
    assert state_bytes(st) == before


def test_a02_complete_but_unreadable_material_is_could_not_look(kit):
    pkg, sig, log, st = seeded(kit)
    before = state_bytes(st)
    r = accept(pkg, log, st, kit.d / "no-such.sig", kit.signers, "chad")
    assert r.returncode == 2 and "COULD NOT LOOK" in r.stdout and no_traceback(r)
    assert state_bytes(st) == before


# ---- A03 ---------------------------------------------------------------------------------------------

def test_a03_invalid_signatures_are_refused_and_the_positive_control_still_passes(kit):
    pkg, sig, log, st = seeded(kit)
    before = state_bytes(st)
    (kit.d / "mallory_dir").mkdir()
    other = Kit(kit.d / "mallory_dir")
    cases = {}
    # 1. one package byte altered after signing (one letter of the artifact name)
    altered = kit.d / "altered.json"
    raw = pkg.read_bytes()
    altered.write_bytes(raw.replace(b'"name":"fixture"', b'"name":"fixturE"', 1))
    assert altered.read_bytes() != raw
    cases["altered package byte"] = (altered, sig, kit.signers, "chad")
    # 2. signature altered
    bad_sig = kit.d / "bad.sig"
    lines = sig.read_text().splitlines()
    mid = len(lines) // 2
    lines[mid] = lines[mid][:-4] + ("AAAA" if not lines[mid].endswith("AAAA") else "BBBB")
    bad_sig.write_text("\n".join(lines) + "\n")
    cases["altered signature"] = (pkg, bad_sig, kit.signers, "chad")
    # 3. wrong signer identity (the key is chad's; ask for graeme)
    cases["wrong identity"] = (pkg, sig, kit.signers, "graeme")
    # 4. unknown public key: signed by a key not in allowed_signers
    cases["unknown key"] = (pkg, sign(other.key, write_pkg(kit.d / "mal.json", pkg=json.loads(pkg.read_text()))),
                            kit.signers, "chad")
    # 5. wrong namespace
    ns_copy = write_pkg(kit.d / "ns.json", pkg=json.loads(pkg.read_text()))
    cases["wrong namespace"] = (pkg, sign(kit.key, ns_copy, ns="file"), kit.signers, "chad")
    for name, (p, s, signers, ident) in cases.items():
        r = accept(p, log, st, s, signers, ident)
        assert r.returncode == 1, (name, r.stdout + r.stderr)
        assert "FAIL  signature" in r.stdout and "REFUSED" in r.stdout and no_traceback(r), name
        assert state_bytes(st) == before, name
    r = kit.accept(pkg, sig, log, st)  # positive control: the correct key still passes
    assert r.returncode == 0, r.stdout + r.stderr


# ---- A04 ---------------------------------------------------------------------------------------------

def test_a04_missing_ssh_keygen_is_could_not_look(kit):
    pkg, sig, log, st = seeded(kit)
    before = state_bytes(st)
    r = kit.accept(pkg, sig, log, st, env=dict(os.environ, PATH=str(kit.d / "empty-path")))
    assert r.returncode == 2 and "COULD NOT LOOK" in r.stdout and "ssh-keygen" in r.stdout and no_traceback(r)
    assert state_bytes(st) == before
    # Control: the same invocation with the real PATH is accepted, so the only difference was the tool.
    r = kit.accept(pkg, sig, log, st)
    assert r.returncode == 0, r.stdout + r.stderr


# ---- A05 ---------------------------------------------------------------------------------------------

def test_a05_a_valid_signature_overrides_nothing_else(kit):
    pkg, sig, log, st = seeded(kit)
    first = kit.d / "first.json"
    before = state_bytes(st)
    # (a) signed, but not the latest witnessed entry
    newer, _ = kit.pkg("newer.json", {"thermal": "hot"})
    r = kit.accept(pkg, sig, write_log(kit.d / "w_newer.log", [first, pkg, newer]), st)
    assert r.returncode == 1 and "FAIL  freshness_witness" in r.stdout
    assert state_bytes(st) == before
    # (b) a broken semantic check: decision flipped, resealed, then validly signed by the real key
    forged = json.loads(pkg.read_text(encoding="utf-8"))
    forged["decision"] = {"decision": "REFUSE", "reasons": ["verification_not_passed"]}
    fpath, fsig = kit.pkg("forged.json", pkg=reseal(forged))
    r = kit.accept(fpath, fsig, write_log(kit.d / "w_forged.log", [first, fpath]), st)
    assert r.returncode == 1 and "PASS  signature" in r.stdout and "REFUSED" in r.stdout
    assert state_bytes(st) == before
    # (c) legitimate, distinct, latest, extends the log: accepted, state advances
    r = kit.accept(pkg, sig, log, st)
    assert r.returncode == 0, r.stdout
    advanced = state_bytes(st)
    assert advanced != before
    # (d) the same package again: replay refused
    r = kit.accept(pkg, sig, log, st)
    assert r.returncode == 1 and "replay" in r.stdout
    assert state_bytes(st) == advanced
    # (e) rollback: a later package on a log truncated below the anchor this consumer has seen
    third, sig3 = kit.pkg("third.json", {"thermal": "hot"})
    r = kit.accept(third, sig3, write_log(kit.d / "w_rolled.log", [third]), st)
    assert r.returncode == 1 and "rollback" in r.stdout
    assert state_bytes(st) == advanced


# ---- A06 ---------------------------------------------------------------------------------------------

def test_a06_no_unsigned_escape_hatch(kit):
    pkg, sig, log, st = seeded(kit)
    before = state_bytes(st)
    for extra in (["--allow-unsigned"], ["--allow-unsigned", "--signature", str(sig)]):
        r = accept(pkg, log, st, extra=extra)
        assert r.returncode == 2 and "usage:" in r.stderr and no_traceback(r)
        assert state_bytes(st) == before
    env = dict(os.environ, SV_ALLOW_UNSIGNED="1", ALLOW_UNSIGNED="1", SV_UNSIGNED="1", SV_INSECURE="1")
    r = accept(pkg, log, st, env=env)
    assert r.returncode == 2 and "usage:" in r.stderr
    assert state_bytes(st) == before
    # The inspection path: verify_package.py reads an unsigned package, never touches consumer state,
    # and never says SIGNED or ACCEPTED.
    r = verify_cli(pkg)
    assert r.returncode == 0 and "authenticity=NOT_PROVEN" in r.stdout
    assert "SIGNED" not in r.stdout and "ACCEPTED" not in r.stdout
    assert state_bytes(st) == before


# ---- A07 ---------------------------------------------------------------------------------------------

def test_a07_trust_material_failures_fail_closed(kit):
    pkg, sig, log, st = seeded(kit)
    before = state_bytes(st)
    a_dir = kit.d / "a_directory"
    a_dir.mkdir()
    empty = kit.d / "empty"
    empty.write_text("")
    garbage = kit.d / "garbage_signers"
    garbage.write_text("this is not an allowed_signers file\n")
    could_not_look = {
        "allowed-signers absent": (sig, kit.d / "absent_signers", "chad"),
        "signature absent": (kit.d / "absent.sig", kit.signers, "chad"),
        "allowed-signers unreadable": (sig, a_dir, "chad"),
        "signature unreadable": (a_dir, kit.signers, "chad"),
        "signature empty": (empty, kit.signers, "chad"),
        "allowed-signers empty": (sig, empty, "chad"),
    }
    for name, (s, signers, ident) in could_not_look.items():
        r = accept(pkg, log, st, s, signers, ident)
        assert r.returncode == 2 and "COULD NOT LOOK" in r.stdout and no_traceback(r), (name, r.stdout + r.stderr)
        assert state_bytes(st) == before, name
    refused = {
        "malformed allowed-signers": (sig, garbage, "chad"),
        "identity not in the trust file": (sig, kit.signers, "mallory"),
    }
    for name, (s, signers, ident) in refused.items():
        r = accept(pkg, log, st, s, signers, ident)
        assert r.returncode == 1 and "FAIL  signature" in r.stdout and no_traceback(r), (name, r.stdout)
        assert state_bytes(st) == before, name


# ---- A08 ---------------------------------------------------------------------------------------------

def _run_main(cons, argv, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["consumer.py", *map(str, argv)])
    with pytest.raises(SystemExit) as e:
        cons.main()
    return e.value.code


def _argv(kit, pkg, sig, log, st):
    return ["accept", pkg, "--witness-log", log, "--state", st, "--signature", sig,
            "--allowed-signers", kit.signers, "--identity", "chad"]


def _leftovers(d):
    return sorted(p.name for p in d.iterdir() if p.name.startswith(".consumer-state-"))


@pytest.mark.parametrize("first_use", [False, True])
@pytest.mark.parametrize("where", ["serialization", "before_replace"])
def test_a08_interrupted_write_leaves_previous_state_then_retry_succeeds(kit, monkeypatch, capsys, where, first_use):
    if first_use:
        pkg, sig = kit.pkg("pkg.json")
        log, st = write_log(kit.d / "w.log", [pkg]), kit.d / "state.json"
    else:
        pkg, sig, log, st = seeded(kit)
    before = state_bytes(st)
    cons = load_consumer()
    real_dump, real_replace = cons.json.dump, cons.os.replace

    def broken_dump(obj, fh, **kw):
        fh.write('{"consumed": ["partial')  # half a document reaches the temp file, then the disk "fails"
        raise OSError("injected: disk full during serialization")

    def broken_replace(src, dst):
        raise OSError("injected: failure immediately before replacement")

    with monkeypatch.context() as m:
        if where == "serialization":
            m.setattr(cons.json, "dump", broken_dump)
        else:
            m.setattr(cons.os, "replace", broken_replace)
        code = _run_main(cons, _argv(kit, pkg, sig, log, st), m)
    out = capsys.readouterr().out
    assert code == 2 and "state not written" in out and "ACCEPTED  authenticity" not in out
    assert state_bytes(st) == before                       # previous bytes, or still absent on first use
    assert _leftovers(kit.d) == []                         # the temp file was cleaned up
    assert cons.json.dump is real_dump and cons.os.replace is real_replace
    code = _run_main(cons, _argv(kit, pkg, sig, log, st), monkeypatch)  # recovery: retry succeeds
    assert code == 0, capsys.readouterr().out
    state = json.loads(st.read_text(encoding="utf-8"))     # complete, valid JSON
    assert json.loads(pkg.read_text(encoding="utf-8"))["package_sha256"] in state["consumed"]
    assert _leftovers(kit.d) == []


def test_a08_temp_file_is_written_in_the_state_files_directory(kit, monkeypatch):
    cons = load_consumer()
    seen = []
    real = cons.os.replace

    def spy(src, dst):
        seen.append((os.path.dirname(os.path.abspath(src)), os.path.dirname(os.path.abspath(dst))))
        return real(src, dst)

    monkeypatch.setattr(cons.os, "replace", spy)
    sub = kit.d / "nested"
    sub.mkdir()
    cons.write_state(str(sub / "state.json"), {"consumed": [], "anchor": None})
    assert seen == [(str(sub), str(sub))]
    assert json.loads((sub / "state.json").read_text(encoding="utf-8")) == {"consumed": [], "anchor": None}


def test_a08_documentation_does_not_claim_power_loss_durability():
    doc = CONSUMER.read_text(encoding="utf-8")
    assert "not a durability guarantee against power loss" in doc
    assert ROOT.joinpath("tools", "consumer.py") == CONSUMER


# ---- additive (ChatGPT review probe 2, #66 comment 6085812504): not frozen cases, added attacks --------

@pytest.mark.parametrize("breakage", ["chain is a string", "contract is a list", "artifact missing", "top level list"])
def test_add_malformed_nested_v1_with_a_valid_signature_is_could_not_look_or_refused(kit, breakage):
    pkg, sig, log, st = seeded(kit)
    before = state_bytes(st)
    p = json.loads(pkg.read_text(encoding="utf-8"))
    if breakage == "chain is a string":
        p["provenance"]["chain"] = "x"
    elif breakage == "contract is a list":
        p["contract"] = ["sv.gate/0"]
    elif breakage == "artifact missing":
        del p["artifact"]
    else:
        p = [p]
    bad, bsig = kit.pkg("bad.json", pkg=p if isinstance(p, list) else reseal(p))
    r = kit.accept(bad, bsig, write_log(kit.d / "wb.log", [pkg]) if isinstance(p, list) else
                   write_log(kit.d / "wb.log", [kit.d / "first.json", bad]), st)
    assert r.returncode in (1, 2) and no_traceback(r), (breakage, r.stdout + r.stderr)
    assert "ACCEPTED" not in r.stdout.replace("NOT ACCEPTED", "")
    assert state_bytes(st) == before


def test_add_malformed_v1_without_ssh_keygen_is_could_not_look(kit):
    pkg, sig, log, st = seeded(kit)
    before = state_bytes(st)
    p = json.loads(pkg.read_text(encoding="utf-8"))
    p["provenance"]["chain"] = "x"
    bad, bsig = kit.pkg("bad.json", pkg=reseal(p))
    r = kit.accept(bad, bsig, log, st, env=dict(os.environ, PATH=str(kit.d / "empty-path")))
    assert r.returncode == 2 and "COULD NOT LOOK" in r.stdout and no_traceback(r)
    assert state_bytes(st) == before
