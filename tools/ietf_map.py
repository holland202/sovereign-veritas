#!/usr/bin/env python3
"""IM probe (registration: docs/IETF_MAP_PREREG.md, commit 8a2805b, pushed before this file existed).

Runs this repository's consumer, verifier and Gate on one case per mappable requirement of
draft-krausz-verification-state-03 and prints CONFORMS / DIFFERS / NOT COVERED against the registered prediction.

  python tools/ietf_map.py              exit 0 only if every observation matches its registered prediction
  python tools/ietf_map.py --sabotage   M5 is given the genuine signature; its prediction must then fail (exit 1)
Needs ssh-keygen (M4, M13 and --sabotage verify signatures).
"""
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.dont_write_bytecode = True

from sovereign_veritas.capability import Capability  # noqa: E402
from sovereign_veritas.decision import Gate  # noqa: E402
from sovereign_veritas.evidence import EvidenceRecord  # noqa: E402
from sovereign_veritas.runtime import RuntimeState  # noqa: E402

SABOTAGE = "--sabotage" in sys.argv
EV = os.path.join(ROOT, "evidence")
LATEST = os.path.join(EV, "sv_package_7548237bceca.json")      # entry 6 of 6 in the witness log
BEHIND = os.path.join(EV, "sv_package_1956abdc6154.json")      # entry 4 of 6
SIGNERS, LOG = os.path.join(ROOT, "keys", "allowed_signers"), os.path.join(ROOT, "witness", "packages.log")
DIGEST = "44823d0ff707213ae8bc310ed8b21e135f8e742fd8834e8f9474743d3a250628"


def sh(*args):
    p = subprocess.run([sys.executable, *args], capture_output=True, text=True, cwd=ROOT)
    return p.returncode, (p.stdout + p.stderr).strip().splitlines()[-1:] or [""]


def consumer(tmp, pkg, sig=None, state="s.json"):
    cmd = [os.path.join(ROOT, "tools", "consumer.py"), "accept", pkg, "--witness-log", LOG,
           "--state", os.path.join(tmp, state)]
    if sig:
        cmd += ["--signature", sig, "--allowed-signers", SIGNERS, "--identity", "holland202"]
    return sh(*cmd)


def gate(status="PASS", thermal="normal", **rt):
    ev = EvidenceRecord(record_id="r", input_digest="abc", verification=None if status is None else {"status": status},
                        action={"capability": "act", "requested": "go"}, metadata={"sensor": True})
    d = Gate().evaluate(ev, Capability("act", True, ("sensor",)),
                        RuntimeState(platform="im", python_version="3", thermal_status=thermal, **rt))
    return d.decision, tuple(d.reasons)


