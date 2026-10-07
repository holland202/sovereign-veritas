"""Regressions for an independent adversarial review of 48ab26a (docs/REVIEW_2026-10-07.md). Each test fails on the
code the reviewer attacked and passes after the fix. Finding numbers are the reviewer's."""
import hashlib
import json
import math
import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from sovereign_veritas import anchored_file_ledger as afl
from sovereign_veritas.anchored_file_ledger import AnchoredFileLedger
from sovereign_veritas.capability import Capability
from sovereign_veritas.evidence import Ledger, LedgerSink
from sovereign_veritas.idempotency import FileReservations, ReservationRefused
from sovereign_veritas.interfaces.contracts import ActionProposal, Prediction
from sovereign_veritas.runtime import RuntimeState
from sovereign_veritas.workflow import EvidenceWorkflow

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "runs" / "vehicle_sitl_v13" / "sv_package_a911244dfcf7.json"
CONSUMER, VERIFIER = ROOT / "tools" / "consumer.py", ROOT / "tools" / "verify_package.py"


class _S:
    def observe(self):
        return b"x"

    def predict(self, o):
        return Prediction(value=1)

    def verify(self, o, p):
        return {"status": "PASS"}


class _Ex:
    def __init__(self, effects, raise_first=False, gate=None, entered=None):
        self.effects, self.raise_first, self.gate, self.entered = effects, raise_first, gate, entered

    def execute(self, action):
        if self.raise_first:
            raise TimeoutError("network down before the request left")
        if self.entered:
            self.entered.set()
        if self.gate:
            self.gate.wait(10)
        self.effects.append(threading.current_thread().name)
        return "ok"


CAP, RT = Capability("pay", authorized=True), RuntimeState("x", "3")
ACT = ActionProposal("pay", "transfer", {"amount": 100})


def _wf(sink, ex, store=None):
    return EvidenceWorkflow(sensor=_S(), predictor=_S(), verifier=_S(), executor=ex, evidence_sink=sink, reservations=store)


@pytest.mark.skipif(afl.fcntl is None, reason="AnchoredFileLedger is POSIX-only (fcntl.flock); on Windows it refuses to "
                                              "run, pinned on every platform by the test below and by "
                                              "test_anchored_file_ledger_platform.py")
def test_f2_a_second_ledger_instance_sees_the_first_ones_record_before_executing(tmp_path):
    path, effects = tmp_path / "ledger.jsonl", []
    worker_a, worker_b = LedgerSink(AnchoredFileLedger(path)), LedgerSink(AnchoredFileLedger(path))
    _wf(worker_a, _Ex(effects)).run(record_id="txn-42", input_digest="d", capability=CAP, runtime=RT, action=ACT)
    assert worker_b.has_record("txn-42")
    with pytest.raises(ValueError, match="duplicate record_id refused before execution"):
        _wf(worker_b, _Ex(effects)).run(record_id="txn-42", input_digest="d", capability=CAP, runtime=RT, action=ACT)
    assert len(effects) == 1


def test_f2_without_flock_the_refusal_comes_before_the_effect(tmp_path, monkeypatch):
    """Found by CI on windows-latest at b7d072b: contains() now reads under the lock, so without fcntl the anchored
    ledger refuses at the duplicate check, before execute(); before that fix the refusal came at append, after the
    effect. Runs on every platform by removing fcntl."""
    monkeypatch.setattr(afl, "fcntl", None)
    effects = []
    with pytest.raises(RuntimeError, match="requires fcntl.flock"):
        _wf(LedgerSink(AnchoredFileLedger(tmp_path / "ledger.jsonl")), _Ex(effects)).run(
            record_id="txn-42", input_digest="d", capability=CAP, runtime=RT, action=ACT)
    assert effects == []


@pytest.mark.parametrize("rid,digest", [("", "d"), ("r", ""), (None, "d"), (7, "d")])
def test_f2b_an_unrecordable_record_id_is_refused_before_execution(rid, digest):
    effects = []
    with pytest.raises(ValueError, match="before execution"):
        _wf(LedgerSink(Ledger()), _Ex(effects)).run(record_id=rid, input_digest=digest, capability=CAP, runtime=RT,
                                                    action=ACT)
    assert effects == []


