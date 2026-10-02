#!/usr/bin/env python3
"""Sustained device benchmark: does throughput hold up under heat? (instrument for H1-P10)

    python device_bench.py --model ~/models/Qwen_Qwen3.5-2B-Q4_K_M.gguf --minutes 20
    python device_bench.py --selftest

Why this exists: the benchmark runs' "gen tok/s" was measured over 3-6 generated tokens per
call (per-call overhead, not throughput), and llama-server's prompt cache made models
process different prompt lengths (STATS.md, finding 6). This instrument uses llama-bench's
FIXED workload (default: read 512 tokens, write 128) back to back for N minutes, and logs
CPU-core and battery temperature BY ZONE TYPE between iterations (never a max over all 68
zones — see sovereign-veritas docs/THERMAL_ZONES.md).

H1-P10 (registered in PREREG_H1.md): the final-5-minute median generation tok/s is >= 70% of
the first-5-minute median, for Qwen3.5-2B Q4_K_M over 20 minutes on the S25.

Exit codes: 0 = measured (whatever the verdict; a refuted prediction is a result, not a build
failure) · 1 = the instrument could not run (llama-bench missing or unparseable) ·
2 = ran but not enough data for a verdict (fewer than 3 iterations in either window).
Resumable: every iteration is appended to results/<label>/device_bench_<model>.jsonl as soon
as it finishes; re-running continues a new session in the same file. Run termux-wake-lock first.
"""
import argparse, json, os, platform, statistics, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def thermal_by_type(base="/sys/class/thermal"):
    """{'cpu_core_max', 'gpu_max', 'battery'} in C, None where unreadable (honest in a container)."""
    out = {"cpu_core_max": None, "gpu_max": None, "battery": None}
    try:
        zones = [z for z in os.listdir(base) if z.startswith("thermal_zone")]
    except OSError:
        return out
    def read(p):
        with open(p) as fh:
            return fh.read().strip()
    for z in zones:
        try:
            typ = read(f"{base}/{z}/type")
            c = int(read(f"{base}/{z}/temp")) / 1000
        except (OSError, ValueError):
            continue
        if not 0 < c < 150:
            continue
        key = "cpu_core_max" if typ.startswith("cpu-") else "gpu_max" if typ.startswith("gpuss") else "battery" if typ == "battery" else None
        if key == "battery":
            out[key] = c
        elif key:
            out[key] = c if out[key] is None else max(out[key], c)
    return out


def run_once(bench_bin, model, pp, tg, threads):
    cmd = [bench_bin, "-m", model, "-p", str(pp), "-n", str(tg), "-r", "1", "-o", "json"]
    if threads:
        cmd += ["-t", str(threads)]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"llama-bench rc={p.returncode}: {p.stderr[-400:]}")
    data = json.loads(p.stdout)
    pp_e = next(e for e in data if e.get("n_prompt") == pp and e.get("n_gen") == 0)
    tg_e = next(e for e in data if e.get("n_gen") == tg and e.get("n_prompt") == 0)
    return {"pp_tps": pp_e["avg_ts"], "tg_tps": tg_e["avg_ts"], "build_commit": pp_e.get("build_commit"),
            "n_threads": pp_e.get("n_threads")}


def verdict(rows, window_s=300.0, registered_s=1200.0, bar=0.70):
    """H1-P10 verdict from per-iteration rows with 't' (seconds since start) and 'tg_tps'.

    The registered test is a 20-minute run. Anything shorter is INSUFFICIENT, never a verdict:
    on a short run the first and last 5-minute windows overlap, and the ratio is 1.0 by
    construction (found 2026-10-02: a 20-second smoke run reported CONFIRMED)."""
    if not rows:
        return {"status": "INSUFFICIENT", "reason": "no iterations"}
    t_end = max(r["t"] for r in rows)
    first = [r["tg_tps"] for r in rows if r["t"] <= window_s]
    last = [r["tg_tps"] for r in rows if r["t"] >= t_end - window_s and r["t"] > window_s]
    if t_end < registered_s * 0.95 or t_end - window_s <= window_s or len(first) < 3 or len(last) < 3:
        return {"status": "INSUFFICIENT", "reason": f"ran {t_end:.0f}s of the registered {registered_s:.0f}s; "
                                                    f"first-window n={len(first)}, last-window n={len(last)}"}
    m1, m2 = statistics.median(first), statistics.median(last)
    ratio = m2 / m1
    return {"status": "CONFIRMED" if ratio >= bar else "REFUTED", "first5_median_tg": round(m1, 3),
            "last5_median_tg": round(m2, 3), "ratio": round(ratio, 4), "bar": bar,
            "n_first": len(first), "n_last": len(last), "seconds": round(t_end, 1)}