def main():
    rows = []  # (id, predicted, observed, detail)
    with tempfile.TemporaryDirectory() as tmp:
        rc, last = consumer(tmp, os.path.join(tmp, "nope.json"), state="m1.json")
        rows.append(("M1", "CONFORMS", "CONFORMS" if rc != 0 else "DIFFERS", f"exit {rc}: {last[0][:70]}"))

        bad = os.path.join(tmp, "bad.json")
        open(bad, "w").write(open(LATEST).read()[:-40])
        rc, last = consumer(tmp, bad, state="m2.json")
        rows.append(("M2", "CONFORMS", "CONFORMS" if rc != 0 else "DIFFERS", f"exit {rc}: {last[0][:70]}"))

        rc, last = consumer(tmp, BEHIND, BEHIND + ".sig", state="m3.json")
        rows.append(("M3", "CONFORMS", "CONFORMS" if rc != 0 else "DIFFERS", f"exit {rc}: {last[0][:70]}"))

        rc, last = consumer(tmp, LATEST, BEHIND + ".sig", state="m4.json")
        rows.append(("M4", "CONFORMS", "CONFORMS" if rc != 0 else "DIFFERS", f"exit {rc}: {last[0][:70]}"))

        rc, last = consumer(tmp, LATEST, LATEST + ".sig" if SABOTAGE else None, state="m5.json")
        rows.append(("M5", "DIFFERS", "DIFFERS" if rc == 0 else "CONFORMS",
                     f"exit {rc} with {'signature (SABOTAGE)' if SABOTAGE else 'no signature'}: {last[0][:60]}"))

        text = open(LATEST).read()
        keys = set()

        def walk(o):
            if isinstance(o, dict):
                for k, v in o.items():
                    keys.add(k)
                    walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)
        walk(json.loads(text))
        bound = DIGEST in text or any(w in k.lower() for k in keys for w in ("contract", "mapping", "rules_version", "gate_version"))
        rows.append(("M6", "DIFFERS", "CONFORMS" if bound else "DIFFERS",
                     f"contract digest in package: {DIGEST in text}; mapping-like keys: "
                     f"{sorted(k for k in keys if any(w in k.lower() for w in ('contract', 'mapping', 'version')))}"))

        m7 = [gate("INSUFFICIENT_EVIDENCE")[0], gate(None)[0], gate("MAYBE")[0]]
        rows.append(("M7", "CONFORMS", "CONFORMS" if "ALLOW" not in m7 else "DIFFERS",
                     f"INSUFFICIENT_EVIDENCE/missing/unknown -> {m7}"))

        m8 = gate("PASS")
        rows.append(("M8", "DIFFERS", "DIFFERS" if m8[0] == "ALLOW" else "CONFORMS",
                     f"PASS, no adversarial check -> {m8[0]}"))

        rt_default = RuntimeState(platform="im", python_version="3", thermal_status="normal")
        m9 = gate("PASS")
        rows.append(("M9", "NOT COVERED", "NOT COVERED" if m9[0] == "ALLOW" else "CONFORMS",
                     f"compute_budget={rt_default.compute_budget!r} power_status={rt_default.power_status!r} "
                     f"(defaults, nobody supplied them) -> {m9[0]}"))

        m10a = gate("PASS", thermal="hot")
        rows.append(("M10a", "CONFORMS", "CONFORMS" if m10a[0] != "ALLOW" else "DIFFERS",
                     f"PASS + thermal hot -> {m10a}"))

        m10b = gate("REFUTED", thermal="hot")
        first = m10b[1][0] if m10b[1] else ""
        rows.append(("M10b", "DIFFERS", "DIFFERS" if first.startswith("verification") else "CONFORMS",
                     f"REFUTED + thermal hot -> {m10b}"))

        rc_bad, _ = sh(os.path.join(ROOT, "tools", "verify_package.py"), bad)
        tampered = os.path.join(tmp, "tampered.json")
        pkg = json.loads(text)
        pkg["decision"]["decision"] = "REFUSE" if pkg["decision"]["decision"] != "REFUSE" else "ALLOW"
        open(tampered, "w").write(json.dumps(pkg))
        rc_t, _ = sh(os.path.join(ROOT, "tools", "verify_package.py"), tampered)
        rows.append(("M11", "CONFORMS", "CONFORMS" if (rc_bad, rc_t) == (2, 1) else "DIFFERS",
                     f"malformed -> exit {rc_bad} (could not look); tampered decision -> exit {rc_t} (evaluated)"))

        p = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "verify_package.py"), LATEST],
                           capture_output=True, text=True, cwd=ROOT)
        replay = [l for l in p.stdout.splitlines() if "gate_replay" in l]
        rows.append(("M12", "CONFORMS", "CONFORMS" if replay and replay[0].startswith("PASS") else "DIFFERS",
                     replay[0].strip()[:80] if replay else "no gate_replay line"))

        r1, _ = consumer(tmp, LATEST, LATEST + ".sig", state="m13.json")
        r2, last = consumer(tmp, LATEST, LATEST + ".sig", state="m13.json")
        rows.append(("M13", "BEYOND", "BEYOND" if (r1, r2) == (0, 1) else "NOT BEYOND",
                     f"first accept exit {r1}, second exit {r2}: {last[0][:50]}"))

    print(f"{'ID':5} {'predicted':12} {'observed':12} detail")
    held = 0
    for rid, pred, obs, detail in rows:
        held += pred == obs
        print(f"{rid:5} {pred:12} {obs:12} {'' if pred == obs else '[NOT AS REGISTERED] '}{detail}")
    tally = {k: sum(1 for r in rows if r[2] == k) for k in ("CONFORMS", "DIFFERS", "NOT COVERED", "BEYOND")}
    print("\nmode:", "SABOTAGE (M5 given the genuine signature)" if SABOTAGE else "normal")
    print("observed:", ", ".join(f"{k} {v}" for k, v in tally.items()))
    print(f"VERDICT  {held} of {len(rows)} as registered")
    return 0 if held == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
