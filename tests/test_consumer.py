import json, os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT / "runs" / "vehicle_sitl_v12" / "sv_package_1506bcc87b3f.json"
PKG = ROOT / "runs" / "vehicle_sitl_v13" / "sv_package_a911244dfcf7.json"
THIRD = ROOT / "runs" / "vehicle_sitl" / "sv_package_aa2fd72afe52.json"
CONSUMER = ROOT / "tools" / "consumer.py"


def digest(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))["package_sha256"]


def run(pkg, log, state):
    return subprocess.run(
        [sys.executable, str(CONSUMER), "accept", str(pkg),
         "--witness-log", str(log), "--state", str(state)],
        capture_output=True, text=True,
    )


def write_log(path, pkgs):
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("# sv witness log v0\n" + "".join(f"{i} {digest(p)}\n" for i, p in enumerate(pkgs, 1)))


def test_accept_once_then_refuse_replay(tmp_path):
    log, st = tmp_path / "w.log", tmp_path / "s.json"
    write_log(log, [OLD, PKG])
    r1 = run(PKG, log, st)
    assert r1.returncode == 0, r1.stdout + r1.stderr
    assert "CONSUMER  ACCEPTED" in r1.stdout
    r2 = run(PKG, log, st)
    assert r2.returncode == 1, r2.stdout + r2.stderr
    assert "already accepted" in r2.stdout or "REFUSED" in r2.stdout


def test_rollback_after_seeing_more_is_refused(tmp_path):
    log, st = tmp_path / "full.log", tmp_path / "s.json"
    write_log(log, [OLD, PKG, THIRD])
    assert run(THIRD, log, st).returncode == 0
    short = tmp_path / "short.log"
    write_log(short, [OLD, PKG])
    r = run(PKG, short, st)
    assert r.returncode == 1, r.stdout
    assert "rollback" in r.stdout.lower() or "REFUSED" in r.stdout


def test_garbage_log_is_unreadable(tmp_path):
    log, st = tmp_path / "w.log", tmp_path / "s.json"
    log.write_text("not a witness log\n", encoding="utf-8")
    r = run(PKG, log, st)
    assert r.returncode == 2
    assert "COULD NOT LOOK" in r.stdout or "WitnessUnreadable" in r.stdout


# RP-1 (docs/RP1_RESULTS.md, P6/P7): load-check-write on the state file had no lock. A forced
# interleaving doubled 100% of trials in manual reproduction (consumer.py's own `load_state`
# monkeypatched to pause between the read and the write, the same technique
# tools/rp1_vectors.py's P7c control uses). This is the regression test for the fix: it fails
# (doubled >= 1) against the pre-fix consumer.py and must report 0 doubled after the fix.
PAUSED_CONSUMER = r"""
import importlib.util, sys, time
spec = importlib.util.spec_from_file_location("c", "tools/consumer.py")
c = importlib.util.module_from_spec(spec); spec.loader.exec_module(c)
orig = c.load_state
def paused(p):
    s = orig(p); time.sleep(0.2); return s
c.load_state = paused
sys.argv = ["consumer.py"] + sys.argv[1:]
c.main()
"""


def test_concurrent_accepts_do_not_double(tmp_path):
    log, st = tmp_path / "w.log", tmp_path / "s.json"
    write_log(log, [OLD, PKG])
    trials, procs, doubled, errors = 8, 6, 0, 0
    for t in range(trials):
        state = tmp_path / f"race_{t}.state.json"
        args = [sys.executable, "-c", PAUSED_CONSUMER, "accept", str(PKG),
                "--witness-log", str(log), "--state", str(state)]
        ps = [subprocess.Popen(args, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
              for _ in range(procs)]
        outs = [p.communicate()[0] for p in ps]
        codes = [p.returncode for p in ps]
        if any(c not in (0, 1) for c in codes):
            errors += 1
        if codes.count(0) >= 2:
            doubled += 1
    assert errors == 0, "every process must exit 0 (accepted) or 1 (refused), never crash"
    assert doubled == 0, "no trial may accept the same package twice under a forced interleaving"


# K1 (docs/RP1_FIX_RESULTS.md, addendum): the 7a03566 lock was an O_EXCL lock file, so a consumer killed while holding it
# left the file behind and every later consumer timed out (COULD NOT LOOK) until a person deleted it. The lock must be
# released by the operating system when its holder dies.
HOLDING_CONSUMER = r"""
import importlib.util, sys, time
spec = importlib.util.spec_from_file_location("c", "tools/consumer.py")
c = importlib.util.module_from_spec(spec); spec.loader.exec_module(c)
orig = c.load_state
def hang(p):
    s = orig(p); print("HOLDING", flush=True); time.sleep(60); return s
c.load_state = hang
sys.argv = ["consumer.py"] + sys.argv[1:]
c.main()
"""


def test_a_killed_lock_holder_does_not_block_the_next_consumer(tmp_path):
    import signal
    import time
    log, st = tmp_path / "w.log", tmp_path / "s.json"
    write_log(log, [OLD, PKG])
    holder = subprocess.Popen([sys.executable, "-c", HOLDING_CONSUMER, "accept", str(PKG), "--witness-log", str(log),
                               "--state", str(st)], cwd=ROOT, stdout=subprocess.PIPE, text=True)
    assert holder.stdout.readline().strip() == "HOLDING"
    holder.send_signal(signal.SIGKILL if hasattr(signal, "SIGKILL") else signal.SIGTERM)
    holder.wait()
    t0 = time.monotonic()
    r = run(PKG, log, st)
    assert r.returncode == 0, r.stdout
    assert time.monotonic() - t0 < 10
    assert run(PKG, log, st).returncode == 1  # still at most once
