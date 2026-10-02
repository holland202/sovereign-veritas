#!/usr/bin/env python3
"""Run a registered plan end to end, resumably. One command, also on the phone.

    python run_suite.py --plan h1 --label container_h1 --models-dir ~/models --threads 2
    python run_suite.py --plan h1 --label s25_h1 --models-dir ~/models --threads 6   # Termux

Every step calls run_bench.py / run_decomposed.py, which skip finished cases, so if Android
kills the process, re-running the same command continues where it stopped. A step whose
model file is missing is reported and skipped, never faked. Prints a summary at the end.
"""
import argparse, json, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))

MODELS = {
    "qwen2.5-1.5b": "qwen2.5-1.5b-instruct-q4_k_m.gguf",
    "lfm2.5-1.2b": "LFM2.5-1.2B-Instruct-Q4_K_M.gguf",
    "qwen3.5-2b": "Qwen_Qwen3.5-2B-Q4_K_M.gguf",
    "qwen3.5-4b": "Qwen_Qwen3.5-4B-Q4_K_M.gguf",
}

PLANS = {
    # registered in PREREG_H1.md
    "h1": {"cases": "heldout/cases_h1.jsonl", "reps": 1,
           "steps": [("direct", m, None) for m in MODELS]
                    + [("decomposed", m, "a2") for m in MODELS]
                    + [("decomposed", m, "a3") for m in ("qwen3.5-2b", "qwen3.5-4b")]},
    # the original 39 cases, all arms (what v0 + A1 + A2 ran in the container)
    "v0": {"cases": "cases.jsonl", "reps": 2,
           "steps": [("direct", m, None) for m in MODELS] + [("decomposed", m, "a2") for m in MODELS]},
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", choices=sorted(PLANS), default="h1")
    ap.add_argument("--label", required=True)
    ap.add_argument("--models-dir", default=os.path.expanduser("~/models"))
    ap.add_argument("--server-bin", default="llama-server")
    ap.add_argument("--threads", type=int, default=os.cpu_count())
    ap.add_argument("--only", nargs="*", help="restrict to these model keys")
    a = ap.parse_args()
    plan = PLANS[a.plan]
    log = []
    for arm, key, prompt in plan["steps"]:
        if a.only and key not in a.only:
            continue
        model = os.path.join(a.models_dir, MODELS[key])
        if not os.path.exists(model):
            print(f"SKIP {arm}/{key}: model file not found at {model}", flush=True)
            log.append({"arm": arm, "model": key, "prompt": prompt, "status": "missing model"})
            continue
        script = "run_bench.py" if arm == "direct" else "run_decomposed.py"
        cmd = [sys.executable, os.path.join(HERE, script), "--model", model, "--label", a.label,
               "--server-bin", a.server_bin, "--threads", str(a.threads), "--reps", str(plan["reps"]),
               "--cases", os.path.join(HERE, plan["cases"])]
        if prompt:
            cmd += ["--extract-prompt", prompt]
        print(f"=== {arm}{'/' + prompt if prompt else ''} {key} ===", flush=True)
        t0 = time.time()
        rc = subprocess.call(cmd)
        log.append({"arm": arm, "model": key, "prompt": prompt, "rc": rc, "seconds": round(time.time() - t0, 1)})
        if rc != 0:
            print(f"step failed rc={rc}; re-run the same command to resume", flush=True)
    out = os.path.join(HERE, "results", a.label, "suite_log.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    prev = json.load(open(out)) if os.path.exists(out) else []
    json.dump(prev + [{"plan": a.plan, "finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                       "steps": log}], open(out, "w"), indent=2)
    print(json.dumps(log, indent=1))


if __name__ == "__main__":
    main()
