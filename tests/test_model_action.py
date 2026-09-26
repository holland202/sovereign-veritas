"""A local model proposes an action (tools/model_action.py). Registered in docs/MODEL_ACTION.md (A1-A9).

The "scripted" backend is a fixed stand-in, not a model. The llama backend is exercised against a
local HTTP server speaking llama-server's API, so no model is needed here.
"""
import copy
import hashlib
import http.server
import json
import os
import pathlib
import re
import socket
import subprocess
import sys
import threading

import pytest

from test_thermal_policy import ROOT, failed, reseal, tree, vp

TOOL = ROOT / "tools" / "model_action.py"


def run(tmp_path, *flags, hot=False):
    zones = tmp_path / ("hot" if hot else "cool")
    if not zones.exists():
        tree(zones, {"cpu-0-0-0": 99600} if hot else None)
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    p = subprocess.run([sys.executable, str(TOOL), *flags, "--thermal-root", str(zones),
                        "--sandbox", str(tmp_path / "sandbox")], capture_output=True, text=True,
                       env=dict(os.environ, HOME=str(home)), timeout=300)
    if p.returncode != 0:
        return None, p
    path = next(line.split()[1] for line in p.stdout.splitlines() if line.startswith("package "))
    pkg = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    os.remove(path)
    return pkg, p


def notes(tmp_path):
    d = tmp_path / "sandbox" / "notes"
    return sorted(d.iterdir()) if d.exists() else []


# ---- A1-A6 --------------------------------------------------------------------------------------------
@pytest.mark.parametrize("how,ask_for,hot,decision,reasons", [
    ("right", "write_note", False, "ALLOW", []),                                        # A1
    ("wrong", "write_note", False, "REFUSE", ["verification_not_passed"]),              # A2
    ("garbage", "write_note", False, "REFUSE", ["verification_not_passed"]),            # A3
    ("right", "delete_file", False, "REFUSE", ["action_not_permitted_by_policy"]),      # A4
    ("right", "write_note", True, "DEFER", ["runtime_not_healthy"]),                    # A5
])
def test_a1_a6_decision_note_and_verification(tmp_path, how, ask_for, hot, decision, reasons):
    pkg, _ = run(tmp_path, "--model", "scripted", "--scripted", how, "--ask-for", ask_for, hot=hot)
    assert [pkg["decision"]["decision"], pkg["decision"]["reasons"]] == [decision, reasons]
    written = notes(tmp_path)
    note_sha = pkg["measurement"]["note_sha256"]
    if decision == "ALLOW":
        assert len(written) == 1 and hashlib.sha256(written[0].read_bytes()).hexdigest() == note_sha
    else:
        assert written == [] and note_sha is None
    results = {n: ok for n, ok, _ in vp.verify(pkg)}
    assert all(results.values()) and results.get("model_check_bound") is True
    assert pkg["measurement"]["backend"] == "scripted"


# ---- A7: a resealing attacker ------------------------------------------------------------------------------
def pkg_for(tmp_path, how, ask_for="write_note"):
    return run(tmp_path, "--model", "scripted", "--scripted", how, "--ask-for", ask_for)[0]


def set_decision(p, decision, reasons):
    p["decision"] = {"decision": decision, "reasons": reasons}
    rec = p["provenance"]["chain"][-1]["record"]
    rec["decision"], rec["reasons"] = decision, reasons
    return rec


def test_a7_wrong_answer_record_flipped_to_pass_and_allow(tmp_path):
    p = pkg_for(tmp_path, "wrong")
    set_decision(p, "ALLOW", [])["verification"]["status"] = "PASS"
    assert failed(reseal(p)) == ["model_check_bound"]


def test_a7_model_asked_to_delete_but_the_record_says_write(tmp_path):
    p = pkg_for(tmp_path, "right", "delete_file")
    set_decision(p, "ALLOW", [])["action"]["requested"] = "write_note"
    assert failed(reseal(p)) == ["model_check_bound"]


def test_a7_note_hash_changed(tmp_path):
    p = pkg_for(tmp_path, "right")
    p["measurement"]["note_sha256"] = "0" * 64
    assert failed(reseal(p)) == ["model_check_bound"]


def test_a7_note_hash_added_where_nothing_ran(tmp_path):
    p = pkg_for(tmp_path, "wrong")
    p["measurement"]["note_sha256"] = hashlib.sha256(b"x").hexdigest()
    assert failed(reseal(p)) == ["model_check_bound"]


