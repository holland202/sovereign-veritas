#!/usr/bin/env python3
"""re1_probe.py - RE-1: what large inputs cost tools/verify_package.py, and how exhaustion is reported
(docs/KL1_RE1_PREREG.md). Each case runs the real verifier in a child process; peak memory is that child's ru_maxrss;
timings are taken 3 times (median, min-max). Address-space limits use RLIMIT_AS (Linux). Writes large temporary files
(about 1 GB at most, one at a time) and deletes them.

  python tools/re1_probe.py              # exit 0 iff all 6 registered predictions held
  python tools/re1_probe.py --sabotage   # RE-P2 runs without the memory limit, so it must be refuted -> exit 1
  python tools/re1_probe.py --expect-fix # after the RE-1 fixes: RE-P2 and RE-P5 give COULD NOT LOOK (exit 2), and the
                                         # 50 MB depth refusal takes < 2x the 10 MB one (json_depth stops early)
"""
import hashlib
import importlib.util
import json
import os
import resource
import shutil
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERIFY = os.path.join(ROOT, "tools", "verify_package.py")
MAKE = os.path.join(ROOT, "tools", "make_package.py")
MB, GIB = 1_000_000, 1 << 30
LAUNCH = ("import resource, subprocess, sys\n"
          "limit = int(sys.argv[1])\n"
          "def pre():\n"
          "    if limit: resource.setrlimit(resource.RLIMIT_AS, (limit, limit))\n"
          "p = subprocess.run(sys.argv[2:], preexec_fn=pre, capture_output=True, text=True)\n"
          "print(p.returncode); print(resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)\n"
          "sys.stdout.write(p.stdout[-2000:] + '\\n----\\n' + p.stderr[-2000:])\n")


def load_vp():
    spec = importlib.util.spec_from_file_location("verify_package", VERIFY)
    vp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vp)
    return vp


def measure(args, limit=0):
    """(exit code, peak RSS in MB, seconds, stdout+stderr tail) of one verifier run in a fresh child."""
    t0 = time.perf_counter()
    p = subprocess.run([sys.executable, "-c", LAUNCH, str(limit), sys.executable, VERIFY, *args],
                       capture_output=True, text=True)
    dt = time.perf_counter() - t0
    lines = p.stdout.split("\n", 2)
    return int(lines[0]), int(lines[1]) / 1024, dt, lines[2] if len(lines) > 2 else ""


def repeat(args, n=3, limit=0):
    runs = [measure(args, limit) for _ in range(n)]
    secs = [r[2] for r in runs]
    return runs[0][0], max(r[1] for r in runs), statistics.median(secs), (min(secs), max(secs)), runs[0][3]


def pearson(xs, ys):
    mx, my = statistics.mean(xs), statistics.mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = (sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys)) ** 0.5
    return num / den if den else float("nan")


def padded(vp, base, nbytes, path):
    """The genuine package with artifact.name (no check binds it) padded so the file is about nbytes, resealed."""
    pkg = json.loads(json.dumps(base))
    pkg["artifact"]["name"] = ""
    small = len(vp.canon(pkg).encode())
    pkg["artifact"]["name"] = "x" * max(1, nbytes - small - 100)
    pkg["package_sha256"] = vp.sha(vp.canon({k: v for k, v in pkg.items() if k != "package_sha256"}))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(vp.canon(pkg))
    return pkg


def witness_log(path, n, last):
    with open(path, "w", encoding="ascii", newline="\n") as fh:
        fh.write("# sv witness log v0\n")
        for i in range(1, n):
            fh.write(f"{i} {hashlib.sha256(str(i).encode()).hexdigest()}\n")
        fh.write(f"{n} {last}\n")


