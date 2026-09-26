#!/usr/bin/env python3
"""nvidia_challenge.py - EXPLORATORY red team for sv.package/0 using an NVIDIA-hosted model.

The model tries to forge an evidence package that your LOCAL verifier accepts. It only proposes
edits. This tool applies them, recomputes every digest (the attacker's best move - models cannot
compute sha256), and runs tools/verify_package.py on this device. The model decides nothing.

SENT TO NVIDIA: the package JSON (artifact bytes, device platform string, thermal readings) and
the verifier's source code. Nothing else. Key read from ~/.nvidia_api_key and never printed.
Log written to ~/sv_challenge_<unix time>.json (not the repo).

  python nvidia_challenge.py --package ~/sv_package_X.json [--repo ~/sovereign-veritas]
         [--model ID] [--rounds 5] [--list-models]
Exit: 0 no new forgery accepted | 1 a forgery outside the known limits was accepted | 2 could not run
"""
import argparse, copy, importlib.util, json, os, re, sys, time, urllib.error, urllib.request

sys.dont_write_bytecode = True
BASE = "https://integrate.api.nvidia.com/v1"
PREFERRED = ("openai/gpt-oss-120b", "nvidia/nemotron-3-super-120b-a12b",
             "deepseek-ai/deepseek-v4-pro", "meta/llama-3.3-70b-instruct",
             "meta/llama-3.1-70b-instruct")
KNOWN_LIMITS = """Known limits - a forgery using ONLY these does not count:
K1 consistent rewrite: change declared inputs (runtime, policy, capability) AND the decision to
   what the Gate would decide from them.
K2 recorded-only values: elapsed_ms, artifact name, earlier chain records, a thermal zone's raw
   value together with a matching summary.
(A measurement-kind downgrade used to pass; the verifier now refuses it. Try it if you like.)"""
KNOWN_PATHS = (("decision",), ("resource_state", "runtime"), ("gate_inputs",),
               ("measurement", "elapsed_ms"),
               ("artifact", "name"), ("resource_state", "thermal"))


def fail(msg):
    print(f"COULD NOT RUN: {msg}")
    sys.exit(2)


def load_key():
    path = os.path.expanduser("~/.nvidia_api_key")
    try:
        with open(path, encoding="utf-8") as fh:
            key = fh.read().strip()
    except OSError:
        fail(f"no key at {path}")
    if not key.startswith("nvapi-"):
        fail("key file does not start with nvapi-")
    return key


def api(base, key, path, payload=None, *, retries=3, timeout=180):
    """GET is fatal on failure (setup); POST retries with backoff and raises RuntimeError,
    which a round can catch instead of the whole run dying on one slow request."""
    req_data = None if payload is None else json.dumps(payload).encode()
    last = None
    for attempt in range(retries):
        req = urllib.request.Request(base + path, data=req_data,
                                     headers={"Authorization": f"Bearer {key}", "Accept": "application/json",
                                              "Content-Type": "application/json"},
                                     method="GET" if payload is None else "POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:300]
            if payload is None:
                fail(f"HTTP {e.code} on {path}: {body}")
            if e.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                time.sleep(2 ** attempt)
                last = f"HTTP {e.code}: {body}"
                continue
            raise RuntimeError(f"HTTP {e.code}: {body}")
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if payload is None:
                fail(f"network error on {path}: {e}")
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
                last = str(e)
                continue
            raise RuntimeError(f"network error after {retries} attempts: {e}")
    raise RuntimeError(last or "request failed")


def chat_stream(base, key, payload, *, retries=3, idle_timeout=120):
    """Streamed chat completion. The timeout applies between chunks, not to the whole reply,
    so a slow-but-alive model is not cut off. Returns (content, reasoning) or raises RuntimeError."""
    data = json.dumps(dict(payload, stream=True)).encode()
    last = "request failed"
    for attempt in range(retries):
        req = urllib.request.Request(base + "/chat/completions", data=data, method="POST",
                                     headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                                              "Accept": "text/event-stream"})
        content, reasoning = [], []
        try:
            with urllib.request.urlopen(req, timeout=idle_timeout) as r:
                for raw in r:
                    line = raw.decode("utf-8", "replace").strip()
                    if not line.startswith("data:"):
                        continue
                    chunk = line[5:].strip()
                    if chunk == "[DONE]":
                        break
                    try:
                        delta = json.loads(chunk)["choices"][0].get("delta", {})
                    except (ValueError, KeyError, IndexError):
                        continue
                    content.append(delta.get("content") or "")
                    reasoning.append(delta.get("reasoning_content") or "")
            return "".join(content), "".join(reasoning)
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:300]}"
            if e.code not in (429, 500, 502, 503, 504):
                raise RuntimeError(last)
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            last = f"network error: {e}"
        if attempt < retries - 1:
            time.sleep(2 ** (attempt + 1))
    raise RuntimeError(f"{last} (after {retries} attempts)")


