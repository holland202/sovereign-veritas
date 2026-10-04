"""RK-2 (docs/RK2_PREREG.md): reserved idempotency keys. Pins the registered outcome of tools/rk2_probe.py."""
import os
import subprocess
import sys
import threading

import pytest

from sovereign_veritas.capability import Capability
from sovereign_veritas.evidence import Ledger, LedgerSink
from sovereign_veritas.idempotency import (COMPLETED, IN_FLIGHT, UNKNOWN, FileReservations, MemoryReservations,
                                           ReservationRefused)
from sovereign_veritas.interfaces.contracts import ActionProposal, Prediction
from sovereign_veritas.runtime import RuntimeState
from sovereign_veritas.workflow import EvidenceWorkflow

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class _S:
    def observe(self):
        return "o"


class _P:
    def predict(self, o):
        return Prediction(value="p", uncertainty=0.1, model_id="t")


class _V:
    def verify(self, o, p):
        return {"status": "PASS"}


class _Ex:
    def __init__(self, lose_first=False):
        self.effects, self.lose_first = 0, lose_first

    def execute(self, action):
        self.effects += 1
        if self.lose_first and self.effects == 1:
            raise TimeoutError("response lost")
        return {"ok": True}


def _run(sink, ex, store, rid, key):
    wf = EvidenceWorkflow(sensor=_S(), predictor=_P(), verifier=_V(), executor=ex, evidence_sink=sink,
                          reservations=store)
    return wf.run(record_id=rid, input_digest="abc", capability=Capability("read_only", True, ("fresh",)),
                  runtime=RuntimeState(platform="t", python_version="3"),
                  action=ActionProposal(capability="read_only", requested="read", parameters={}),
                  metadata={"fresh": True}, idempotency_key=key)


@pytest.fixture(params=["memory", "file"])
def store(request, tmp_path):
    return MemoryReservations() if request.param == "memory" else FileReservations(tmp_path / "res")


def test_fresh_record_id_same_key_runs_once_and_records_unknown(store):
    sink, ex = LedgerSink(Ledger()), _Ex(lose_first=True)
    with pytest.raises(TimeoutError):
        _run(sink, ex, store, "r1", "K")
    with pytest.raises(ReservationRefused):
        _run(sink, ex, store, "r2", "K")
    assert ex.effects == 1
    assert [r.metadata["execution_status"] for r in sink.ledger.all()] == ["UNKNOWN"]
    assert store.state("K") == UNKNOWN


def test_fresh_key_per_attempt_is_not_protected_stated_limit(store):
    sink, ex = LedgerSink(Ledger()), _Ex(lose_first=True)
    with pytest.raises(TimeoutError):
        _run(sink, ex, store, "r1", "K1")
    _run(sink, ex, store, "r2", "K2")
    assert ex.effects == 2


def test_completed_key_is_refused_and_success_records_key(store):
    sink, ex = LedgerSink(Ledger()), _Ex()
    _run(sink, ex, store, "r1", "K")
    assert store.state("K") == COMPLETED
    assert sink.ledger.all()[0].metadata["idempotency_key"] == "K"
    with pytest.raises(ReservationRefused):
        _run(sink, ex, store, "r2", "K")
    assert ex.effects == 1


def test_expired_lease_becomes_unknown_and_is_still_refused(store):
    store.reserve("K", lease_s=0)
    with pytest.raises(ReservationRefused, match="UNKNOWN"):
        _run(LedgerSink(Ledger()), _Ex(), store, "r", "K")
    store2 = MemoryReservations()
    store2.reserve("K", lease_s=60)
    assert store2.state("K") == IN_FLIGHT


def test_release_only_from_unknown_and_kept_in_history(store):
    sink, ex = LedgerSink(Ledger()), _Ex()
    _run(sink, ex, store, "r1", "K")
    with pytest.raises(ValueError):
        store.release("K", by="op", reason="x")  # COMPLETED cannot be released
    s2, ex2 = LedgerSink(Ledger()), _Ex(lose_first=True)
    with pytest.raises(TimeoutError):
        _run(s2, ex2, store, "a", "J")
    store.release("J", by="op", reason="checked")
    _run(s2, ex2, store, "b", "J")
    assert ex2.effects == 2 and store.released_history("J")[0][-1]["to"] == "RELEASED"