def test_a7_note_in_the_record_changed(tmp_path):
    p = pkg_for(tmp_path, "right")
    p["provenance"]["chain"][-1]["record"]["action"]["parameters"]["note"] = "something else"
    assert failed(reseal(p)) == ["model_check_bound"]


def test_a7_recorded_check_edited(tmp_path):
    p = pkg_for(tmp_path, "wrong")
    p["measurement"]["check"]["verdict"] = "PASS"
    assert "measurement_recomputed" in failed(reseal(p))


def test_a7_stated_limit_rewriting_the_reply_itself_verifies_unsigned(tmp_path):
    """Documented, not a pass: the raw reply is recorded data; only a signature binds it."""
    p = pkg_for(tmp_path, "wrong")
    m = p["measurement"]
    task = json.loads(__import__("base64").b64decode(p["artifact"]["bytes_b64"]))["task"]
    ans = task["a"] * task["b"]
    m["raw_output"] = json.dumps({"answer": ans, "action": "write_note", "note": "forged"})
    m["output_sha256"] = hashlib.sha256(m["raw_output"].encode()).hexdigest()
    m["check"] = vp.model_check(task, m["raw_output"])
    rec = set_decision(p, "ALLOW", [])
    rec["verification"]["status"] = "PASS"
    rec["prediction"]["value"]["output_sha256"] = m["output_sha256"]
    rec["action"]["parameters"] = {"note": "forged"}
    assert failed(reseal(p)) == []


# ---- A8: the llama backend, against a stand-in server ------------------------------------------------------
class FakeLlama(http.server.BaseHTTPRequestHandler):
    """Speaks llama-server's /v1/models and /v1/chat/completions; multiplies correctly."""
    def log_message(self, *args):
        pass

    def reply(self, obj):
        body = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self.reply({"data": [{"id": "fake-llama-for-tests"}]})

    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        a, b = map(int, re.search(r"What is (\d+) times (\d+)", req["messages"][-1]["content"]).groups())
        text = "```json\n" + json.dumps({"answer": a * b, "action": "write_note", "note": f"{a*b}."}) + "\n```"
        self.reply({"choices": [{"message": {"content": text}}]})


def test_a8_llama_backend_against_a_stand_in_server(tmp_path):
    server = http.server.HTTPServer(("127.0.0.1", 0), FakeLlama)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        pkg, p = run(tmp_path, "--model", "llama", "--server", f"http://127.0.0.1:{server.server_port}")
    finally:
        server.shutdown()
    assert pkg is not None, p.stdout + p.stderr
    assert pkg["decision"]["decision"] == "ALLOW" and pkg["measurement"]["model_id"] == "fake-llama-for-tests"
    assert pkg["measurement"]["backend"] == "llama-server" and all(ok for _, ok, _ in vp.verify(pkg))


def test_a8_no_server_is_could_not_run_not_a_package(tmp_path):
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()  # nothing listens here now
    pkg, p = run(tmp_path, "--model", "llama", "--server", f"http://127.0.0.1:{port}")
    assert pkg is None and p.returncode == 2 and "COULD NOT RUN" in p.stdout


def test_tasks_are_the_same_on_every_platform():
    """make_task derives the numbers from sha256, not from random, so B1-B4 are reproducible."""
    spec = __import__("importlib.util").util.spec_from_file_location("model_action", TOOL)
    ma = __import__("importlib.util").util.module_from_spec(spec)
    spec.loader.exec_module(ma)
    assert ma.make_task("easy", 1) == {"op": "mul", "a": 23, "b": 8}
    assert ma.make_task("hard", 1)["a"] >= 1000 and ma.make_task("hard", 1)["b"] >= 1000


def test_model_file_hash_is_recorded_and_the_package_still_verifies(tmp_path):
    f = tmp_path / "model.gguf"
    f.write_bytes(b"not really a model" * 1000)
    pkg, _ = run(tmp_path, "--model", "scripted", "--model-file", str(f))
    mf = pkg["measurement"]["model_file"]
    assert mf["sha256"] == hashlib.sha256(f.read_bytes()).hexdigest() and mf["size"] == f.stat().st_size
    assert all(ok for _, ok, _ in vp.verify(pkg))


def test_an_unreadable_model_file_is_could_not_run(tmp_path):
    pkg, p = run(tmp_path, "--model", "scripted", "--model-file", str(tmp_path / "missing.gguf"))
    assert pkg is None and p.returncode == 2 and "model file unreadable" in p.stdout

