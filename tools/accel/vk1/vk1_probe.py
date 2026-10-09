#!/usr/bin/env python3
"""VK-1 probe: is llama.cpp Vulkan output on the S25 Ultra's Adreno 830 correct?

Registered in VK1_PREREG.md (same folder). Read it first. Stdlib only.

Every llama.cpp process runs with stdin=/dev/null and a timeout, so it cannot
fall into llama-cli's interactive chat loop. On 2026-10-06 that loop swallowed
two experimental runs.

Usage (Termux, one at a time):
  python3 vk1_probe.py --plan        list the matrix, run nothing
  python3 vk1_probe.py --preflight   environment record only
  python3 vk1_probe.py               run every cell not yet done (resumable)
  python3 vk1_probe.py --only LABEL  run one cell (repeatable flag)
  python3 vk1_probe.py --report      evaluate the registered predictions

Output: ~/sv-lab/runs/vk1/{results.jsonl,preflights.jsonl,logs/*.log}
Each completed cell is fsync'd to results.jsonl immediately. A killed run
loses only the cell in progress; re-running skips completed cells.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import random
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

VERSION = "vk1-probe 1"
HERE = Path(__file__).resolve().parent
HOME = Path(os.environ.get("HOME") or str(Path.home()))
OUT = HOME / "sv-lab" / "runs" / "vk1"
RESULTS = OUT / "results.jsonl"
PREFLIGHTS = OUT / "preflights.jsonl"
LOGS = OUT / "logs"
PREREG = HERE / "VK1_PREREG.md"

# ---- frozen constants (VK1_PREREG.md section 3) ----
GEN_PROMPT = "Explain in one sentence what evidence means."
N_GEN = 32
GEN_CTX = 512
GEN_MATCH_CHARS = 24
PPL_CTX = 128
PPL_CHUNKS = 4
PPL_TOL = 1.05
SCRAMBLE_SEED = 20261006
SCRAMBLE_MIN_RATIO = 3.0
TIMEOUT_GEN = 300
TIMEOUT_PPL = 900
TIMEOUT_CLI_RAW = 180
MEM_WARN_KB = 1_500_000

# None until the first full device run is pinned (separate, later step).
# Form: {"digest": "<sha256>", "held": ("P1", ...)}
RECORDED = {  # pinned from the 2026-10-06 S25 run (RESULTS_VK1.md)
    "digest": "e464c9443057b6626f1fb94aa0d12c672255dec41700bad98d0261447f8055a4",
    "held": ("P1", "P2b", "P3", "P4", "P6", "P7", "P8", "P9"),
}

MODELS = {
    "tinyllama": {
        "path": HOME / "models" / "tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf",
        "sha256": "9fecc3b3cd76bba89d504f29b616eedf7da85b96540e490ca5824d3f7d2776a0",
        "quant": "Q4_K_M",
    },
    "q40": {
        "path": HOME / "sovereign_knowledge.gguf",
        "sha256": "dcd819ff094852c38faba6873d8ff0c9d51eadb2844539e52042ae5d647bbfdb",
        "quant": "Q4_0",
    },
    "qwen_q4km": {
        "path": HOME / "models" / "qwen2.5-1.5b-instruct-q4_k_m.gguf",
        "sha256": None,  # unpinned: recorded on first run
        "quant": "Q4_K_M",
    },
}

EXPLORE_FLAGS = [
    ("mmvq", "GGML_VK_DISABLE_MMVQ"),
    ("f16", "GGML_VK_DISABLE_F16"),
    ("coopmat2dv", "GGML_VK_DISABLE_COOPMAT2_DECODE_VECTOR"),
    ("dot2", "GGML_VK_DISABLE_DOT2"),
    ("fusion", "GGML_VK_DISABLE_FUSION"),
    ("graphopt", "GGML_VK_DISABLE_GRAPH_OPTIMIZE"),
]
BISECT_NGL = [1, 2, 11, 21, 22, 23, 99]

CORPUS = """\
Evidence is what remains when the story is taken away. A machine builder learns this early. A drawing can say that a weld will hold, a supplier can say that a bearing is rated for the load, and a manager can say that the schedule is safe, but none of those sentences is the weld, the bearing, or the schedule. The only way to know is to put weight on the thing and watch what it does. If the frame bends, the drawing was wrong, no matter how clean the lines were.