def main(argv):
    sabotage, fixed = "--sabotage" in argv, "--expect-fix" in argv
    vp = load_vp()
    d = tempfile.mkdtemp()
    rows = []

    def row(case, prediction, held, observed):
        rows.append(held)
        print(f"  {case:<6} {'HELD   ' if held else 'REFUTED'} {prediction}\n         observed: {observed}")

    try:
        mk = subprocess.run([sys.executable, MAKE, "--thermal-status", "normal", "--rounds", "20000"],
                            env=dict(os.environ, HOME=d), cwd=ROOT, capture_output=True, text=True)
        base_path = next(l.split()[1] for l in mk.stdout.splitlines() if l.startswith("package "))
        base = json.loads(open(base_path, encoding="utf-8").read())
        rc, rss, sec, spread, _ = repeat([base_path])
        print(f"  baseline genuine package ({os.path.getsize(base_path)} bytes): exit {rc}, peak {rss:.1f} MB, "
              f"{sec:.3f} s (min-max {spread[0]:.3f}-{spread[1]:.3f})")

        # RE-P1: padded packages, resealed (artifact.name is unbound, so they still verify)
        sizes, secs, peaks, exits, consistent = [1, 10, 50, 100], [], [], [], []
        for s in sizes:
            path = os.path.join(d, f"p{s}.json")
            padded(vp, base, s * MB, path)
            rc, rss, sec, spread, out = repeat([path])
            exits.append(rc)
            consistent.append("VERDICT  CONSISTENT" in out)
            secs.append(sec)
            peaks.append(rss)
            print(f"  RE-P1  {s:>3} MB: exit {rc}, peak {rss:.1f} MB, {sec:.2f} s (min-max {spread[0]:.2f}-{spread[1]:.2f})"
                  f"{', VERDICT CONSISTENT' if consistent[-1] else ''}")
            os.remove(path)
        r_t, r_m = pearson(sizes, secs), pearson(sizes, peaks)
        row("RE-P1", "no size refusal; time and peak memory linear (r >= 0.99); peak at 100 MB >= 2x the file",
            all(e in (0, 1) for e in exits) and r_t >= 0.99 and r_m >= 0.99 and peaks[-1] >= 200,
            f"exits {exits}; all CONSISTENT: {all(consistent)}; r(time) {r_t:.4f}, r(peak) {r_m:.4f}; "
            f"peak at 100 MB {peaks[-1]:.0f} MB")

        # RE-P2: 400 MB under a 1 GiB address-space limit
        path = os.path.join(d, "p400.json")
        padded(vp, base, 400 * MB, path)
        rc, rss, sec, out = measure([path], 0 if sabotage else GIB)
        tail = [l for l in out.splitlines() if l.strip()][-1:] or [""]
        if fixed:
            row("RE-P2", "expect-fix: 400 MB under RLIMIT_AS 1 GiB is COULD NOT LOOK: MemoryError, exit 2",
                rc == 2 and "COULD NOT LOOK: MemoryError" in out, f"exit {rc}, {sec:.1f} s, out: {out.strip()[:110]}")
        else:
            row("RE-P2", "400 MB under RLIMIT_AS 1 GiB: uncaught MemoryError, exit 1 ('a check failed')",
                rc == 1 and "MemoryError" in out, f"exit {rc}, {sec:.1f} s, last line: {tail[0][:110]}")
        os.remove(path)

        # RE-P3: depth refusal cost
        times = {}
        for s in (10, 50):
            path = os.path.join(d, f"deep{s}.json")
            with open(path, "w") as fh:
                fh.write("[" * (s * MB))
            rc3, _, sec, spread, out = repeat([path])
            times[s] = (rc3, sec, "COULD NOT LOOK" in out)
            print(f"  RE-P3  {s} MB of '[': exit {rc3}, {sec:.2f} s (min-max {spread[0]:.2f}-{spread[1]:.2f})")
            os.remove(path)
        ratio = times[50][1] / times[10][1]
        both = times[10][0] == 2 and times[50][0] == 2 and times[10][2] and times[50][2]
        if fixed:
            row("RE-P3", "expect-fix: COULD NOT LOOK both times; the 50 MB refusal takes < 2x the 10 MB one",
                both and ratio < 2, f"exits {times[10][0]}, {times[50][0]}; ratio {ratio:.2f}")
        else:
            row("RE-P3", "COULD NOT LOOK both times; the 50 MB refusal takes >= 4x the 10 MB one (no early exit)",
                both and ratio >= 4, f"exits {times[10][0]}, {times[50][0]}; ratio {ratio:.2f}")

        # RE-P4 / RE-P5: witness logs
        wl = {}
        for n in (10 ** 5, 10 ** 6):
            path = os.path.join(d, f"w{n}.log")
            witness_log(path, n, base["package_sha256"])
            rc4, rss, sec, spread, out = repeat([base_path, "--witness-log", path])
            wl[n] = (rc4, sec, "LATEST_WITNESSED" in out)
            print(f"  RE-P4  {n:>8} entries ({os.path.getsize(path) / MB:.0f} MB): exit {rc4}, peak {rss:.1f} MB, "
                  f"{sec:.2f} s (min-max {spread[0]:.2f}-{spread[1]:.2f})")
            os.remove(path)
        ratio = wl[10 ** 6][1] / wl[10 ** 5][1]
        row("RE-P4", "10^5 and 10^6 entries both judged LATEST_WITNESSED (exit 0); 10^6 takes >= 5x the 10^5 time",
            all(v[0] == 0 and v[2] for v in wl.values()) and ratio >= 5, f"exits {[v[0] for v in wl.values()]}; ratio {ratio:.2f}")
        path = os.path.join(d, "w1e7.log")
        witness_log(path, 10 ** 7, base["package_sha256"])
        rc5, _, sec, out = measure([base_path, "--witness-log", path], 512 << 20)
        tail = [l for l in out.splitlines() if l.strip()][-1:] or [""]
        if fixed:
            row("RE-P5", "expect-fix: 10^7 entries under RLIMIT_AS 512 MiB is COULD NOT LOOK: MemoryError, exit 2",
                rc5 == 2 and "COULD NOT LOOK: MemoryError" in out, f"exit {rc5}, {sec:.1f} s, out: {out.strip()[:100]}")
        else:
            row("RE-P5", "10^7 entries under RLIMIT_AS 512 MiB: uncaught MemoryError, exit 1",
                rc5 == 1 and "MemoryError" in out, f"exit {rc5}, {sec:.1f} s, log {os.path.getsize(path) / MB:.0f} MB, "
                                                   f"last line: {tail[0][:100]}")
        os.remove(path)

        # RE-P6: the verifier's maximum chain rounds
        d6 = os.path.join(d, "r6")
        os.mkdir(d6)
        mk = subprocess.run([sys.executable, MAKE, "--thermal-status", "normal", "--rounds", "10000000"],
                            env=dict(os.environ, HOME=d6), cwd=ROOT, capture_output=True, text=True)
        p6 = next(l.split()[1] for l in mk.stdout.splitlines() if l.startswith("package "))
        rc6, rss, sec, out = measure([p6])
        row("RE-P6", "rounds = 10,000,000 completes in < 30 s", rc6 == 0 and sec < 30,
            f"exit {rc6}, {sec:.2f} s, peak {rss:.1f} MB")
    finally:
        shutil.rmtree(d, ignore_errors=True)
    print(f"mode: {'SABOTAGE (RE-P2 without the memory limit)' if sabotage else 'registered'}{' +expect-fix' if fixed else ''}")
    print(f"VERDICT  {sum(rows)} of {len(rows)} as registered")
    return 0 if all(rows) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
