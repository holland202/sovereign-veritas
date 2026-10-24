#!/usr/bin/env python3
"""BT-002 driver: re-run BT-001's planted-fault audit with the BT-002 gap tests in the suite, on the phone.

Uses tools/bt001_mutate.py unchanged (same 351 mutants, same oracles T and C, same controls). It changes only the
order: BT-001's T-survivors run first, so the registered predictions about them are answered early; then every other
mutant in BT-001's order until the deadline. One JSON line per mutant, flushed as it is written (BT-002 R1: the
DIFF-001 phone run lost unflushed records when it was stopped). A device line (battery and temperature, when the
phone exposes them) is appended every 60 s to a separate file.

    bt002_run.py --until 2026-10-24T16:00:00Z --out DIR        # the registered run (resumable)
    bt002_run.py --order                                       # print the run order, run nothing
Stdlib only. Self-tested: written by Claude (Anthropic, Opus 5.5).
"""
import argparse, json, os, shutil, subprocess, sys, threading, time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bt001_mutate as bm  # noqa: E402

ROOT = bm.ROOT
BT001 = os.path.join(ROOT, "results", "bt001", "blue_a1.jsonl")


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def bt001_survivors():
    out = []
    for line in open(BT001, encoding="utf-8"):
        r = json.loads(line)
        if "control" not in r and r.get("T", {}).get("verdict") == "PASS":
            out.append(r["id"])
    return out


def order():
    all_m = [(t, m) for t in bm.TARGETS for m in bm.mutants(t)[1]]
    first = set(bt001_survivors())
    return [x for x in all_m if x[1]["id"] in first] + [x for x in all_m if x[1]["id"] not in first]


def device_reading():
    for cmd in (["termux-battery-status"], ["rish", "-c", "dumpsys battery"]):
        if shutil.which(cmd[0]):
            try:
                p = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
                if p.returncode == 0 and p.stdout.strip():
                    return {"source": cmd[0], "raw": p.stdout.strip()[:800]}
            except Exception as exc:  # recorded, never fatal
                return {"source": cmd[0], "error": type(exc).__name__}
    return {"source": "unavailable"}


def device_logger(path, stop):
    with open(path, "a", encoding="utf-8") as fh:
        while not stop.is_set():
            fh.write(json.dumps({"utc": now(), **device_reading()}, sort_keys=True) + "\n")
            fh.flush()
            stop.wait(60)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--until")
    ap.add_argument("--out", default="bt002_out")
    ap.add_argument("--order", action="store_true")
    a = ap.parse_args(argv)
    seq = order()
    if a.order:
        for i, (t, m) in enumerate(seq):
            print(i, m["id"], m["sha256"][:12])
        return 0
    os.makedirs(a.out, exist_ok=True)
    res_path = os.path.join(a.out, "blue.jsonl")
    done = set()
    if os.path.exists(res_path):
        done = {json.loads(l)["id"] for l in open(res_path, encoding="utf-8") if l.strip()}
    deadline = datetime.fromisoformat(a.until.replace("Z", "+00:00")).timestamp()
    work = os.path.join(os.path.abspath(a.out), "work")
    bm.make_work(work)
    stop = threading.Event()
    threading.Thread(target=device_logger, args=(os.path.join(a.out, "device.jsonl"), stop), daemon=True).start()
    out = open(res_path, "a", encoding="utf-8")

    def emit(rec):
        rec["utc"] = now()
        out.write(json.dumps(rec, sort_keys=True) + "\n")
        out.flush()
        os.fsync(out.fileno())

    launch = sum(1 for i in done if i.startswith("control:")) // 2 + 1
    dsrc = open(os.path.join(ROOT, "sovereign_veritas/decision.py"), encoding="utf-8").read()
    import ast
    for name, text, want in (("null", dsrc, "PASS"), ("always-allow", bm.always_allow(dsrc, ast.parse(dsrc)), "FAIL")):
        r = bm.run_one(work, "sovereign_veritas/decision.py", text)
        ok = r["T"]["verdict"] == want and r["C"]["verdict"] == want
        emit({"id": f"control:{name}:launch{launch}", "control": name, "expected": want, "as_expected": ok, **r})
        print(f"control {name}: T {r['T']['verdict']} C {r['C']['verdict']} as_expected={ok}", flush=True)
        if not ok:
            stop.set()
            return 2
    n, end = 0, "all mutants done"
    for t, m in seq:
        if m["id"] in done:
            continue
        if time.time() >= deadline:
            end = "deadline reached"
            break
        r = bm.run_one(work, t, m["text"])
        emit({k: m[k] for k in ("id", "target", "op", "line", "equal_to_base", "sha256")} | r)
        n += 1
        if n % 10 == 0:
            print(f"{now()} {n} mutants this launch, last {m['id']} T={r['T']['verdict']}", flush=True)
    stop.set()
    with open(os.path.join(a.out, "end.json"), "w", encoding="utf-8") as fh:
        json.dump({"utc": now(), "end": end, "mutants_this_launch": n, "launch": launch}, fh, sort_keys=True)
    print(f"{end} after {n} mutants this launch", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