The same rule applies to software, and it applies with more force, because software is very good at describing itself. A program can print that a service is running when the service has already stopped. A dashboard can show a green light that is wired to nothing. A test can pass because it never asked a question that could fail. In each case the report is real and the fact behind it is missing. The report is a claim about the world, and a claim needs support before anyone should lean on it.

Good measurement starts by deciding, before looking, what result would prove the idea wrong. This is harder than it sounds. Once the numbers arrive it is tempting to find a reason why the surprising ones do not count and the comfortable ones do. Writing the prediction down first removes that temptation. If the prediction fails, the failure is kept and studied, because a failed prediction usually teaches more than a successful one. It points at the exact place where understanding was thin.

A careful record also separates layers that are easy to blur together. The hardware may be present while the driver is broken. The driver may load while the runtime refuses the work. The runtime may accept the work while the answer comes back wrong. Each layer needs its own evidence, and a success at one layer says nothing about the next. A technician who checks only that the pump motor turns has not checked that water moves through the pipe.

Comparison is the second tool. One measurement alone rarely means much, because there is nothing to hold it against. Two measurements taken the same way, with one thing changed between them, can isolate a cause. Change two things at once and the result cannot say which one mattered. This is why a good experiment looks slow and boring from the outside. It moves one variable, records everything else, and repeats the step until the answer stops changing.