def test_key_without_store_refused_before_execution():
    ex = _Ex()
    with pytest.raises(ValueError, match="no reservation store"):
        _run(LedgerSink(Ledger()), ex, None, "r", "K")
    assert ex.effects == 0


def test_file_store_claim_is_exclusive_across_objects(tmp_path):
    wins = []
    def claim():
        try:
            FileReservations(tmp_path / "res").reserve("K")
            wins.append(1)
        except ReservationRefused:
            pass
    ts = [threading.Thread(target=claim) for _ in range(8)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert len(wins) == 1


def test_no_key_path_unchanged_failed_label():
    sink, ex = LedgerSink(Ledger()), _Ex(lose_first=True)
    with pytest.raises(TimeoutError):
        _run(sink, ex, None, "r", None)
    assert sink.ledger.all()[0].metadata["execution_status"] == "FAILED"
    assert "idempotency_key" not in sink.ledger.all()[0].metadata


def test_rk2_probe_registered_outcome_and_sabotage():
    ok = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "rk2_probe.py")], capture_output=True, text=True)
    assert ok.returncode == 0, ok.stdout[-800:]
    sab = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "rk2_probe.py"), "--sabotage"],
                         capture_output=True, text=True)
    assert sab.returncode == 1, sab.stdout[-800:]


@pytest.mark.parametrize("make", [lambda p: MemoryReservations(), lambda p: FileReservations(p / "r")])
def test_keys_compared_byte_for_byte_no_unicode_normalization(tmp_path, make):
    """Documents a limit found 2026-10-04 (JG-2 Amendment 1): the same visible key in two Unicode forms is two
    keys, so a caller that re-normalizes its key between attempts can run the action twice. Both stores agree."""
    import unicodedata
    nfc, nfd = unicodedata.normalize("NFC", "café"), unicodedata.normalize("NFD", "café")
    assert nfc != nfd
    store = make(tmp_path)
    store.reserve(nfc)
    store.reserve(nfd)  # not refused: a second, separate reservation
    with pytest.raises(ReservationRefused):
        store.reserve(nfc)  # the exact same bytes are still refused


# RK-3 (docs/RK3_PREREG.md)

def test_rk3_reserve_never_writes_an_existing_key(tmp_path):
    store = FileReservations(tmp_path / "res")
    store.reserve("K", lease_s=0)
    path = store._path("K")
    before = path.read_bytes()
    with pytest.raises(ReservationRefused, match="UNKNOWN"):
        store.reserve("K")
    assert path.read_bytes() == before  # expiry is derived, so a late complete() cannot be overwritten


def test_rk3_late_holder_is_recorded_not_obeyed(store):
    old = store.reserve("K", lease_s=0)
    store.release("K", by="op", reason="checked")
    new = store.reserve("K", lease_s=60)
    store.complete("K", token=old)  # the released holder finishes late
    assert store.state("K") == IN_FLIGHT  # the current holder's entry is untouched
    [ev] = store.late_events("K")
    assert ev["event"] == "late_complete" and ev["late_token"] == old and ev["current_token"] == new
    store.complete("K", token=new)
    assert store.state("K") == COMPLETED


def test_rk3_release_records_the_derived_expiry(store):
    store.reserve("K", lease_s=0)
    store.release("K", by="op", reason="checked")
    assert [h["to"] for h in store.released_history("K")[0]] == [IN_FLIGHT, UNKNOWN, "RELEASED"]


def test_rk3_run_passes_the_lease(store):
    wf = EvidenceWorkflow(sensor=_S(), predictor=_P(), verifier=_V(), executor=_Ex(), evidence_sink=LedgerSink(Ledger()),
                          reservations=store)
    seen = {}
    real = store.reserve
    store.reserve = lambda key, lease_s=30.0: seen.setdefault("lease", lease_s) and real(key, lease_s)
    wf.run(record_id="r", input_digest="abc", capability=Capability("read_only", True, ("fresh",)),
           runtime=RuntimeState(platform="t", python_version="3"),
           action=ActionProposal(capability="read_only", requested="read", parameters={}),
           metadata={"fresh": True}, idempotency_key="K", lease_s=5.0)
    assert seen["lease"] == 5.0 and store.state("K") == COMPLETED