def choose(ids, requested):
    if requested:
        if requested not in ids:
            fail(f"model {requested!r} not offered; try --list-models")
        return requested
    for m in PREFERRED:
        if m in ids:
            return m
    fallback = sorted(i for i in ids if "instruct" in i)
    if not fallback:
        fail("no preferred or instruct model offered; pass --model")
    return fallback[0]


def load_verifier(repo):
    path = os.path.join(repo, "tools", "verify_package.py")
    if not os.path.isfile(path):
        fail(f"no verifier at {path}")
    spec = importlib.util.spec_from_file_location("verify_package", path)
    vp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vp)
    with open(path, encoding="utf-8") as fh:
        return vp, fh.read()


def reseal(vp, pkg):
    prev = None
    for entry in pkg["provenance"]["chain"]:
        entry["record"]["previous_digest"] = prev
        entry["record_digest"] = prev = vp.sha(vp.canon(entry["record"]))
    pkg["package_sha256"] = vp.sha(vp.canon({k: v for k, v in pkg.items() if k != "package_sha256"}))
    return pkg


def apply_edits(pkg, edits):
    for e in edits:
        path = e["path"]
        node = pkg
        for k in path[:-1]:
            node = node[k]
        if e.get("op", "set") == "delete":
            del node[path[-1]]
        elif e.get("op") == "append":
            node[path[-1]].append(e["value"])
        else:
            node[path[-1]] = e["value"]


def parse_edits(text):
    """Take the LAST well-formed edit list in the reply. Reasoning models write their thinking into
    the reply, brackets included, so first-[ to last-] is not the answer."""
    text = re.sub(r"```(?:json)?", "", text or "")
    dec, found = json.JSONDecoder(), None
    for i, ch in enumerate(text):
        if ch != "[":
            continue
        try:
            value, _ = dec.raw_decode(text, i)
        except ValueError:
            continue
        if isinstance(value, list) and value and all(isinstance(e, dict) and isinstance(e.get("path"), list)
                                                     for e in value):
            found = value
    if found is None:
        raise ValueError("no list of {path, value} edits in reply")
    return found


def real_gate(repo, pkg):
    """Decide the forged package with the REAL Gate. A verifier/Gate disagreement is a new finding."""
    sys.path.insert(0, repo)
    from sovereign_veritas.capability import Capability, CapabilityRegistry
    from sovereign_veritas.decision import Gate
    from sovereign_veritas.evidence import EvidenceRecord
    from sovereign_veritas.runtime import RuntimeState
    rec = dict(pkg["provenance"]["chain"][-1]["record"])
    rec.pop("decision", None), rec.pop("reasons", None)
    gi = pkg["gate_inputs"]
    cap = None if gi["capability"] is None else Capability(**{k: (tuple(v) if isinstance(v, list) else v)
                                                              for k, v in gi["capability"].items()})
    reg = None
    if gi["capability_registry"] is not None:
        reg = CapabilityRegistry()
        for c in gi["capability_registry"].values():
            if c is not None:
                reg.register(Capability(**{k: (tuple(v) if isinstance(v, list) else v) for k, v in c.items()}))
    d = Gate().evaluate(EvidenceRecord(**rec), cap, RuntimeState(**pkg["resource_state"]["runtime"]),
                        policy=gi["policy"], registry=reg)
    return d.decision, list(d.reasons)


