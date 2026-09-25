#!/usr/bin/env python3
"""thermal_probe.py - EXPLORATORY. Which thermal zones get hot under CPU load, and how hot?

Question: could the 104.6 C max in sv_real_inference_test.py be a real reading taken
under load, or does it come from a zone that is not a temperature?

Takes one consistent pass over every zone per sample (the two-command dump read the
device twice and lost zones 15, 45, 57 between reads). Keeps each zone's type. Loads
every core with busy-loop subprocesses for --seconds, samples once a second, then
reports per-zone maxima. Raw samples go to a JSON file under $HOME.

Domains come from the zone type names observed on the S25 on 2026-09-25. Anything
unmatched is 'unknown' and is reported, never averaged into anything.
  python thermal_probe.py [--seconds 30] [--root /sys/class/thermal]
Stdlib only. Burners are always killed, including on Ctrl+C.
"""
import argparse, hashlib, json, os, platform, subprocess, sys, time

DOMAINS = [  # (type prefix, domain) - order matters, first match wins
    ("cpuss-", "cpu_subsystem"), ("cpu-", "cpu_core"), ("gpuss-", "gpu"),
    ("nsph", "npu"), ("ddr", "ddr"), ("mdmss-", "modem"), ("camera", "camera"),
    ("video", "video"), ("aoss-", "always_on"), ("pm8550-bcl", "NOT_TEMPERATURE_bcl"),
    ("pm", "pmic"), ("battery", "battery"), ("sys-therm", "board"),
    ("sdr", "rf"), ("mmw", "rf"),
]


def domain(ztype):
    return next((d for p, d in DOMAINS if ztype.startswith(p)), "unknown")


def zones(root):
    out = []
    for name in sorted(os.listdir(root)):
        if name.startswith("thermal_zone"):
            try:
                with open(os.path.join(root, name, "type")) as fh:
                    ztype = fh.read().strip()
            except OSError:
                ztype = "?"
            out.append((name, ztype))
    return out


def snapshot(root, zs):
    vals = {}
    for name, _ in zs:
        try:
            with open(os.path.join(root, name, "temp")) as fh:
                vals[name] = int(fh.read().strip())
        except (OSError, ValueError):
            vals[name] = None
    return vals


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=int, default=30)
    ap.add_argument("--root", default="/sys/class/thermal")
    a = ap.parse_args()
    zs = zones(a.root) if os.path.isdir(a.root) else []
    if not zs:
        print(f"COULD NOT LOOK: no thermal zones under {a.root}")
        sys.exit(2)
    types = dict(zs)
    samples = [("idle", time.time(), snapshot(a.root, zs))]
    n = os.cpu_count() or 1
    burners = []
    try:
        burners = [subprocess.Popen([sys.executable, "-c", "while True: pass"]) for _ in range(n)]
        end = time.time() + a.seconds
        while time.time() < end:
            time.sleep(1)
            samples.append(("load", time.time(), snapshot(a.root, zs)))
    finally:
        for b in burners:
            b.kill()
        for b in burners:
            b.wait()
    time.sleep(1)
    samples.append(("after", time.time(), snapshot(a.root, zs)))

    load = [s for s in samples if s[0] == "load"]
    idle = samples[0][2]
    print(f"EXPLORATORY thermal_probe | {platform.machine()} python {platform.python_version()}"
          f" | {len(zs)} zones | {n} burners x {a.seconds}s | {len(load)} load samples")
    rows = []
    for name, ztype in zs:
        seen = [s[2][name] for s in load if s[2][name] is not None]
        rows.append((max(seen) if seen else None, name, ztype, idle[name]))
    rows.sort(key=lambda r: (r[0] is None, -(r[0] or 0)))
    print("TOP 12 zones by max under load (millidegrees as read):")
    for mx, name, ztype, i0 in rows[:12]:
        print(f"  {mx:>7} (idle {i0:>7})  {name:<15} {ztype:<18} {domain(ztype)}")
    by_dom = {}
    for mx, name, ztype, _ in rows:
        if mx is not None:
            d = domain(ztype)
            by_dom[d] = max(by_dom.get(d, mx), mx)
    print("MAX by domain:", ", ".join(f"{d}={v}" for d, v in sorted(by_dom.items(), key=lambda x: -x[1])))
    print("ZONES 15/45/57:", ", ".join(f"{z}={types.get(z, 'absent')}" for z in
                                      ("thermal_zone15", "thermal_zone45", "thermal_zone57")))
    over = [r for r in rows if r[0] is not None and r[0] >= 90000]
    print(f">= 90 C under load: {len(over)} zones")
    unknown = sorted({t for _, t in zs if domain(t) == "unknown"})
    print(f"unknown types: {unknown}")
    path = os.path.join(os.path.expanduser("~"), f"thermal_probe_{int(samples[0][1])}.json")
    blob = json.dumps({"zones": zs, "samples": samples, "burners": n, "seconds": a.seconds},
                      separators=(",", ":"))
    with open(path, "w") as fh:
        fh.write(blob)
    print(f"raw  {path}  md5 {hashlib.md5(blob.encode()).hexdigest()}")


if __name__ == "__main__":
    main()
