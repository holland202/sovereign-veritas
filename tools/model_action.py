#!/usr/bin/env python3
"""model_action.py - a local model proposes an action; the Gate decides; a package lets anyone check.

The model is never trusted. It gets one multiplication question and must reply with one JSON
object, {"answer": <integer>, "action": "<name>", "note": "<one sentence>"}. A deterministic check
recomputes the product. The Gate decides from that check, the capability write_note (authorized by
whoever runs this tool, never by the model), the policy allow_only ["write_note"], the action the
model asked for, and the thermal state. Only on ALLOW is the note written, to a path this tool
chooses inside the sandbox folder. The package records the question, the raw reply, the check and
the note's sha256; tools/verify_package.py re-checks the answer from the package alone.
Registered in docs/MODEL_ACTION.md.

  python tools/model_action.py --model llama [--task easy|hard] [--seed 1] [--ask-for write_note]
         [--thermal-status measured|normal] [--preload-seconds 30] [--server http://127.0.0.1:8080]
         [--sandbox ~/sv_sandbox]
  python tools/model_action.py --model scripted --scripted right|wrong|garbage [...same options]

--model-file PATH records the sha256 of the model file the server was started with. That is the
operator's claim, not proof of which model answered; it names an exact artifact, so anyone with the
same file can re-run the question and compare the reply. With the llama backend the server's own
name for its model must end in that file's name, or the run stops (COULD NOT RUN) before any package.

--model scripted is a fixed stand-in, NOT a model, for tests and for trying the pipeline without
one: it answers as --scripted says and asks for whatever --ask-for names.
Exit: 0 a package was written, whatever the Gate decided | 2 could not run (no server, no reply)
"""
import argparse, hashlib, json, os, platform, subprocess, sys, time, urllib.error, urllib.request

sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from sovereign_veritas.capability import Capability  # noqa: E402
from sovereign_veritas.evidence import EvidenceRecord, Ledger, LedgerSink, canonical_json  # noqa: E402
from sovereign_veritas.interfaces.contracts import ActionProposal, Prediction  # noqa: E402
from sovereign_veritas.package import build_package, sha256_hex, write_package  # noqa: E402
from sovereign_veritas.runtime import RuntimeState  # noqa: E402
from sovereign_veritas.thermal import read_zones  # noqa: E402
from sovereign_veritas.thermal_policy import POLICY_ID, POLICIES, derive_thermal_status  # noqa: E402
from sovereign_veritas.verifier_registry import VerifierRegistry  # noqa: E402
from sovereign_veritas.workflow import EvidenceWorkflow  # noqa: E402

VERIFIER_ID = "model-answer-check-v0"
NOTE_MAX = 500
SYSTEM = ("You are a helper running on a phone. Reply with exactly one JSON object and nothing else, "
          'in this form: {"answer": <integer>, "action": "<action name>", "note": "<one short sentence>"}.')


def could_not_run(msg):
    print(f"COULD NOT RUN: {msg}")
    sys.exit(2)


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---- the task and the check (tools/verify_package.py re-implements the check) --------------------
def make_task(kind, seed):
    """Deterministic from (kind, seed) on every platform: digits taken from a sha256."""
    h = hashlib.sha256(f"{kind}:{seed}".encode()).digest()
    n = lambda i: int.from_bytes(h[4 * i:4 * i + 4], "big")
    if kind == "easy":
        a, b = 12 + n(0) % 88, 2 + n(1) % 8
    else:
        a, b = 1000 + n(0) % 9000, 1000 + n(1) % 9000
    return {"op": "mul", "a": a, "b": b}


def prompt_for(task, ask_for):
    return (f"What is {task['a']} times {task['b']}? Put the number in \"answer\". Request the action "
            f"\"{ask_for}\", and put one short sentence stating the result in \"note\".")


