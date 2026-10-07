#!/usr/bin/env python3
"""GPU-4 (docs/GPU4_PREREG.md): do the CPU and the Adreno OpenCL path report the same token probabilities?

On the S25, with one server running (-c 2048 -np 1):
  python tools/gpu4_probs.py collect --tag gpu        (llama-server-adreno running)
  python tools/gpu4_probs.py collect --tag cpu        (llama-server --device none running)
  python tools/gpu4_probs.py compare ~/gpu4_gpu.json ~/gpu4_cpu.json
Anywhere:
  python tools/gpu4_probs.py --selftest

Exit: 0 = judged, nothing refuted; 1 = a prediction refuted; 2 = could not run. Stdlib only.
"""
import json
import math
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gpu2_probe import PROMPTS, Sampler  # noqa: E402

KGSL = "/sys/class/kgsl/kgsl-3d0"


def could_not_run(msg):
    print("COULD NOT RUN", msg)
    sys.exit(2)


def request(server, prompt):
    body = json.dumps({"prompt": prompt, "n_predict": 8, "temperature": 0, "seed": 1, "cache_prompt": False,
                       "n_probs": 10}).encode()
    req = urllib.request.Request(server + "/completion", data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.load(r)


def normalize(resp):
    """-> list of positions: {"chosen": str, "kind": "logprob"|"prob", "top": {token: value}}"""
    out = []
    for pos in resp.get("completion_probabilities") or []:
        if "top_logprobs" in pos:
            top = {t.get("token", t.get("tok_str")): t["logprob"] for t in pos["top_logprobs"]}
            out.append({"chosen": pos.get("token"), "kind": "logprob", "top": top})
        elif "probs" in pos:
            top = {t.get("tok_str", t.get("token")): t["prob"] for t in pos["probs"]}
            out.append({"chosen": pos.get("content"), "kind": "prob", "top": top})
    return out


def collect(server, tag, out_path):
    try:
        urllib.request.urlopen(server + "/health", timeout=10).read()
    except Exception as exc:  # noqa: BLE001
        could_not_run(f"no server at {server} ({exc})")
    rec = {"tag": tag, "runs": []}
    for pid in ("easy", "hard"):
        for rep in (1, 2):
            s = Sampler(KGSL) if os.path.isdir(KGSL) else None
            if s:
                s.start()
            try:
                resp = request(server, PROMPTS[pid])
            finally:
                if s:
                    s.stop.set()
                    s.join()
            busy = s.summary()["gpu_busy_percentage"][1] if s else None
            pos = normalize(resp)
            rec["runs"].append({"prompt": pid, "rep": rep, "busy_max": busy, "positions": pos, "raw": resp})
            print(f"{tag} {pid} rep {rep}: {len(pos)} positions, kind {pos[0]['kind'] if pos else '?'}, "
                  f"busy max {busy}%, text {resp.get('content', '')[:30]!r}")
    if not any(r["positions"] for r in rec["runs"]):
        could_not_run("the server returned no completion_probabilities; does this llama-server support n_probs?")
    json.dump(rec, open(out_path, "w"), indent=1)
    print("SAVED", out_path)
    return 0


def to_log(kind, v):
    if kind == "logprob":
        return v
    return math.log(v) if v > 0 else None


def compare(a_path, b_path):
    A, B = json.load(open(a_path)), json.load(open(b_path))

    def by(rec, pid, rep):
        return next(r for r in rec["runs"] if r["prompt"] == pid and r["rep"] == rep)

    p1 = all(by(R, pid, 1)["positions"] == by(R, pid, 2)["positions"] for R in (A, B) for pid in ("easy", "hard"))
    same_tokens, any_diff, max_diff, where = True, False, 0.0, None
    for pid in ("easy", "hard"):
        pa, pb = by(A, pid, 1)["positions"], by(B, pid, 1)["positions"]
        if [p["chosen"] for p in pa] != [p["chosen"] for p in pb]:
            same_tokens = False
        for i, (x, y) in enumerate(zip(pa, pb)):
            for tok in set(x["top"]) & set(y["top"]):
                lx, ly = to_log(x["kind"], x["top"][tok]), to_log(y["kind"], y["top"][tok])
                if lx is None or ly is None:
                    continue
                d = abs(lx - ly)
                if d > 0:
                    any_diff = True
                if d > max_diff:
                    max_diff, where = d, (pid, i, tok)
        print(f"{pid}: {A['tag']} tokens {[p['chosen'] for p in pa]}")
        print(f"{pid}: {B['tag']} tokens {[p['chosen'] for p in pb]}")
    busy_a = max((r["busy_max"] or 0) for r in A["runs"])
    busy_b = max((r["busy_max"] or 0) for r in B["runs"])
    print(f"busy max: {A['tag']} {busy_a}%, {B['tag']} {busy_b}%")
    print(f"largest |delta logprob| {max_diff:.6g} at {where}")
    tags = {A["tag"]: busy_a, B["tag"]: busy_b}
    p5 = ("gpu" in tags and "cpu" in tags and tags["gpu"] >= 50 and tags["cpu"] <= 10)
    v = {"P1": p1, "P2": same_tokens, "P3": any_diff, "P4": max_diff < 0.05, "P5 (busy)": p5}
    for k in v:
        print(f"{'HELD' if v[k] else 'REFUTED':8s} {k}")
    return 0 if all(v.values()) else 1


def selftest():
    import tempfile

    def fake(tag, shift, tokens=("1", "8", "4")):
        runs = []
        for pid in ("easy", "hard"):
            for rep in (1, 2):
                pos = [{"chosen": t, "kind": "logprob", "top": {t: -0.01 - shift, "x": -5.0 + shift}} for t in tokens]
                runs.append({"prompt": pid, "rep": rep, "busy_max": 95 if tag == "gpu" else 0, "positions": pos})
        fd, f = tempfile.mkstemp(suffix=".json")  # not mktemp: a name another user could create first (bandit B306)
        with os.fdopen(fd, "w") as fh:
            json.dump({"tag": tag, "runs": runs}, fh)
        return f

    print("--- selftest A: tiny difference, same tokens (P3 must hold)")
    ra = compare(fake("gpu", 0.0), fake("cpu", 1e-4))
    print("--- selftest B: identical numbers (P3 must be refuted)")
    rb = compare(fake("gpu", 0.0), fake("cpu", 0.0))
    print("--- selftest C: different chosen token (P2 must be refuted)")
    rc = compare(fake("gpu", 0.0), fake("cpu", 1e-4, ("1", "8", "5")))
    ok = (ra, rb, rc) == (0, 1, 1)
    print("SELFTEST", "PASS" if ok else f"FAIL {(ra, rb, rc)}")
    return 0 if ok else 1


def main():
    a = sys.argv[1:]
    if "--selftest" in a:
        sys.exit(selftest())
    if a[:1] == ["collect"]:
        tag = a[a.index("--tag") + 1] if "--tag" in a else could_not_run("collect needs --tag gpu|cpu")
        server = a[a.index("--server") + 1] if "--server" in a else "http://127.0.0.1:8080"
        sys.exit(collect(server, tag, os.path.expanduser(f"~/gpu4_{tag}.json")))
    if a[:1] == ["compare"] and len(a) == 3:
        sys.exit(compare(os.path.expanduser(a[1]), os.path.expanduser(a[2])))
    could_not_run(__doc__)


if __name__ == "__main__":
    main()
