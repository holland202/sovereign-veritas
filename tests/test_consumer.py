"""tools/consumer.py: act once, never go backwards (round 3, docs/ATTACK_HARNESS.md P13-P15).

P-001 (2026-10-09): the consumer now accepts only signed sv.package/1 (W1/W2). These three tests
keep their original intent (replay refused, rollback refused, unreadable log is COULD NOT LOOK) but
run on kernel-built v1 packages signed with a throwaway key. They previously consumed unsigned
sv.package/0 files from runs/, which the hardened consumer refuses by design. The frozen acceptance
cases live in tests/test_p001_w1.py and tests/test_p001_w2.py.
"""
from p001_support import Kit, needs_ssh, write_log

pytestmark = needs_ssh


def test_accept_once_then_refuse_replay(tmp_path):
    k = Kit(tmp_path)
    old, _ = k.pkg("old.json", {"steps": 1})
    pkg, sig = k.pkg("pkg.json", {"steps": 2})
    log, st = write_log(tmp_path / "w.log", [old, pkg]), tmp_path / "s.json"
    r1 = k.accept(pkg, sig, log, st)
    assert r1.returncode == 0, r1.stdout + r1.stderr
    assert "CONSUMER  ACCEPTED" in r1.stdout
    r2 = k.accept(pkg, sig, log, st)
    assert r2.returncode == 1, r2.stdout + r2.stderr
    assert "replay" in r2.stdout and "REFUSED" in r2.stdout


def test_rollback_after_seeing_more_is_refused(tmp_path):
    k = Kit(tmp_path)
    old, _ = k.pkg("old.json", {"steps": 1})
    pkg, sig = k.pkg("pkg.json", {"steps": 2})
    third, sig3 = k.pkg("third.json", {"thermal": "hot"})
    st = tmp_path / "s.json"
    assert k.accept(third, sig3, write_log(tmp_path / "full.log", [old, pkg, third]), st).returncode == 0
    r = k.accept(pkg, sig, write_log(tmp_path / "short.log", [old, pkg]), st)
    assert r.returncode == 1, r.stdout
    assert "rollback" in r.stdout.lower() and "REFUSED" in r.stdout


def test_garbage_log_is_unreadable(tmp_path):
    k = Kit(tmp_path)
    pkg, sig = k.pkg("pkg.json")
    log, st = tmp_path / "w.log", tmp_path / "s.json"
    log.write_text("not a witness log\n", encoding="utf-8")
    r = k.accept(pkg, sig, log, st)
    assert r.returncode == 2
    assert "COULD NOT LOOK" in r.stdout