def selftest():
    """The verdict logic must be able to return each outcome (anti-vacuity), and the thermal
    reader must ignore non-CPU zones and impossible readings."""
    import tempfile
    ok = True
    def check(cond, name):
        nonlocal ok
        ok &= bool(cond)
        print(("PASS " if cond else "FAIL ") + name)
    flat = [{"t": t, "tg_tps": 10.0} for t in range(0, 1201, 30)]
    drop = [{"t": t, "tg_tps": 10.0 if t < 600 else 5.0} for t in range(0, 1201, 30)]
    short = [{"t": t, "tg_tps": 10.0} for t in range(0, 300, 30)]
    tiny = [{"t": t, "tg_tps": 8.0} for t in (4, 7, 10, 13, 16, 20)]   # the 20-second run that once said CONFIRMED
    check(verdict(flat)["status"] == "CONFIRMED", "steady throughput -> CONFIRMED")
    check(verdict(drop)["status"] == "REFUTED" and verdict(drop)["ratio"] == 0.5, "halved throughput -> REFUTED, ratio 0.5")
    check(verdict(short)["status"] == "INSUFFICIENT", "5-minute run -> INSUFFICIENT")
    check(verdict(tiny)["status"] == "INSUFFICIENT", "20-second run (overlapping windows) -> INSUFFICIENT, never CONFIRMED")
    d = tempfile.mkdtemp()
    for i, (typ, milli) in enumerate([("cpu-0-0-0", 61000), ("cpu-1-1-1", 74500), ("battery", 33100),
                                      ("mdmss-0", 99000), ("mmw0", -273000), ("gpuss-0", 52000)]):
        os.makedirs(f"{d}/thermal_zone{i}")
        for name, val in (("type", typ), ("temp", str(milli))):
            with open(f"{d}/thermal_zone{i}/{name}", "w") as fh:
                fh.write(val)
    th = thermal_by_type(d)
    check(th == {"cpu_core_max": 74.5, "gpu_max": 52.0, "battery": 33.1}, f"thermal by type ignores modem and -273 zones {th}")
    print("selftest", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model")
    ap.add_argument("--minutes", type=float, default=20.0)
    ap.add_argument("--bench-bin", default="llama-bench")
    ap.add_argument("--threads", type=int, default=0, help="0 = llama-bench default")
    ap.add_argument("--pp", type=int, default=512)
    ap.add_argument("--tg", type=int, default=128)
    ap.add_argument("--label", default="s25")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not a.model or not os.path.exists(a.model):
        print(f"model not found: {a.model}", file=sys.stderr)
        return 1
    stem = os.path.basename(a.model).rsplit(".gguf", 1)[0]
    out = os.path.join(HERE, "results", a.label, f"device_bench_{stem}.jsonl")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    session = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    print(f"session {session}: {a.minutes} min of pp{a.pp}/tg{a.tg} on {stem} -> {out}", flush=True)
    t0 = time.time()
    rows = []
    while time.time() - t0 < a.minutes * 60:
        th_before = thermal_by_type()
        try:
            r = run_once(a.bench_bin, a.model, a.pp, a.tg, a.threads)
        except (RuntimeError, FileNotFoundError, ValueError, StopIteration) as e:
            print(f"instrument could not run: {e}", file=sys.stderr)
            return 1
        row = {"session": session, "t": round(time.time() - t0, 1), **r, "thermal_before": th_before,
               "thermal_after": thermal_by_type(), "machine": platform.machine(), "pp": a.pp, "tg": a.tg}
        rows.append(row)
        with open(out, "a") as f:
            f.write(json.dumps(row) + "\n")
            f.flush()
            os.fsync(f.fileno())
        cpu = row["thermal_after"]["cpu_core_max"]
        print(f"t={row['t']:7.1f}s  read {r['pp_tps']:7.1f} tok/s  write {r['tg_tps']:6.2f} tok/s  "
              f"cpu max {cpu if cpu is not None else 'n/a'} C", flush=True)
    v = verdict(rows)  # always judged against the REGISTERED 20 minutes, whatever --minutes was
    summary = {"session": session, "model": stem, "minutes": a.minutes, "iterations": len(rows),
               "prediction": "H1-P10: last-5-min median tg >= 0.70 x first-5-min median", "verdict": v}
    with open(os.path.join(os.path.dirname(out), f"device_bench_{stem}_{session}_summary.json"), "w") as fh:
        json.dump(summary, fh, indent=2)
    print(json.dumps(summary, indent=2))
    return 2 if v["status"] == "INSUFFICIENT" else 0


if __name__ == "__main__":
    sys.exit(main())
