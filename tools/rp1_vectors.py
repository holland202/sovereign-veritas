#!/usr/bin/env python3
"""rp1_vectors.py - relying-party replay vectors (docs/RP1_PREREG.md).

Runs accepting/refusing vector pairs through the real tools/verify_package.py, tools/consumer.py and
tools/witness.py, writes each vector's inputs to results/rp1/vectors/<id>/ with a vector.json, and judges
P1-P9 as registered.

  python tools/rp1_vectors.py            # the registered run
  python tools/rp1_vectors.py --flip     # P9: invert P2's expected exits; must report REFUTED and exit 1

Exit: 0 all held | 1 something refuted | 2 could not run. Linux; stdlib only.
"""
import glob, importlib.util, json, os, shutil, subprocess, sys, tempfile, time

sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join("results", "rp1", "vectors")  # relative to ROOT, so vector.json commands rerun from ROOT
PY = sys.executable
FLIP = "--flip" in sys.argv
TRIALS_P7, PROCS_P7, TRIALS_P7C, PAUSE_P7C = 100, 8, 20, 0.2


def could_not_run(msg):
    print("COULD NOT RUN", msg)
    sys.exit(2)


def run(args):
    p = subprocess.run([PY] + args, cwd=ROOT, capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def rel(*parts):
    return os.path.join(OUT, *parts)


def make_package(dest):
    """One real make_package.py run (same seed and action every time); returns the path under ROOT."""
    home = tempfile.mkdtemp()
    env = dict(os.environ, HOME=home)
    p = subprocess.run([PY, "tools/make_package.py", "--rounds", "1000", "--thermal-status", "normal",
                        "--seed", "rp1"], cwd=ROOT, capture_output=True, text=True, env=env)
    made = glob.glob(os.path.join(home, "sv_package_*.json"))
    if p.returncode != 0 or len(made) != 1 or "decision ALLOW" not in p.stdout:
        could_not_run(f"make_package failed: {p.stdout}{p.stderr}")
    shutil.move(made[0], os.path.join(ROOT, dest))
    shutil.rmtree(home)
    return dest


class Vector:
    def __init__(self, vid, title):
        self.vid, self.title, self.steps = vid, title, []
        os.makedirs(os.path.join(ROOT, rel(vid)), exist_ok=True)

    def path(self, name):
        return rel(self.vid, name)

    def copy_in(self, src, name):
        shutil.copy(os.path.join(ROOT, src), os.path.join(ROOT, self.path(name)))
        return self.path(name)

    def step(self, label, args, expect_exit, expect_sub):
        code, out = run(args)
        ok = code == expect_exit and expect_sub in out
        last = [l for l in out.strip().splitlines() if l.strip()]
        self.steps.append({"label": label, "command": "python " + " ".join(args), "expected_exit": expect_exit,
                           "expected_substring": expect_sub, "observed_exit": code, "as_expected": ok})
        print(f"  {self.vid} {label:<44} exit {code} (expected {expect_exit}) {'ok' if ok else 'NOT AS EXPECTED'}"
              f" | {last[-1] if last else ''}")
        return code, out

    def save(self, extra=None):
        doc = {"id": self.vid, "title": self.title, "baseline": "sovereign-veritas main 16850f6",
               "note": "Run from the repository root. Consumer state files start absent; delete *.state.json to rerun.",
               "steps": self.steps, **(extra or {})}
        with open(os.path.join(ROOT, self.path("vector.json")), "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=1)
        for f in glob.glob(os.path.join(ROOT, self.path("*.state.json"))):  # keep the evidence, reset the input
            os.replace(f, f.replace(".state.json", ".state.after.json"))


def consumer(pkg, log, state):
    return ["tools/consumer.py", "accept", pkg, "--witness-log", log, "--state", state]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


PAUSED_CONSUMER = r"""
import importlib.util, sys, time
spec = importlib.util.spec_from_file_location("c", "tools/consumer.py")
c = importlib.util.module_from_spec(spec); spec.loader.exec_module(c)
orig = c.load_state
def paused(p):
    s = orig(p); time.sleep(%s); return s
c.load_state = paused
sys.argv = ["consumer.py"] + sys.argv[1:]
c.main()
""" % PAUSE_P7C


def race(trials, procs, pkg, log, workdir, paused=False):
    doubled = zero = errors = 0
    for t in range(trials):
        state = os.path.join(workdir, f"race_{t}.state.json")
        args = (["-c", PAUSED_CONSUMER] if paused else ["tools/consumer.py"]) + \
               ["accept", pkg, "--witness-log", log, "--state", state]
        ps = [subprocess.Popen([PY] + args, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
              for _ in range(procs)]
        codes = [p.wait() for p in ps]
        accepted = codes.count(0)
        if any(c not in (0, 1) for c in codes):
            errors += 1
        if accepted >= 2:
            doubled += 1
        if accepted == 0:
            zero += 1
        if os.path.exists(os.path.join(ROOT, state)):
            os.remove(os.path.join(ROOT, state))
    return doubled, zero, errors


def main():
    if os.path.exists(os.path.join(ROOT, OUT)):
        shutil.rmtree(os.path.join(ROOT, OUT))
    pool = rel("_pool")
    os.makedirs(os.path.join(ROOT, pool))
    A = make_package(os.path.join(pool, "A.json"))
    B = make_package(os.path.join(pool, "B.json"))
    pa, pb = (json.load(open(os.path.join(ROOT, p))) for p in (A, B))
    same_action = (pa["artifact"]["sha256"] == pb["artifact"]["sha256"]
                   and pa["gate_inputs"] == pb["gate_inputs"] and pa["decision"] == pb["decision"])
    print(f"A {pa['package_sha256'][:12]}  B {pb['package_sha256'][:12]}  same artifact, gate inputs and decision: "
          f"{same_action}  decision {pa['decision']['decision']}")
    if not same_action or pa["package_sha256"] == pb["package_sha256"]:
        could_not_run("A and B are not two packages for one action")
    log = os.path.join(pool, "witness.txt")
    for p in (A,):
        code, out = run(["tools/witness.py", "append", p, "--log", log])
        if code != 0:
            could_not_run(out)
    shutil.copy(os.path.join(ROOT, log), os.path.join(ROOT, pool, "log_A.txt"))
    code, out = run(["tools/witness.py", "append", B, "--log", log])
    if code != 0:
        could_not_run(out)
    shutil.copy(os.path.join(ROOT, log), os.path.join(ROOT, pool, "log_AB.txt"))
    os.remove(os.path.join(ROOT, log))
    LA, LAB = os.path.join(pool, "log_A.txt"), os.path.join(pool, "log_AB.txt")
    verdict = {}

    # P1 re-verify
    v = Vector("P1", "verifying the same package again is not an error; a changed decision is")
    a = v.copy_in(A, "A.json")
    t = json.load(open(os.path.join(ROOT, a)))
    t["decision"]["decision"] = "REFUSE"
    with open(os.path.join(ROOT, v.path("A_decision_changed.json")), "w", encoding="utf-8") as fh:
        json.dump(t, fh)
    c1, o1 = v.step("verify A", ["tools/verify_package.py", a], 0, "VERDICT  CONSISTENT")
    c2, o2 = v.step("verify A again", ["tools/verify_package.py", a], 0, "VERDICT  CONSISTENT")
    c3, _ = v.step("verify A with decision changed", ["tools/verify_package.py", v.path("A_decision_changed.json")],
                   1, "VERDICT")
    v.save({"identical_output": o1 == o2})
    verdict["P1"] = c1 == 0 and c2 == 0 and o1 == o2 and c3 == 1

    # P2 replay
    v = Vector("P2", "the consumer refuses the same package a second time and leaves its state unchanged")
    a, la, s = v.copy_in(A, "A.json"), v.copy_in(LA, "log_A.txt"), v.path("S.state.json")
    e1, e2 = (1, 0) if FLIP else (0, 1)
    c1, _ = v.step("accept A, fresh state", consumer(a, la, s), e1, "CONSUMER")
    before = open(os.path.join(ROOT, s), "rb").read() if os.path.exists(os.path.join(ROOT, s)) else None
    c2, o2 = v.step("accept A again, same state", consumer(a, la, s), e2, "replay" if not FLIP else "CONSUMER")
    after = open(os.path.join(ROOT, s), "rb").read() if os.path.exists(os.path.join(ROOT, s)) else None
    v.save({"state_unchanged_by_refusal": before == after, "flipped": FLIP})
    verdict["P2"] = (c1, c2) == (e1, e2) and (FLIP or ("replay" in o2 and before == after))

    # P3 same action, second package
    v = Vector("P3", "a second package for the same action is accepted: at-most-once is per package, not per action")
    a, b = v.copy_in(A, "A.json"), v.copy_in(B, "B.json")
    la, lab, s = v.copy_in(LA, "log_A.txt"), v.copy_in(LAB, "log_AB.txt"), v.path("S.state.json")
    c1, _ = v.step("accept A (log: A)", consumer(a, la, s), 0, "ACCEPTED")
    c2, _ = v.step("accept B, same action (log: A,B), same state", consumer(b, lab, s), 0, "ACCEPTED")
    c3, _ = v.step("accept A again (log: A,B), same state", consumer(a, lab, s), 1, "replay")
    v.save({"same_artifact_gate_inputs_and_decision": same_action})
    verdict["P3"] = (c1, c2, c3) == (0, 0, 1)

    # P4 relative order
    v = Vector("P4", "staleness is order in the author's log, not whether this package was acted on")
    a, la, lab = v.copy_in(A, "A.json"), v.copy_in(LA, "log_A.txt"), v.copy_in(LAB, "log_AB.txt")
    c1, _ = v.step("A latest, fresh consumer S1", consumer(a, la, v.path("S1.state.json")), 0, "ACCEPTED")
    c2, _ = v.step("A after B witnessed, fresh consumer S2", consumer(a, lab, v.path("S2.state.json")), 1, "STALE")
    v.save()
    verdict["P4"] = (c1, c2) == (0, 1)

    # P5 rollback and first use
    v = Vector("P5", "retained state detects a rolled-back log; a consumer without it cannot")
    a, b = v.copy_in(A, "A.json"), v.copy_in(B, "B.json")
    la, lab = v.copy_in(LA, "log_A.txt"), v.copy_in(LAB, "log_AB.txt")
    c1, _ = v.step("accept B (log: A,B): anchor 2 entries", consumer(b, lab, v.path("S.state.json")), 0, "ACCEPTED")
    c2, _ = v.step("A with the log cut to 1 entry, anchored S", consumer(a, la, v.path("S.state.json")), 1, "rollback")
    c3, _ = v.step("A with the log cut to 1 entry, fresh S2", consumer(a, la, v.path("S2.state.json")), 0, "ACCEPTED")
    v.save()
    verdict["P5"] = (c1, c2, c3) == (0, 1, 0)

    # P6 forced interleaving, in-process, real consumer_check
    v = Vector("P6", "two consumers that read the same state before either writes both accept")
    cons = load_module("rp1_consumer", "tools/consumer.py")
    vp = cons.load_verifier()
    pkg = json.load(open(os.path.join(ROOT, A)))
    entries = vp.read_witness_log(os.path.join(ROOT, LA))
    snap = cons.load_state(None)
    ok1, why1, new1 = cons.consumer_check(vp, pkg, entries, snap)
    ok2, why2, _ = cons.consumer_check(vp, pkg, entries, snap)
    ok3, why3, _ = cons.consumer_check(vp, pkg, entries, new1)
    print(f"  P6 interleaved: first {ok1} ({why1}); second on the same snapshot {ok2} ({why2})")
    print(f"  P6 sequential:  second given the first's new state {ok3} ({why3})")
    v.save({"interleaved": [ok1, ok2], "sequential_second": ok3, "how": "in-process, tools/consumer.py consumer_check"})
    verdict["P6"] = ok1 and ok2 and not ok3

    # P7 real processes, and P7c its control
    v = Vector("P7", f"{PROCS_P7} consumer processes, one package, one fresh state file per trial")
    a, la = v.copy_in(A, "A.json"), v.copy_in(LA, "log_A.txt")
    t0 = time.time()
    d, z, e = race(TRIALS_P7, PROCS_P7, a, la, rel("P7"))
    print(f"  P7  real     N={PROCS_P7} trials={TRIALS_P7} doubled={d} zero={z} errors={e} ({time.time() - t0:.0f} s)")
    dc, zc, ec = race(TRIALS_P7C, PROCS_P7, a, la, rel("P7"), paused=True)
    print(f"  P7c paused   N={PROCS_P7} trials={TRIALS_P7C} doubled={dc} zero={zc} errors={ec} "
          f"(pause {PAUSE_P7C} s between read and write)")
    v.save({"P7": {"trials": TRIALS_P7, "procs": PROCS_P7, "doubled": d, "zero": z, "errors": e},
            "P7c": {"trials": TRIALS_P7C, "procs": PROCS_P7, "pause_s": PAUSE_P7C, "doubled": dc, "zero": zc,
                    "errors": ec}})
    verdict["P7"] = d >= 1 and e == 0
    verdict["P7c"] = dc >= 18 and ec == 0

    # P8 torn state write
    v = Vector("P8", "a torn consumer state file fails closed for every package")
    a, b = v.copy_in(A, "A.json"), v.copy_in(B, "B.json")
    la, lab = v.copy_in(LA, "log_A.txt"), v.copy_in(LAB, "log_AB.txt")
    c0, _ = v.step("accept A (builds a real state)", consumer(a, la, v.path("S.state.json")), 0, "ACCEPTED")
    data = open(os.path.join(ROOT, v.path("S.state.json")), "rb").read()
    shutil.copy(os.path.join(ROOT, v.path("S.state.json")), os.path.join(ROOT, v.path("T.state.json")))
    with open(os.path.join(ROOT, v.path("T.state.json")), "wb") as fh:
        fh.write(data[: len(data) // 2])
    c1, _ = v.step("B with the torn state T", consumer(b, lab, v.path("T.state.json")), 2, "COULD NOT LOOK")
    c2, _ = v.step("B with the intact state S", consumer(b, lab, v.path("S.state.json")), 0, "ACCEPTED")
    v.save({"torn_bytes": len(data) // 2, "intact_bytes": len(data)})
    verdict["P8"] = (c0, c1, c2) == (0, 2, 0)

    print()
    for k, ok in verdict.items():
        print(f"  {k:<4} {'HELD' if ok else 'REFUTED'}")
    held = sum(verdict.values())
    print(f"mode: {'FLIP (P2 expectations inverted)' if FLIP else 'registered'}")
    print(f"VERDICT  {held} of {len(verdict)} as registered")
    return 0 if held == len(verdict) else 1


if __name__ == "__main__":
    sys.exit(main())