Finally, evidence has to survive the person who gathered it. Notes written for the moment are lost within a week. A useful record says what was run, on which machine, with which version, at what time, and what came back, word for word. Someone who was not there should be able to repeat the work and either get the same answer or find out exactly where the two runs differ. That is the difference between a result and an anecdote, and it is the reason the slow work is worth doing.
"""


# ---------------------------------------------------------------- utilities
def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def meminfo() -> dict | None:
    d = {}
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                k, v = line.split(":", 1)
                d[k] = int(v.split()[0])
    except Exception:
        return None
    return {k: d.get(k) for k in ("MemTotal", "MemAvailable", "SwapTotal", "SwapFree")}


def battery() -> dict | None:
    p = shutil.which("termux-battery-status")
    if not p:
        return None
    try:
        cp = subprocess.run([p], stdin=subprocess.DEVNULL, capture_output=True, timeout=15)
        j = json.loads(cp.stdout.decode("utf-8", "replace"))
    except Exception:
        return None
    return {k: j.get(k) for k in ("temperature", "current", "voltage", "percentage", "plugged")}


def telemetry() -> dict:
    return {"t": now(), "mem_kb": meminfo(), "battery": battery()}


def scrambled(text: str) -> str:
    words = text.split()
    random.Random(SCRAMBLE_SEED).shuffle(words)
    return " ".join(words) + "\n"


def run_capture(argv, env=None, timeout=60):
    """Run with stdin=/dev/null. Returns (rc, stdout, stderr). rc is an int
    (negative = killed by signal), 'timeout', or 'oserror:...'."""
    try:
        cp = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True,
                            env=env, timeout=timeout)
        rc, out, err = cp.returncode, cp.stdout, cp.stderr
    except subprocess.TimeoutExpired as e:
        rc, out, err = "timeout", e.stdout or b"", e.stderr or b""
    except OSError as e:
        rc, out, err = f"oserror:{e}", b"", b""
    return rc, out.decode("utf-8", "replace"), err.decode("utf-8", "replace")


# ---------------------------------------------------------------- tools
def select_tools() -> dict:
    t = {"gen": None, "gen_path": None, "gen_help": "", "ppl_path": None, "cli_path": None}
    for name in ("llama-completion", "llama-simple", "llama-cli"):
        p = shutil.which(name)
        if p:
            t["gen"], t["gen_path"] = name, p
            if name != "llama-simple":
                _, o, e = run_capture([p, "--help"], timeout=60)
                t["gen_help"] = o + e
            break
    t["ppl_path"] = shutil.which("llama-perplexity")
    t["cli_path"] = shutil.which("llama-cli")
    return t


def gen_argv(tools: dict, model_path: str, ngl: int) -> list[str]:
    p, name, h = tools["gen_path"], tools["gen"], tools["gen_help"]
    if name == "llama-simple":
        return [p, "-m", model_path, "-n", str(N_GEN), "-ngl", str(ngl), GEN_PROMPT]
    argv = [p, "-m", model_path, "-n", str(N_GEN), "-ngl", str(ngl), "-c", str(GEN_CTX),
            "--temp", "0", "--seed", "1", "-p", GEN_PROMPT]
    if name == "llama-completion" and "--no-conversation" in h:
        argv.append("-no-cnv")
    if name == "llama-cli" and "--single-turn" in h:
        argv.append("--single-turn")
    return argv


def cli_raw_argv(tools: dict, model_path: str) -> list[str]:
    # The original 2026-10-06 crash command, unchanged except stdin=/dev/null.
    return [tools["cli_path"], "-m", model_path, "-ngl", "99", "-c", "512",
            "-p", GEN_PROMPT, "-n", "32"]


def ppl_argv(tools: dict, model_path: str, ngl: int, corpus: Path) -> list[str]:
    return [tools["ppl_path"], "-m", model_path, "-f", str(corpus), "-c", str(PPL_CTX),
            "--chunks", str(PPL_CHUNKS), "-ngl", str(ngl)]


# ---------------------------------------------------------------- matrix
def build_cells() -> list[dict]:
    cells: list[dict] = []

    def add(label, model, kind, ngl, group, env=None, ref=None, corpus="text"):
        cells.append({"label": label, "model": model, "kind": kind, "ngl": ngl,
                      "env": env or {}, "ref": ref, "corpus": corpus, "group": group})

    add("ppl_cpu_tinyllama", "tinyllama", "ppl", 0, "A_antivacuity")
    add("ppl_cpu_tinyllama_scrambled", "tinyllama", "ppl", 0, "A_antivacuity", corpus="scrambled")
    for m in MODELS:
        add(f"gen_cpu_{m}", m, "gen", 0, "B_ref")
    add("gen_cpu_tinyllama_r2", "tinyllama", "gen", 0, "A_antivacuity", ref="gen_cpu_tinyllama")
    for m in ("q40", "qwen_q4km"):
        add(f"ppl_cpu_{m}", m, "ppl", 0, "B_ref")
    for n, grp in ((1, "C_ngl1"), (99, "D_full")):
        for m in MODELS:
            add(f"gen_vk{n}_{m}", m, "gen", n, grp, ref=f"gen_cpu_{m}")
            add(f"ppl_vk{n}_{m}", m, "ppl", n, grp, ref=f"ppl_cpu_{m}")
    for n in BISECT_NGL:
        if n not in (1, 99):
            add(f"gen_vk{n}_tinyllama", "tinyllama", "gen", n, "E_bisect", ref="gen_cpu_tinyllama")
    for r in (1, 2, 3):
        add(f"cli_vk99_tinyllama_r{r}", "tinyllama", "cli_raw", 99, "F_repeat")
    for short, flag in EXPLORE_FLAGS:
        add(f"gen_vk1_tinyllama_{short}", "tinyllama", "gen", 1, "G_explore",
            env={flag: "1"}, ref="gen_cpu_tinyllama")
    return cells


# ---------------------------------------------------------------- parsing
ABORT_RE = re.compile(r"compute pipeline creation failed for (\S+?):")
PPL_RE = re.compile(r"Final estimate: PPL = ([0-9.]+) \+/- ([0-9.]+)")
OFFLOAD_RE = re.compile(r"offloaded (\d+)/(\d+) layers to GPU")
FTYPE_RE = re.compile(r"(?:file type\s*=|^ftype\s*:)\s*(.+?)\s*$", re.M)
SPEED_RE = re.compile(r"Prompt: ([0-9.]+) t/s \| Generation: ([0-9.]+) t/s")
GEN_CUTS = ("\n[ Prompt:", "\nllama_perf", "\nmain: decoded", "\n> ")


def extract_gen_text(stdout: str, stderr: str) -> str | None:
    for src in (stdout, stdout + "\n" + stderr):
        i = src.rfind(GEN_PROMPT)
        if i < 0:
            continue
        tail = src[i + len(GEN_PROMPT):]
        cut = min([tail.find(c) for c in GEN_CUTS if tail.find(c) >= 0] or [len(tail)])
        return tail[:cut]
    return None


def norm(s: str) -> str:
    return " ".join(s.split())


def parse(stdout: str, stderr: str) -> dict:
    both = stdout + "\n" + stderr
    a = ABORT_RE.search(both)
    p = PPL_RE.search(both)
    o = OFFLOAD_RE.search(both)
    f = FTYPE_RE.search(both)
    s = SPEED_RE.findall(both)
    return {
        "abort_pipeline": a.group(1) if a else None,
        "uncaught_exception": "terminating due to uncaught exception" in both,
        "ppl": float(p.group(1)) if p else None,
        "ppl_err": float(p.group(2)) if p else None,
        "offload": [int(o.group(1)), int(o.group(2))] if o else None,
        "ftype": f.group(1) if f else None,
        "vulkan_in_log": ("Vulkan0" in both) or ("ggml_vulkan" in both),
        "speeds_not_benchmark": s[-1] if s else None,
    }


# ---------------------------------------------------------------- preflight
def preflight(tools: dict) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    corpus_t, corpus_s = OUT / "corpus_text.txt", OUT / "corpus_scrambled.txt"
    corpus_t.write_text(CORPUS, encoding="utf-8")
    corpus_s.write_text(scrambled(CORPUS), encoding="utf-8")

    pf = {"t": now(), "harness": VERSION, "harness_sha256": sha256_file(Path(__file__)),
          "prereg_sha256": sha256_file(PREREG) if PREREG.exists() else None,
          "uname": list(platform.uname()), "python": sys.version.split()[0],
          "cpu_count": os.cpu_count(), "telemetry": telemetry(),
          "corpus_sha256": {"text": sha256_file(corpus_t), "scrambled": sha256_file(corpus_s)},
          "tools": {k: v for k, v in tools.items() if k != "gen_help"}}

    pk = shutil.which("pkg")
    if pk:
        _, o, e = run_capture([pk, "list-installed"], timeout=120)
        pf["pkg_llama"] = [l for l in (o + e).splitlines() if l.startswith("llama-cpp")]
    bins = {}
    for b in ("llama-cli", "llama-completion", "llama-simple", "llama-perplexity", "llama-bench"):
        p = shutil.which(b)
        bins[b] = {"path": p, "sha256": sha256_file(Path(p)) if p else None}
    pf["binaries"] = bins

    prefix = Path(os.environ.get("PREFIX", "/data/data/com.termux/files/usr"))
    vk = prefix / "lib" / "libggml-vulkan.so"
    if vk.exists():
        data = vk.read_bytes()
        pf["libggml_vulkan"] = {
            "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
            "env_vars": sorted({m.decode() for m in re.findall(rb"GGML_VK_[A-Z0-9_]+", data)})}
    else:
        pf["libggml_vulkan"] = None

    if tools["cli_path"]:
        rc, o, e = run_capture([tools["cli_path"], "--list-devices"], timeout=60)
        pf["list_devices"] = {"rc": rc, "out": (o + e)[-4000:]}
    else:
        pf["list_devices"] = None

    mods = {}
    for k, m in MODELS.items():
        p = m["path"]
        if not p.exists():
            mods[k] = {"path": str(p), "exists": False, "usable": False}
            continue
        h = sha256_file(p)
        match = None if m["sha256"] is None else (h == m["sha256"])
        mods[k] = {"path": str(p), "exists": True, "bytes": p.stat().st_size,
                   "sha256": h, "expected": m["sha256"], "match": match,
                   "pinned": m["sha256"] is not None, "usable": match is not False}
    pf["models"] = mods

    with open(PREFLIGHTS, "a", encoding="utf-8") as f:
        f.write(json.dumps(pf, sort_keys=True) + "\n")
        f.flush()
        os.fsync(f.fileno())
    return pf


# ---------------------------------------------------------------- running
def load_results() -> dict:
    recs = {}
    if RESULTS.exists():
        for line in RESULTS.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue  # a line torn by a kill mid-write
            recs[r["label"]] = r
    return recs


def load_preflights() -> list:
    out = []
    if PREFLIGHTS.exists():
        for line in PREFLIGHTS.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


def append_result(rec: dict) -> None:
    with open(RESULTS, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, sort_keys=True) + "\n")
        f.flush()
        os.fsync(f.fileno())


def run_cell(cell: dict, tools: dict, pf: dict) -> dict:
    m = pf["models"][cell["model"]]
    mp = m["path"]
    if cell["kind"] == "gen":
        argv, timeout, tool = gen_argv(tools, mp, cell["ngl"]), TIMEOUT_GEN, tools["gen"]
    elif cell["kind"] == "ppl":
        corpus = OUT / ("corpus_scrambled.txt" if cell["corpus"] == "scrambled" else "corpus_text.txt")
        argv, timeout, tool = ppl_argv(tools, mp, cell["ngl"], corpus), TIMEOUT_PPL, "llama-perplexity"
    else:
        argv, timeout, tool = cli_raw_argv(tools, mp), TIMEOUT_CLI_RAW, "llama-cli-raw"

    env = os.environ.copy()
    env.update(cell["env"])
    before = telemetry()
    t0 = time.monotonic()
    rc, so, se = run_capture(argv, env=env, timeout=timeout)
    wall = round(time.monotonic() - t0, 2)
    after = telemetry()

    log = LOGS / f"{cell['label']}.log"
    with open(log, "w", encoding="utf-8") as f:
        f.write(f"# {cell['label']} {now()}\n# argv: {json.dumps(argv)}\n")
        f.write(f"# env flags: {json.dumps(cell['env'])}\n# rc: {rc}  wall_s: {wall}\n")
        f.write("# ---- stdout ----\n" + so + "\n# ---- stderr ----\n" + se + "\n")

    rec = dict(cell)
    rec.update({"t": now(), "tool": tool, "argv": argv, "rc": rc, "wall_s": wall,
                "model_sha256": m.get("sha256"), "telemetry_before": before,
                "telemetry_after": after, "log": str(log),
                "gen_text": extract_gen_text(so, se) if cell["kind"] == "gen" else None})
    rec.update(parse(so, se))
    return rec


# ---------------------------------------------------------------- evaluation
def classify(rec: dict | None, recs: dict) -> str:
    if rec is None:
        return "NOT_RUN"
    if rec.get("tool_missing"):
        return "TOOL_MISSING"
    rc = rec.get("rc")
    if rec.get("abort_pipeline") or (isinstance(rc, int) and rc != 0):
        return "ABORT"
    if isinstance(rc, str) and rc.startswith("oserror"):
        return "ABORT"
    if rec["kind"] == "cli_raw":
        return "COMPLETED"  # did not abort; correctness not assessed for this cell
    ref = recs.get(rec.get("ref")) if rec.get("ref") else None
    if rec["kind"] == "gen":
        if rec.get("gen_text") is None:
            return "UNPARSED"
        if rec.get("ref") is None:
            return "REF" if rec["gen_text"].strip() else "EMPTY"
        if ref is None or ref.get("gen_text") is None or classify(ref, recs) not in ("REF",):
            return "NO_REF"
        if ref.get("tool") != rec.get("tool"):
            return "TOOL_MISMATCH"
        r, g = norm(ref["gen_text"]), norm(rec["gen_text"])
        k = min(GEN_MATCH_CHARS, len(r))
        if k == 0:
            return "NO_REF"
        return "CORRECT" if len(g) >= k and g[:k] == r[:k] else "INCORRECT"
    # ppl
    if rec.get("ppl") is None:
        return "UNPARSED"
    if rec.get("ref") is None:
        return "REF"
    if ref is None or ref.get("ppl") is None:
        return "NO_REF"
    return "CORRECT" if rec["ppl"] / ref["ppl"] <= PPL_TOL else "INCORRECT"


def evaluate(recs: dict, pfs: list) -> list[tuple[str, str, str]]:
    st = {lbl: classify(r, recs) for lbl, r in recs.items()}

    def s(lbl):
        return st.get(lbl, "NOT_RUN")

    out = []

    def verdict(pid, cond, detail):
        out.append((pid, cond, detail))

    # P1
    ld = pfs[-1].get("list_devices") if pfs else None
    if ld is None:
        verdict("P1", "INDETERMINATE", "no --list-devices record")
    else:
        ok = "Adreno (TM) 830" in ld["out"] and "Vulkan" in ld["out"]
        verdict("P1", "HELD" if ok else "REFUTED", "Adreno 830 listed under Vulkan" if ok else "not listed")
    # P2a
    a, b = recs.get("ppl_cpu_tinyllama"), recs.get("ppl_cpu_tinyllama_scrambled")
    if a and b and a.get("ppl") and b.get("ppl"):
        ratio = b["ppl"] / a["ppl"]
        verdict("P2a", "HELD" if ratio >= SCRAMBLE_MIN_RATIO else "REFUTED", f"scrambled/text = {ratio:.2f}")
    else:
        verdict("P2a", "INDETERMINATE", "PPL missing (llama-perplexity absent or unparsed?)")
    # P2b
    x = s("gen_cpu_tinyllama_r2")
    verdict("P2b", {"CORRECT": "HELD", "INCORRECT": "REFUTED"}.get(x, "INDETERMINATE"), x)
    # P3
    cpu = [recs.get(f"gen_cpu_{m}") for m in MODELS]
    if any(r is None for r in cpu):
        verdict("P3", "INDETERMINATE", "a CPU reference is missing")
    else:
        ok = all(s(r["label"]) == "REF" for r in cpu)
        verdict("P3", "HELD" if ok else "REFUTED", ", ".join(s(r["label"]) for r in cpu))
    # P4-P7: predicted INCORRECT
    for pid, lbl in (("P4", "gen_vk1_tinyllama"), ("P5", "ppl_vk1_tinyllama"),
                     ("P6", "gen_vk1_q40"), ("P7", "gen_vk1_qwen_q4km")):
        x = s(lbl)
        verdict(pid, {"INCORRECT": "HELD", "CORRECT": "REFUTED"}.get(x, "INDETERMINATE"), f"{lbl} = {x}")
    # P8
    reps = [recs.get(f"cli_vk99_tinyllama_r{r}") for r in (1, 2, 3)]
    if any(r is None for r in reps) or not all(r.get("tool") == "llama-cli-raw" for r in reps):
        verdict("P8", "INDETERMINATE", "repeats missing or llama-cli absent")
    else:
        ab = [s(r["label"]) == "ABORT" and r.get("abort_pipeline") for r in reps]
        verdict("P8", "HELD" if all(ab) else "REFUTED",
                " / ".join(f"{s(r['label'])}:{r.get('abort_pipeline')}" for r in reps))
    # P9
    seq = [(n, s(f"gen_vk{n}_tinyllama")) for n in BISECT_NGL]
    if any(x in ("NOT_RUN", "TOOL_MISSING") for _, x in seq):
        verdict("P9", "INDETERMINATE", "bisection incomplete")
    else:
        flags = [x == "ABORT" for _, x in seq]
        mono = all(flags[i] <= flags[i + 1] for i in range(len(flags) - 1))
        onset = next((n for n, f in zip(BISECT_NGL, flags) if f), None)
        held = mono and not flags[0]
        verdict("P9", "HELD" if held else "REFUTED",
                f"monotone={mono} onset_ngl={onset} " + " ".join(f"{n}:{x}" for n, x in seq))
    return out


def report() -> int:
    recs, pfs = load_results(), load_preflights()
    st = {lbl: classify(r, recs) for lbl, r in recs.items()}
    print(f"== VK-1 report ({VERSION}) ==")
    if pfs:
        p = pfs[-1]
        print(f"preflight {p['t']}  prereg_sha256={p.get('prereg_sha256')}")
        print(f"gen tool: {p['tools'].get('gen')}  ppl tool: {p['tools'].get('ppl_path')}")
        for k, m in p["models"].items():
            tag = "UNPINNED" if not m.get("pinned") else ("ok" if m.get("match") else "HASH MISMATCH")
            print(f"  model {k}: {'present' if m.get('exists') else 'MISSING'} {tag} {m.get('sha256', '')[:16]}")
    print("\n-- cells --")
    for c in build_cells():
        r = recs.get(c["label"])
        x = st.get(c["label"], "NOT_RUN")
        extra = ""
        if r:
            if r.get("abort_pipeline"):
                extra = f"abort={r['abort_pipeline']}"
            elif r.get("ppl") is not None:
                extra = f"ppl={r['ppl']:.3f}"
            elif r.get("gen_text") is not None:
                extra = "text=" + json.dumps(norm(r["gen_text"])[:40], ensure_ascii=False)
            mem = (r.get("telemetry_before") or {}).get("mem_kb") or {}
            if mem.get("MemAvailable"):
                extra += f"  avail={mem['MemAvailable'] // 1024}MiB"
            if r.get("offload"):
                extra += f"  offload={r['offload'][0]}/{r['offload'][1]}"
        print(f"  {c['label']:<34} {x:<13} rc={r.get('rc') if r else '-'!s:<8} {extra}")

    print("\n-- registered predictions (P4-P7 predict FAILURE of the Vulkan path) --")
    res = evaluate(recs, pfs)
    for pid, cond, d in res:
        print(f"  {pid:<4} {cond:<13} {d}")
    det = [r for r in res if r[1] != "INDETERMINATE"]
    held = tuple(pid for pid, cond, _ in res if cond == "HELD")
    print(f"\nVERDICT {len(held)} of {len(det)} determinate predictions held as registered "
          f"({len(res) - len(det)} indeterminate of {len(res)})")

    print("\n-- exploratory (no predictions) --")
    for short, flag in EXPLORE_FLAGS:
        print(f"  {flag:<42} {st.get(f'gen_vk1_tinyllama_{short}', 'NOT_RUN')}")

    print("\n-- labels the evidence allows --")
    for m in MODELS:
        good = [c["label"] for c in build_cells()
                if c["model"] == m and c["ngl"] > 0 and st.get(c["label"]) == "CORRECT"
                and c["group"] != "G_explore"]
        if not good:
            print(f"  {m}: Vulkan inference with correct output NOT DEMONSTRATED")
            continue
        r = recs[good[0]]
        lab = "llama.cpp Vulkan inference on Adreno 830 demonstrated (correct output)"
        if not r.get("vulkan_in_log"):
            lab = "correct output, but Vulkan not evidenced in log: NOT DEMONSTRATED"
        elif not r.get("offload"):
            lab += "; offload not evidenced in log"
        print(f"  {m}: {lab} [{', '.join(good)}]")

    canon = json.dumps({k: st[k] for k in sorted(st)}, sort_keys=True)
    digest = sha256_text(canon)
    print(f"\nDIGEST {digest}")
    if RECORDED is not None:
        same = RECORDED["digest"] == digest and tuple(RECORDED["held"]) == held
        print("RECORDED match" if same else "RECORDED MISMATCH")
        return 0 if same else 1
    print("RECORDED not pinned yet (first device run pins it, as a separate step)")
    print("NOT VALIDATED on the S25 until this report comes from a device run.")
    return 0


# ---------------------------------------------------------------- main
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--preflight", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--only", action="append", default=[])
    ap.add_argument("--force", action="store_true", help="re-run cells already recorded")
    a = ap.parse_args(argv)

    cells = build_cells()
    if a.plan:
        for c in cells:
            env = " ".join(f"{k}=1" for k in c["env"])
            print(f"{c['group']:<14} {c['label']:<34} {c['kind']:<8} ngl={c['ngl']:<3} {env}")
        print(f"{len(cells)} cells")
        return 0
    if a.report:
        return report()

    unknown = [o for o in a.only if o not in {c["label"] for c in cells}]
    if unknown:
        print(f"unknown label(s): {unknown}", file=sys.stderr)
        return 2

    tools = select_tools()
    pf = preflight(tools)
    print(f"preflight written; prereg_sha256={pf['prereg_sha256']}")
    print(f"gen tool={tools['gen']}  ppl tool={tools['ppl_path']}  llama-cli={tools['cli_path']}")
    if pf["prereg_sha256"] is None:
        print("WARNING: VK1_PREREG.md not found next to the harness; registration not recorded.")
    for k, m in pf["models"].items():
        if not m["usable"]:
            print(f"EXCLUDED model {k}: exists={m['exists']} match={m.get('match')}")
    if a.preflight:
        return 0

    done = load_results()
    prev_tools = {r.get("tool") for r in done.values() if r.get("kind") == "gen"}
    if prev_tools and tools["gen"] not in prev_tools:
        print(f"WARNING: earlier gen cells used {prev_tools}, this session uses {tools['gen']}; "
              "comparisons across tools are classified TOOL_MISMATCH.")

    for c in cells:
        if a.only and c["label"] not in a.only:
            continue
        if c["label"] in done and not a.force:
            continue
        if not pf["models"][c["model"]]["usable"]:
            print(f"skip {c['label']}: model {c['model']} excluded")
            continue
        need = {"gen": tools["gen_path"], "ppl": tools["ppl_path"], "cli_raw": tools["cli_path"]}[c["kind"]]
        if need is None:
            # Not recorded: the cell stays NOT_RUN and runs once the tool exists.
            print(f"{c['label']:<34} TOOL_MISSING (not recorded)")
            continue
        mem = meminfo() or {}
        if mem.get("MemAvailable") and mem["MemAvailable"] < MEM_WARN_KB:
            print(f"WARNING: MemAvailable {mem['MemAvailable'] // 1024} MiB before {c['label']}")
        print(f"{c['label']:<34} running ...", end="", flush=True)
        rec = run_cell(c, tools, pf)
        append_result(rec)
        done[c["label"]] = rec
        print(f"\r{c['label']:<34} {classify(rec, done):<13} rc={rec['rc']} {rec['wall_s']}s")

    print()
    return report()


if __name__ == "__main__":
    sys.exit(main())