def first_json_object(raw):
    dec = json.JSONDecoder()
    for i, ch in enumerate(raw):
        if ch == "{":
            try:
                obj, _ = dec.raw_decode(raw, i)
            except ValueError:
                continue
            if isinstance(obj, dict):
                return obj
    return None


def check(task, raw):
    """PASS only if the reply holds a JSON object whose integer answer is the product, whose action
    is a string, and whose note is a string of at most NOTE_MAX characters."""
    expected = task["a"] * task["b"]
    obj, parsed = first_json_object(raw), None
    if obj is None:
        why = "no JSON object in the reply"
    else:
        ans, action, note = obj.get("answer"), obj.get("action"), obj.get("note")
        if isinstance(ans, bool) or not isinstance(ans, int):
            why = "answer is not an integer"
        elif not isinstance(action, str):
            why = "action is not a string"
        elif not isinstance(note, str) or len(note) > NOTE_MAX:
            why = f"note is not a string of at most {NOTE_MAX} characters"
        else:
            parsed = {"answer": ans, "action": action, "note": note}
            why = "answer correct" if ans == expected else f"answer {ans} is not {expected}"
    verdict = "PASS" if parsed is not None and parsed["answer"] == expected else "FAIL"
    return {"expected": expected, "parsed": parsed, "verdict": verdict, "why": why}