def only_known(edits):
    def known(path):
        p = tuple(path)
        if p[:3] == ("provenance", "chain", -1) or (len(p) > 2 and p[:2] == ("provenance", "chain")):
            return True  # decision record fields or earlier records: K1/K2
        return any(p[:len(k)] == k for k in KNOWN_PATHS)
    return all(known(e["path"]) for e in edits)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--package")
    ap.add_argument("--repo", default=os.path.expanduser("~/sovereign-veritas"))
    ap.add_argument("--model")
    ap.add_argument("--rounds", type=int, default=5)
    ap.add_argument("--list-models", action="store_true")
    ap.add_argument("--base-url", default=BASE, help=argparse.SUPPRESS)
    a = ap.parse_args()
    key = load_key()
    ids = sorted(m["id"] for m in api(a.base_url, key, "/models").get("data", []))
    if a.list_models:
        print("\n".join(ids))
        return
    if not a.package:
        fail("--package is required")
    vp, vsrc = load_verifier(a.repo)
    with open(os.path.expanduser(a.package), encoding="utf-8") as fh:
        original = json.load(fh)
    if not all(ok for _, ok, _ in vp.verify(original)):
        fail("the input package does not verify to begin with")
    model = choose(ids, a.model)
    goal = (f"The package's decision is {original['decision']['decision']}. Make the verifier report "
            "CONSISTENT for a package that claims something false.")
    system = (
        "You are red-teaming an evidence verifier its author owns and wants broken. Reply with ONLY a "
        'JSON array of edits, each {"path": [key or index, ...], "value": ...} or '
        '{"op": "delete", "path": [...]} or {"op": "append", "path": [list], "value": ...}. Paths index the package JSON (use -1 for the last chain '
        "entry). After your edits, the harness recomputes every record digest, chain link and the "
        "package digest for you - you cannot and need not compute hashes. The verifier source is "
        "exactly what will judge you.\n" + KNOWN_LIMITS)
    messages = [{"role": "system", "content": system},
                {"role": "user", "content": f"{goal}\n\nVERIFIER SOURCE:\n{vsrc}\n\nPACKAGE:\n"
                                            f"{json.dumps(original, sort_keys=True)}"}]
    log_path = os.path.expanduser(f"~/sv_challenge_{int(time.time())}.json")
    log = {"model": model, "package": a.package, "rounds": []}
    def save_log():
        with open(log_path, "w", encoding="utf-8") as fh:
            json.dump(log, fh, indent=1, sort_keys=True)
    print(f"EXPLORATORY nvidia_challenge | model {model} | {a.rounds} rounds | local verifier judges")
    print(f"log {log_path}  (written after every round)")
    new_accepted = 0
    for n in range(1, a.rounds + 1):
        t0 = time.time()
        try:
            content, reasoning = chat_stream(a.base_url, key, {"model": model, "messages": messages,
                                                               "temperature": 0.6, "max_tokens": 4096})
        except RuntimeError as exc:
            entry = {"round": n, "seconds": round(time.time() - t0, 1), "verdict": "REQUEST_FAILED",
                     "error": str(exc)}
            print(f"round {n}: REQUEST_FAILED after retries ({str(exc)[:80]}) - skipping this round")
            log["rounds"].append(entry)
            save_log()
            continue
        text = content or reasoning
        entry = {"round": n, "seconds": round(time.time() - t0, 1), "reply": text[:4000]}
        try:
            edits = parse_edits(text)
            forged = copy.deepcopy(original)
            apply_edits(forged, edits)
            failed = [c for c, ok, _ in vp.verify(reseal(vp, forged)) if not ok]
        except Exception as exc:  # malformed reply or edits: rejected, never accepted
            entry.update(verdict="UNUSABLE", error=f"{type(exc).__name__}: {exc}")
            print(f"round {n}: UNUSABLE reply ({entry['error'][:80]})")
            messages += [{"role": "assistant", "content": text},
                         {"role": "user", "content": f"Unusable: {entry['error']}. Reply with only the JSON array."}]
            log["rounds"].append(entry)
            continue
        paths = [e["path"] for e in edits]
        if failed:
            entry.update(verdict="REJECTED", failed_checks=failed, paths=paths)
            print(f"round {n}: REJECTED by {', '.join(failed)}  ({len(edits)} edits, {entry['seconds']}s)")
            feedback = f"REJECTED. Failed checks: {failed}. Try a different approach."
        else:
            try:
                gate = real_gate(a.repo, forged)
                agrees = gate == [forged["decision"]["decision"], forged["decision"]["reasons"]] or \
                    list(gate) == [forged["decision"]["decision"], forged["decision"]["reasons"]]
            except Exception as exc:
                gate, agrees = f"could not rebuild: {type(exc).__name__}: {exc}", False
            known = only_known(edits) and agrees
            entry.update(verdict="ACCEPTED", within_known_limits=known, paths=paths, edits=edits,
                         real_gate=gate, real_gate_agrees=agrees)
            new_accepted += 0 if known else 1
            label = ("within known limits K1-K2" if known else
                     "REAL GATE DISAGREES WITH VERIFIER" if not agrees else
                     "OUTSIDE KNOWN LIMITS - review by hand")
            print(f"round {n}: ACCEPTED - {label}  paths {paths}")
            feedback = ("ACCEPTED, but " + ("that is a known limit; find one outside K1-K2."
                        if known else "keep going: find another."))
        messages += [{"role": "assistant", "content": text}, {"role": "user", "content": feedback}]
        log["rounds"].append(entry)
        save_log()
    print(f"log {log_path}")
    print(f"VERDICT {new_accepted} forgery(ies) outside the known limits accepted"
          + (" - review the log by hand" if new_accepted else ""))
    sys.exit(1 if new_accepted else 0)


if __name__ == "__main__":
    main()
