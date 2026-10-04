#!/usr/bin/env python3
"""GPU-2 (docs/GPU2_PREREG.md): does the Adreno GPU's thermal state change the model's reply bytes?

On the S25, with llama-server-adreno already running:
  python tools/gpu2_probe.py [--server http://127.0.0.1:8080] [--model-file ~/MODEL.gguf]
Anywhere (no phone needed):
  python tools/gpu2_probe.py --selftest

Exit: 0 = judged, all registered predictions held or NOT RUN as registered; 1 = a prediction was refuted;
2 = could not run. Stdlib only.
"""
import hashlib
import http.server
import json
import os
import sys
import tempfile
import threading
import time
import urllib.request

PROMPTS = {"hard": "Q: What is 7338 * 5099? Reply with only the number.\nA:",
           "easy": "Q: What is 23 * 8? Reply with only the number.\nA:"}
PROMPT = PROMPTS["hard"]
FIELDS = ("clock_mhz", "gpu_busy_percentage", "temp", "throttling", "thermal_pwrlevel")


def could_not_run(msg):
    print("COULD NOT RUN", msg)
    sys.exit(2)


def read_kgsl(kgsl):
    out = {}
    for f in FIELDS:
        try:
            raw = open(os.path.join(kgsl, f)).read().strip().split()[0]
            out[f] = int(raw)
        except (OSError, ValueError, IndexError):
            out[f] = None
    return out


class Sampler(threading.Thread):
    def __init__(self, kgsl):
        super().__init__(daemon=True)
        self.kgsl, self.samples, self.stop = kgsl, [], threading.Event()

    def run(self):
        while not self.stop.is_set():
            self.samples.append(read_kgsl(self.kgsl))
            self.stop.wait(0.1)

    def summary(self):
        s = {}
        for f in FIELDS:
            vals = [x[f] for x in self.samples if x[f] is not None]
            s[f] = (min(vals), max(vals)) if vals else (None, None)
        return s