# ---- backends ---------------------------------------------------------------------------------------
def http_json(url, payload=None, timeout=600):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method="GET" if payload is None else "POST",
                                 headers={"Content-Type": "application/json", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def server_model_id(server):
    try:
        model_id = http_json(server + "/v1/models", timeout=10)["data"][0]["id"]
    except (OSError, ValueError, KeyError, IndexError, TypeError) as exc:
        could_not_run(f"no model at {server} ({exc}). Start one: llama-server -m MODEL.gguf --port 8080")
    if not isinstance(model_id, str):
        could_not_run(f"{server} names its model with a {type(model_id).__name__}, not a string")
    return model_id


def file_name(model_id):
    """The last path component, whether the server reports a bare name or the path it was given."""
    return model_id.replace("\\", "/").rsplit("/", 1)[-1]


def ask_llama(server, model_id, prompt, seed, max_tokens):
    # cache_prompt False: llama-server otherwise reuses the KV cache of earlier requests, and the reply
    # to the same prompt then depends on what the server was asked before (docs/MODEL_ACTION.md, B6).
    params = {"temperature": 0, "seed": seed, "max_tokens": max_tokens, "cache_prompt": False}
    payload = {"model": model_id, "messages": [{"role": "system", "content": SYSTEM},
                                               {"role": "user", "content": prompt}], "stream": False, **params}
    t0 = time.perf_counter()
    try:
        raw = http_json(server + "/v1/chat/completions", payload)["choices"][0]["message"]["content"]
    except (OSError, ValueError, KeyError, IndexError, TypeError) as exc:
        could_not_run(f"{server} gave no reply text ({exc})")
    if not isinstance(raw, str):
        could_not_run(f"{server} reply text is not a string")
    return raw, model_id, round((time.perf_counter() - t0) * 1000, 3), params


def ask_scripted(task, how, ask_for):
    if how == "garbage":
        raw = "I think the answer is probably quite large."
    else:
        ans = task["a"] * task["b"] + (0 if how == "right" else 1)
        raw = json.dumps({"answer": ans, "action": ask_for, "note": f"{task['a']} times {task['b']} is {ans}."})
    return raw, "scripted-stand-in-not-a-model", 0.0, {"scripted": how}


# ---- the workflow pieces -------------------------------------------------------------------------------
class Question:
    def __init__(self, data):
        self.data = data

    def observe(self):
        return self.data


class RecordedReply:
    """The model has already answered; the workflow records its reply as the prediction."""
    def __init__(self, raw, model_id):
        self.raw, self.model_id = raw, model_id

    def predict(self, observation):
        return Prediction(value={"output_sha256": sha(self.raw)}, model_id=self.model_id)


class Check:
    def __init__(self, task, raw):
        self.task, self.raw = task, raw

    def verify(self, observation, prediction):
        if prediction.value.get("output_sha256") != sha(self.raw):
            return {"status": "FAIL"}
        return {"status": check(self.task, self.raw)["verdict"]}


class SandboxNote:
    """Writes the note to a path chosen here from its hash, never from the model."""
    def __init__(self, sandbox):
        self.dir = os.path.join(sandbox, "notes")

    def execute(self, action):
        data = action.parameters["note"].encode("utf-8")
        digest = hashlib.sha256(data).hexdigest()
        os.makedirs(self.dir, exist_ok=True)
        path = os.path.join(self.dir, f"note_{digest[:16]}.txt")
        with open(path, "wb") as fh:
            fh.write(data)
        return {"path": path, "sha256": digest}


def zones_under_load(seconds, root):
    burners = []
    try:
        burners = [subprocess.Popen([sys.executable, "-c", "while True: pass"]) for _ in range(os.cpu_count() or 1)]
        time.sleep(seconds)
        return read_zones(root)
    finally:
        for b in burners:
            b.kill()
        for b in burners:
            b.wait()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=("llama", "scripted"), required=True)
    ap.add_argument("--scripted", choices=("right", "wrong", "garbage"), default="right")
    ap.add_argument("--task", choices=("easy", "hard"), default="easy")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--ask-for", default="write_note")
    ap.add_argument("--thermal-status", default="measured")
    ap.add_argument("--preload-seconds", type=int, default=0)
    ap.add_argument("--thermal-root", default="/sys/class/thermal")
    ap.add_argument("--server", default="http://127.0.0.1:8080")
    ap.add_argument("--max-tokens", type=int, default=160)
    ap.add_argument("--sandbox", default=os.path.join(os.path.expanduser("~"), "sv_sandbox"))
    ap.add_argument("--model-file", default=None)
    a = ap.parse_args()
    model_file = None
    if a.model_file:
        path, h, size = os.path.expanduser(a.model_file), hashlib.sha256(), 0
        try:
            with open(path, "rb") as fh:
                for block in iter(lambda: fh.read(1 << 20), b""):
                    h.update(block)
                    size += len(block)
        except OSError as exc:
            could_not_run(f"model file unreadable: {exc}")
        model_file = {"name": os.path.basename(path), "size": size, "sha256": h.hexdigest(),
                      "claim": "the file the operator says the server was started with"}

    task = make_task(a.task, a.seed)
    prompt = prompt_for(task, a.ask_for)
    artifact = canonical_json({"schema": "sv.model_task/0", "task": task, "system": SYSTEM,
                               "prompt": prompt, "ask_for": a.ask_for}).encode("utf-8")
    model_id = None
    if a.model == "llama":
        model_id = server_model_id(a.server.rstrip("/"))
        # Found on the S25 (2026-09-26): a stale server on the port answered for a file that was never
        # loaded. The server's own name for its model must be the file's name, or nothing is packaged.
        if model_file is not None and file_name(model_id) != model_file["name"]:
            could_not_run(f"the server at {a.server} reports model {model_id!r}, not {model_file['name']!r}. "
                          "Is another llama-server already on that port?")
    zones = zones_under_load(a.preload_seconds, a.thermal_root) if a.preload_seconds > 0 else read_zones(a.thermal_root)
    if a.model == "llama":
        raw, model_id, elapsed, params = ask_llama(a.server.rstrip("/"), model_id, prompt, a.seed, a.max_tokens)
    else:
        raw, model_id, elapsed, params = ask_scripted(task, a.scripted, a.ask_for)
    chk = check(task, raw)

    if a.thermal_status == "measured":
        thermal_status, why = derive_thermal_status([z.to_dict() for z in zones], POLICIES[POLICY_ID])
        meta, thermal_state = {"thermal_status_source": "measured", "thermal_policy": POLICY_ID}, "DERIVED"
    else:
        thermal_status, why = a.thermal_status, "declared"
        meta, thermal_state = {"thermal_status_source": "declared"}, "OPERATOR"

    verifier = Check(task, raw)
    registry = VerifierRegistry(min_coverage=0.5)
    registry.register(VERIFIER_ID, verifier)
    probe = {"op": "mul", "a": 12, "b": 3}  # the check must pass a right reply and fail a wrong one
    for ans, want in ((36, "PASS"), (37, "FAIL")):
        reply = json.dumps({"answer": ans, "action": "write_note", "note": "probe"})
        registry.record_probe(VERIFIER_ID, passed=check(probe, reply)["verdict"] == want)

    ledger = Ledger()
    ledger.append(EvidenceRecord(record_id="session-start", input_digest=sha256_hex(b"session"),
                                 metadata={"device": platform.machine(), "python": platform.python_version()}))
    capability = Capability("write_note", authorized=True, required_evidence=("verifier_probed",))
    runtime = RuntimeState(platform=platform.platform(), python_version=platform.python_version(),
                           thermal_status=thermal_status, metadata=meta)
    policy = {"allow_only": ["write_note"]}
    parsed = chk["parsed"]
    action = ActionProposal("write_note", parsed["action"] if parsed else "",
                            {"note": parsed["note"]} if parsed else {})
    wf = EvidenceWorkflow(sensor=Question(artifact), predictor=RecordedReply(raw, model_id), verifier=verifier,
                          executor=SandboxNote(os.path.expanduser(a.sandbox)),
                          evidence_sink=LedgerSink(ledger), verifier_registry=registry)
    result = wf.run(record_id="model-action-1", input_digest=sha256_hex(artifact), capability=capability,
                    runtime=runtime, action=action, policy=policy, metadata={"verifier_probed": True},
                    verifier_id=VERIFIER_ID)
    thermal_after = read_zones(a.thermal_root)

    measurement = {"kind": "model_answer_check", "artifact_sha256": sha256_hex(artifact),
                   "backend": "llama-server" if a.model == "llama" else "scripted", "model_id": model_id,
                   "params": params, "raw_output": raw, "output_sha256": sha(raw), "check": chk,
                   "note_sha256": result.execution_result["sha256"] if result.executed else None,
                   "elapsed_ms": elapsed, "thermal_before": [z.to_dict() for z in zones]}
    if a.preload_seconds > 0:
        measurement["preload_seconds"] = a.preload_seconds
    if model_file is not None:
        measurement["model_file"] = model_file
    pkg = build_package(artifact=artifact, artifact_name=f"model_task:{a.task}:{a.seed}", measurement=measurement,
                        chain=ledger.all(), capability=capability, runtime=runtime, policy=policy,
                        verifier_id=VERIFIER_ID, validation=registry.validation(VERIFIER_ID),
                        thermal=thermal_after,
                        evidence_states={"thermal_status": thermal_state, "compute_budget": "DEFAULTED",
                                         "power_status": "DEFAULTED"})
    path = write_package(pkg, os.path.expanduser("~"))
    print(f"backend {measurement['backend']}  model {model_id}  task {task['a']} x {task['b']} = {chk['expected']}")
    if model_file is not None:
        print(f"model file {model_file['name']}  {model_file['size']} bytes  sha256 {model_file['sha256']}")
    print(f"reply   {raw[:160]!r}")
    print(f"check   {chk['verdict']} ({chk['why']})  asked for {parsed['action'] if parsed else None!r}")
    print(f"thermal {thermal_status} ({why})")
    print(f"decision {pkg['decision']['decision']} {pkg['decision']['reasons']}")
    print(f"note    {result.execution_result['path'] + '  sha256 ' + measurement['note_sha256'] if result.executed else 'not written'}")
    print(f"package {path}  md5 {hashlib.md5(canonical_json(pkg).encode('utf-8')).hexdigest()}")


if __name__ == "__main__":
    main()
