#!/usr/bin/env python3
"""Run the evidence-boundary benchmark against one GGUF via llama-server.

One command per model. Stdlib only (works in Termux with `pkg install llama-cpp python`).

  python run_bench.py --model ~/models/X.gguf --label s25 [--threads 6] [--reps 2]

Writes results/<label>/<model-stem>.jsonl (resumable: completed rows are skipped
on re-run, so an Android SIGKILL loses at most one case) and a manifest with every
hash needed to reproduce the run.
"""
import argparse, hashlib, json, os, platform, signal, subprocess, sys, time, urllib.request

from prompt import messages, parse, SYSTEM, render_user

HERE = os.path.dirname(os.path.abspath(__file__))


def sha256(path, buf=1 << 22):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(buf):
            h.update(chunk)
    return h.hexdigest()


def http(url, body=None, timeout=600):
    req = urllib.request.Request(url, data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def peak_rss_mb(pid):
    try:
        for line in open(f"/proc/{pid}/status"):
            if line.startswith("VmHWM:"):
                return int(line.split()[1]) / 1024
    except OSError:
        pass
    return None


def thermal_c(base="/sys/class/thermal"):
    """Per-domain temperatures in C, by zone *type* (see sovereign-veritas docs/THERMAL_ZONES.md).

    A max over every zone mixes CPU cores, modem, and non-temperature zones (pm8550-bcl-*),
    so it is not reported. Returns {"cpu_core_max": .., "battery": ..}; a value is None when
    no readable zone of that type exists, which is the honest value in a container.
    """
    out = {"cpu_core_max": None, "battery": None}
    try:
        zones = [z for z in os.listdir(base) if z.startswith("thermal_zone")]
    except OSError:
        return out
    for z in zones:
        try:
            typ = open(f"{base}/{z}/type").read().strip()
            v = int(open(f"{base}/{z}/temp").read().strip())
        except (OSError, ValueError):
            continue
        c = v / 1000
        if not 0 < c < 150:
            continue
        if typ.startswith("cpu-"):
            out["cpu_core_max"] = c if out["cpu_core_max"] is None else max(out["cpu_core_max"], c)
        elif typ == "battery":
            out["battery"] = c
    return out


def atomic_append(path, row):
    with open(path, "a") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")
        f.flush()
        os.fsync(f.fileno())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--label", required=True, help="device/run label, e.g. s25 or container")
    ap.add_argument("--server-bin", default="llama-server")
    ap.add_argument("--threads", type=int, default=os.cpu_count())
    ap.add_argument("--ctx", type=int, default=2048)
    ap.add_argument("--reps", type=int, default=2)
    ap.add_argument("--port", type=int, default=8089)
    ap.add_argument("--cases", default=os.path.join(HERE, "cases.jsonl"))
    a = ap.parse_args()

    cases = [json.loads(l) for l in open(a.cases)]
    stem = os.path.basename(a.model).rsplit(".gguf", 1)[0]
    outdir = os.path.join(HERE, "results", a.label)
    os.makedirs(outdir, exist_ok=True)
    out = os.path.join(outdir, f"{stem}.jsonl")
    done = set()
    if os.path.exists(out):
        for l in open(out):
            try:
                r = json.loads(l)
                done.add((r["rep"], r["id"]))
            except (json.JSONDecodeError, KeyError):
                pass  # a torn last line from a kill is ignored and that case re-runs

    print(f"hashing {a.model} ...", flush=True)
    model_sha = sha256(a.model)
    prompt_sha = hashlib.sha256((SYSTEM + "\n".join(render_user(c) for c in cases)).encode()).hexdigest()

    cmd = [a.server_bin, "-m", a.model, "--port", str(a.port), "-t", str(a.threads),
           "-c", str(a.ctx), "--seed", "0", "-np", "1", "--jinja", "--no-webui"]
    log = open(os.path.join(outdir, f"{stem}.server.log"), "w")
    t_load0 = time.time()
    srv = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{a.port}"
    try:
        while True:
            if srv.poll() is not None:
                sys.exit(f"llama-server exited rc={srv.returncode}; see {log.name}")
            try:
                if http(base + "/health", timeout=5).get("status") == "ok":
                    break
            except Exception:
                pass
            time.sleep(0.5)
        load_s = time.time() - t_load0
        props = {}
        try:
            props = http(base + "/props", timeout=10)
        except Exception:
            pass

        manifest = {
            "label": a.label, "model_file": os.path.basename(a.model), "model_sha256": model_sha,
            "model_bytes": os.path.getsize(a.model), "cases_sha256": sha256(a.cases),
            "prompt_set_sha256": prompt_sha, "n_cases": len(cases), "reps": a.reps,
            "server_cmd": cmd[0:1] + ["-m", "<model>"] + cmd[3:], "threads": a.threads, "ctx": a.ctx,
            "temperature": 0.0, "seed": 0, "max_tokens": 16,
            "llama_cpp_build": props.get("build_info"), "load_seconds": round(load_s, 2),
            "machine": platform.machine(), "platform": platform.platform(),
            "python": platform.python_version(), "cpu_count": os.cpu_count(),
            "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "backend_claim": "CPU (no GPU/NPU offload flags passed; -ngl not set)",
            "parser": "parsing.parse (hardened, fail-closed)",
        }
        json.dump(manifest, open(os.path.join(outdir, f"{stem}.manifest.json"), "w"), indent=2, sort_keys=True)

        for rep in range(a.reps):
            for c in cases:
                if (rep, c["id"]) in done:
                    continue
                t0 = time.time()
                r = http(base + "/v1/chat/completions", {
                    "messages": messages(c), "temperature": 0.0, "top_k": 1, "seed": 0,
                    "max_tokens": 16, "chat_template_kwargs": {"enable_thinking": False},
                })
                dt = time.time() - t0
                text = r["choices"][0]["message"].get("content") or ""
                tm = r.get("timings", {})
                pred = parse(text)
                row = {"rep": rep, "id": c["id"], "category": c["category"], "expected": c["expected"],
                       "pred": pred, "correct": pred == c["expected"], "raw": text[:200],
                       "latency_s": round(dt, 3), "prompt_n": tm.get("prompt_n"),
                       "prompt_tps": tm.get("prompt_per_second"), "gen_n": tm.get("predicted_n"),
                       "gen_tps": tm.get("predicted_per_second"), "peak_rss_mb": peak_rss_mb(srv.pid),
                       "thermal_c": thermal_c(), "t_unix": round(time.time(), 1)}
                atomic_append(out, row)
                print(f"rep{rep} {c['id']:7s} exp={c['expected']:13s} got={pred:13s} {'ok ' if row['correct'] else 'MISS'} {dt:5.1f}s",
                      flush=True)
    finally:
        srv.send_signal(signal.SIGTERM)
        try:
            srv.wait(timeout=20)
        except subprocess.TimeoutExpired:
            srv.kill()
    print(f"done -> {out}")


if __name__ == "__main__":
    main()