def test_f5_racing_releases_never_free_a_key_twice(tmp_path, monkeypatch):
    store, key, effects = FileReservations(tmp_path / "res"), "invoice-7-pay", []
    sink = LedgerSink(Ledger())
    with pytest.raises(TimeoutError):
        _wf(sink, _Ex(effects, raise_first=True), store).run(record_id="a0", input_digest="d", capability=CAP,
                                                             runtime=RT, action=ACT, idempotency_key=key)
    assert store.state(key) == "UNKNOWN"
    orig_write, b_paused, b_go = FileReservations._write, threading.Event(), threading.Event()

    def write_hook(self, k, entry):
        if threading.current_thread().name == "release-B":
            b_paused.set()
            b_go.wait(10)
        return orig_write(self, k, entry)
    monkeypatch.setattr(FileReservations, "_write", write_hook)
    outcomes = {}

    def release(name):
        try:
            store.release(key, by=name, reason="no charge seen")
            outcomes[name] = "released"
        except ValueError:
            outcomes[name] = "refused"
    tb = threading.Thread(name="release-B", target=release, args=("bob",))
    tb.start()
    assert b_paused.wait(5)
    ta = threading.Thread(name="release-A", target=release, args=("alice",))
    ta.start()
    ta.join(0.5)  # unfixed: A completes while B is paused; fixed: A waits for B's lock

    r1_entered, r1_go = threading.Event(), threading.Event()

    def retry(name, ex):
        try:
            _wf(sink, ex, store).run(record_id=name, input_digest="d", capability=CAP, runtime=RT, action=ACT,
                                     idempotency_key=key)
        except ReservationRefused:
            pass
    t1 = threading.Thread(name="retry-R1", target=retry, args=("r1", _Ex(effects, gate=r1_go, entered=r1_entered)))
    t1.start()
    r1_entered.wait(1)
    b_go.set()
    tb.join(10)
    ta.join(10)
    retry("r2", _Ex(effects))
    r1_go.set()
    t1.join(10)
    assert len(effects) <= 1, (effects, outcomes)
    assert sorted(outcomes.values()) == ["refused", "released"]


def _log(tmp_path):
    dig = json.loads(PKG.read_text())["package_sha256"]
    log = tmp_path / "w.log"
    log.write_text(f"# sv witness log v0\n1 {dig}\n", encoding="utf-8", newline="\n")
    return log


def _consume(*args):
    return subprocess.run([sys.executable, str(CONSUMER), "accept", str(PKG), *map(str, args)], capture_output=True,
                          text=True)


@pytest.mark.skipif(not hasattr(os, "symlink") or sys.platform == "win32", reason="symlinks need POSIX here")
def test_f4_a_symlinked_state_path_is_one_state(tmp_path):
    log = _log(tmp_path)
    (tmp_path / "state.json").write_text('{"consumed": [], "anchor": null}', encoding="utf-8")
    os.symlink("state.json", tmp_path / "link.json")
    assert _consume("--witness-log", log, "--state", tmp_path / "link.json").returncode == 0
    assert (tmp_path / "link.json").is_symlink()
    assert _consume("--witness-log", log, "--state", tmp_path / "state.json").returncode == 1


@pytest.mark.parametrize("given", [("--allowed-signers", "keys/allowed_signers", "--identity", "holland202"),
                                   ("--signature", "x.sig"), ("--identity", "holland202")])
def test_f3_partial_signature_options_are_a_usage_error_not_a_silent_skip(tmp_path, given):
    r = _consume("--witness-log", _log(tmp_path), "--state", tmp_path / "s.json", *given)
    assert r.returncode == 2, r.stdout + r.stderr
    assert not (tmp_path / "s.json").exists()


def _canon(v):
    return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _verify_text(tmp_path, text):
    path = tmp_path / "p.json"
    path.write_text(text, encoding="utf-8")
    return subprocess.run([sys.executable, str(VERIFIER), str(path)], capture_output=True, text=True)


def test_f6a_an_overflowing_float_literal_is_refused_like_infinity(tmp_path):
    pkg = json.loads(PKG.read_text())
    pkg["provenance"]["chain"][-1]["record"]["metadata"]["note"] = "__X__"
    text = _canon(pkg).replace('"__X__"', "1e400")
    r = _verify_text(tmp_path, text)
    assert r.returncode == 2 and "COULD NOT LOOK" in r.stdout, r.stdout


def test_f6b_an_unrepresentable_quality_floor_is_could_not_look_not_a_crash(tmp_path):
    pkg = json.loads(PKG.read_text())
    pkg["gate_inputs"]["capability"]["min_evidence_quality"] = 10 ** 400
    body = {k: v for k, v in pkg.items() if k != "package_sha256"}
    pkg["package_sha256"] = hashlib.sha256(_canon(body).encode()).hexdigest()
    r = _verify_text(tmp_path, _canon(pkg))
    assert r.returncode == 2 and "COULD NOT LOOK" in r.stdout, r.stdout + r.stderr
