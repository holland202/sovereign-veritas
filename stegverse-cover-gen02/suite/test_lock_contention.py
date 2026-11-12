"""Lock contention test for the GEN 02 transition ledger (StegVerse Build Lane).

GEN 01's ledger claimed its duplicate refusal was atomic "under an OS file
lock — for every caller", but on Windows the lock was never taken (msvcrt
imported, never called). GEN 02 implements the lock on both platforms
through _lock_exclusive. This test exercises the claim at the level it is
made: separate PROCESSES, one ledger file, one record_id.

    L1  eight processes race begin("race-record") against one ledger:
        exactly one is admitted, the other seven are refused, and the
        ledger on disk afterwards carries exactly one INTENT for the
        record, with a chain that verifies on reload.
    L2  after the race, a fresh process attempting the same record_id is
        still refused — the refusal is durable, not a memory artifact.

Run like the covering probe, from anywhere, with a Sovereign Veritas
checkout on the path (the ledger imports its canonical_json):

    PYTHONPATH=<sovereign-veritas>:<suite dir> python3 test_lock_contention.py

The package under test is assembled from THIS SUITE's flat members into a
temporary sv_transition_cover/ directory, exactly as COVER__PACKAGE__01.md
describes — so the test exercises the suite as shipped, not a build tree.

Platform scope, stated plainly: on POSIX this exercises fcntl.flock; on
Windows it exercises the same code through msvcrt.locking. A run proves
the platform it runs on. GEN 02's author-side run was on Linux (POSIX);
the Windows path is verified by construction — one helper, both branches
implemented, no platform branch that skips the lock — and stands open for
the subject's reproduction on Windows.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent

WORKER = """
import sys
from sv_transition_cover import TransitionLedger
try:
    TransitionLedger(sys.argv[1]).begin("race-record", "digest-race")
    print("ADMITTED")
except ValueError:
    print("REFUSED")
"""

INIT = """from .guarded_workflow import TransitionExecutor, TransitionSink, run_guarded
from .transition_ledger import TransitionLedger
"""

RESULTS: list[tuple[str, bool, str]] = []


def case(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))
    print(f"{'ok  ' if ok else 'FAIL'} {name}  {detail}")


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="sv-lock-test-"))
    pkg = tmp / "sv_transition_cover"
    pkg.mkdir()
    for f in ("transition_ledger.py", "guarded_workflow.py", "verify_transition.py"):
        shutil.copy(HERE / f, pkg / f)
    (pkg / "__init__.py").write_text(INIT, encoding="utf-8")
    worker = tmp / "worker.py"
    worker.write_text(WORKER, encoding="utf-8")
    ledger = tmp / "ledger.jsonl"

    import os
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(tmp)] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))

    def run_worker() -> str:
        r = subprocess.run([sys.executable, str(worker), str(ledger)],
                           capture_output=True, text=True, env=env, timeout=120)
        return r.stdout.strip()

    # L1 — the race: launch all eight before collecting any.
    procs = [subprocess.Popen([sys.executable, str(worker), str(ledger)],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True, env=env) for _ in range(8)]
    outcomes = []
    for p in procs:
        out, _ = p.communicate(timeout=180)
        outcomes.append(out.strip())
    admitted = outcomes.count("ADMITTED")
    refused = outcomes.count("REFUSED")
    lines = [ln for ln in ledger.read_text(encoding="utf-8").splitlines() if ln.strip()]
    import json
    intents = [json.loads(ln) for ln in lines
               if json.loads(ln).get("kind") == "INTENT"
               and json.loads(ln).get("record_id") == "race-record"]
    chain_ok = True
    try:
        sys.path.insert(0, str(tmp))
        from sv_transition_cover import TransitionLedger as TL
        TL(ledger)  # reload verifies the hash chain
    except Exception as exc:  # noqa: BLE001
        chain_ok = False
        print("   chain reload raised:", exc)
    case("L1 eight processes, one record_id: exactly one admitted",
         admitted == 1 and refused == 7 and len(intents) == 1 and chain_ok,
         f"admitted={admitted} refused={refused} intents_on_disk={len(intents)} chain_ok={chain_ok}")

    # L2 — durability: a fresh process still cannot claim the record.
    out = run_worker()
    case("L2 fresh process after the race: still refused", out == "REFUSED", f"outcome={out}")

    bad = [n for n, ok, _ in RESULTS if not ok]
    print(f"LOCK VERDICT  {'PASS' if not bad else 'FAIL'} - {len(RESULTS) - len(bad)}/{len(RESULTS)} as registered")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