def complete(server, n_predict, temperature, seed, prompt=PROMPT):
    body = json.dumps({"prompt": prompt, "n_predict": n_predict, "temperature": temperature, "seed": seed,
                       "cache_prompt": False}).encode()
    req = urllib.request.Request(server + "/completion", data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.load(r)["content"]


def measured(server, kgsl, n_predict, temperature, seed, prompt=PROMPT):
    s = Sampler(kgsl)
    s.start()
    try:
        content = complete(server, n_predict, temperature, seed, prompt)
    finally:
        s.stop.set()
        s.join()
    return content, hashlib.sha256(content.encode("utf-8")).hexdigest(), s.summary()


def line(phase, i, sha, st, content):
    c, b, t, th, pl = (st[f] for f in FIELDS)
    temp = f"{t[1] / 1000:.1f}C" if t[1] is not None else "?"
    print(f"{phase:7s} {i}  {sha[:12]}  clock {c[0]}-{c[1]} MHz  busy max {b[1]}%  temp max {temp}  "
          f"throttling max {th[1]}  pwrlevel max {pl[1]}  reply {content.strip()[:40]!r}")


def run(server, kgsl, model_file, heat_cap_s, log_path, cold_n=5, hot_n=5, prompt_id="hard", cpu=False):
    prompt = PROMPTS[prompt_id]
    if not os.path.isdir(kgsl):
        could_not_run(f"no kgsl directory at {kgsl}")
    try:
        props = json.load(urllib.request.urlopen(server + "/props", timeout=10))
    except Exception as exc:  # noqa: BLE001
        could_not_run(f"no server at {server} ({exc}). Start llama-server-adreno first")
    mf = None
    if model_file:
        h = hashlib.sha256()
        with open(os.path.expanduser(model_file), "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        mf = h.hexdigest()
    start = read_kgsl(kgsl)
    print(f"PROMPT {prompt_id}  backend {'cpu (not judged on kgsl)' if cpu else 'gpu'}")
    print(f"START  model {props.get('model_path') or props.get('default_generation_settings', {}).get('model')}  "
          f"file sha256 {mf}  temp {start['temp']}  clock {start['clock_mhz']}  pwrlevel {start['thermal_pwrlevel']}")
    rec = {"props_model": props.get("model_path"), "model_sha256": mf, "start": start, "cold": [], "heat": [], "hot": []}

    for i in range(cold_n):
        content, sha, st = measured(server, kgsl, 32, 0, 1, prompt)
        rec["cold"].append({"sha": sha, "content": content, "state": st})
        line("cold", i + 1, sha, st, content)

    t0, k = time.time(), 0
    throttled = False
    while not cpu and time.time() - t0 < heat_cap_s:
        k += 1
        _, _, st = measured(server, kgsl, 256, 0.7, 100 + k, prompt)
        rec["heat"].append(st)
        if (st["throttling"][1] or 0) > 0 or (st["thermal_pwrlevel"][1] or 0) > 0:
            throttled = True
            break
    if not cpu:
        print(f"HEAT   {k} long generations, {time.time() - t0:.0f} s, throttle seen: {throttled}")

    for i in range(0 if cpu else hot_n):
        content, sha, st = measured(server, kgsl, 32, 0, 1, prompt)
        rec["hot"].append({"sha": sha, "content": content, "state": st})
        line("hot", i + 1, sha, st, content)

    ccontent, csha, cst = measured(server, kgsl, 32, 0.8, 2, prompt)
    rec["control"] = {"sha": csha, "content": ccontent, "state": cst}
    line("control", 1, csha, cst, ccontent)

    cold = {r["sha"] for r in rec["cold"]}
    hot = {r["sha"] for r in rec["hot"]}
    p4 = max((r["state"]["gpu_busy_percentage"][1] or 0) for r in rec["cold"]) >= 50
    p1 = len(cold) == 1
    p2 = any(((r["state"]["throttling"][1] or 0) > 0 or (r["state"]["thermal_pwrlevel"][1] or 0) > 0) for r in rec["hot"])
    p5 = csha not in cold
    verdict = {}
    if cpu:
        verdict = {"P1": "HELD" if p1 else "REFUTED", "P2": "NOT RUN (cpu)", "P3": "NOT RUN (cpu)",
                   "P4": "NOT RUN (cpu)", "P5": "HELD" if p5 else "REFUTED"}
        p4 = True
    verdict["P4"] = verdict.get("P4") or ("HELD" if p4 else "REFUTED")
    verdict["P5"] = "HELD" if p5 else "REFUTED"
    if cpu:
        pass
    elif not p4:
        verdict.update(P1="NOT JUDGED", P2="NOT JUDGED", P3="NOT JUDGED")
    else:
        verdict["P1"] = "HELD" if p1 else "REFUTED"
        verdict["P2"] = "HELD" if p2 else "REFUTED"
        verdict["P3"] = ("HELD" if hot == cold and p1 else "REFUTED") if p2 else "NOT RUN (no throttle seen)"
    for p in ("P1", "P2", "P3", "P4", "P5"):
        print(f"{verdict[p]:28s} {p}")
    rec["verdict"] = verdict
    with open(log_path, "w") as fh:
        json.dump(rec, fh, indent=1)
    print(f"SHA    cold {sorted(cold)}  hot {sorted(hot)}  control {csha}")
    print(f"LOG    {log_path}")
    refuted = [p for p, v in verdict.items() if v == "REFUTED" and p != "P2"]
    return 1 if refuted else 0


def selftest():
    """Fake kgsl + fake server. Run A: stable replies -> P3 HELD. Run B: hot replies drift -> P3 REFUTED, exit 1."""
    def fake(drift):
        d = tempfile.mkdtemp()
        state = {"calls": 0, "hot": False}
        for f, v in (("clock_mhz", "900"), ("gpu_busy_percentage", "95 %"), ("temp", "50000"), ("throttling", "0"),
                     ("thermal_pwrlevel", "0")):
            open(os.path.join(d, f), "w").write(v)

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                self._send({"model_path": "fake.gguf"})

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                state["calls"] += 1
                if body["n_predict"] == 256 and state["calls"] > 7:
                    open(os.path.join(d, "thermal_pwrlevel"), "w").write("2")
                    state["hot"] = True
                if body["temperature"] == 0:
                    text = " 37415862" if not (drift and state["hot"]) else " 37415861"
                else:
                    text = f" sampled {body['seed']}"
                self._send({"content": text})

            def _send(self, obj):
                b = json.dumps(obj).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)

        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        return d, f"http://127.0.0.1:{srv.server_address[1]}", srv

    results = []
    for drift in (False, True):
        d, url, srv = fake(drift)
        print(f"--- selftest, hot replies {'DRIFT' if drift else 'stable'}")
        try:
            rc = run(url, d, None, 30, os.path.join(d, "log.json"))
        finally:
            srv.shutdown()
        results.append(rc)
    ok = results == [0, 1]
    print("SELFTEST", "PASS: P3 held when stable, refuted on drift" if ok else f"FAIL {results}")
    return 0 if ok else 1


def main():
    if "--selftest" in sys.argv:
        sys.exit(selftest())

    def opt(name, default):
        return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default
    prompt_id, cpu = opt("--prompt", "hard"), "--cpu" in sys.argv
    if prompt_id not in PROMPTS:
        could_not_run(f"--prompt must be one of {sorted(PROMPTS)}")
    default_log = "~/gpu2_run.json" if (prompt_id == "hard" and not cpu and "--prompt" not in sys.argv) else \
        f"~/gpu3_{prompt_id}_{'cpu' if cpu else 'gpu'}.json"
    sys.exit(run(opt("--server", "http://127.0.0.1:8080"), opt("--kgsl", "/sys/class/kgsl/kgsl-3d0"),
                 opt("--model-file", None), int(opt("--heat-cap", "600")),
                 os.path.expanduser(opt("--log", default_log)), prompt_id=prompt_id, cpu=cpu))


if __name__ == "__main__":
    main()
