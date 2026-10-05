#!/usr/bin/env python3
"""pv1_probe.py - PV-1: is an OPERATOR evidence state evidence that anyone declared the value?

Usage:
  python tools/pv1_probe.py [--sabotage] [--json PATH]

Registration: docs/PV1_PREREG.md. Runs the real tools/make_package.py and tools/verify_package.py as
subprocesses; packages and keys live in a temporary directory, the checkout is never edited.
--sabotage skips the relabel in A3 (its tags stay DEFAULTED): W4 and W6 must be refuted and the run exit 1.
"""
from __future__ import annotations

import glob, hashlib, json, os, pathlib, shutil, subprocess, sys, tempfile

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from sovereign_veritas.evidence_states import resource_statement  # noqa: E402
from sovereign_veritas.package import package_digest  # noqa: E402

RECORDED = (("W1", "W2", "W3", "W4", "W5", "W6"), "d45a5437a660af555e40b4de0cc96101d9b26e84605a50616539e654f7958dd9")
IDENTITY = "pv1-throwaway@example.invalid"
DECLARER_KEYS = ("declar", "operator_id", "declared_by")


def make(extra):
    home = tempfile.mkdtemp(prefix="pv1h_")
    env = dict(os.environ, HOME=home)
    p = subprocess.run([sys.executable, str(REPO / "tools/make_package.py"), "--rounds", "10",
                        "--thermal-status", "normal", *extra], cwd=REPO, env=env, capture_output=True, text=True)
    files = glob.glob(os.path.join(home, "sv_package_*.json"))
    if p.returncode != 0 or len(files) != 1:
        print(f"COULD NOT LOOK: make_package exit {p.returncode}\n{p.stdout}{p.stderr}")
        sys.exit(2)
    return json.load(open(files[0], encoding="utf-8"))


def rewrite(pkg, new_states, regenerate=True, reseal=True):
    q = json.loads(json.dumps(pkg))
    old = resource_statement(q["resource_state"]["evidence_states"])
    q["resource_state"]["evidence_states"].update(new_states)
    if regenerate:
        new = resource_statement(q["resource_state"]["evidence_states"])
        q["known_limitations"] = [new if x == old else x for x in q["known_limitations"]]
    if reseal:
        q["package_sha256"] = package_digest(q)
    return q


def verify(pkg, d, name, sign=None):
    path = os.path.join(d, name + ".json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(pkg, fh)
    args = [sys.executable, str(REPO / "tools/verify_package.py"), path]
    if sign:
        key, signers = sign
        s = subprocess.run(["ssh-keygen", "-Y", "sign", "-f", key, "-n", "sv-package", path],
                           capture_output=True, text=True)
        if s.returncode != 0:
            print(f"COULD NOT LOOK: signing failed\n{s.stderr}")
            sys.exit(2)
        args += ["--signature", path + ".sig", "--allowed-signers", signers, "--identity", IDENTITY]
    v = subprocess.run(args, cwd=REPO, capture_output=True, text=True)
    lines = v.stdout.splitlines()
    return {"exit": v.returncode,
            "verdict": next((ln for ln in lines if ln.startswith("VERDICT")), None),
            "failed": sorted(ln.split()[1] for ln in lines if ln.startswith("FAIL")),
            "tags": pkg["resource_state"]["evidence_states"]}


def key_paths(o, prefix=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield f"{prefix}/{k}"
            yield from key_paths(v, f"{prefix}/{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from key_paths(v, f"{prefix}/{i}")


def main():
    sabotage = "--sabotage" in sys.argv
    print(f"PV-1 | {'SABOTAGE: A3 relabel skipped' if sabotage else 'registered run'} | python "
          f"{sys.version.split()[0]}")
    if not shutil.which("ssh-keygen"):
        print("COULD NOT LOOK: ssh-keygen not found")
        return 2
    d = tempfile.mkdtemp(prefix="pv1_")
    key = os.path.join(d, "k")
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", IDENTITY, "-f", key], check=True)
    signers = os.path.join(d, "allowed_signers")
    with open(signers, "w", encoding="utf-8") as fh:
        fh.write(f'{IDENTITY} namespaces="sv-package" {open(key + ".pub").read().split(" ", 2)[0]} '
                 f'{open(key + ".pub").read().split(" ", 2)[1]}\n')

    a0 = make([])
    a1 = make(["--compute-budget", "available", "--power-status", "stable"])
    op = {"compute_budget": "OPERATOR", "power_status": "OPERATOR"}
    a2 = rewrite(a0, op, regenerate=False, reseal=False)
    a3 = rewrite(a0, {} if sabotage else op)
    a4 = rewrite(a0, {"compute_budget": "MEASURED"})

    r = {"A0": verify(a0, d, "a0"), "A1": verify(a1, d, "a1"), "A2": verify(a2, d, "a2"),
         "A3": verify(a3, d, "a3"), "A4": verify(a4, d, "a4"),
         "S_A1": verify(a1, d, "s_a1", (key, signers)), "S_A3": verify(a3, d, "s_a3", (key, signers))}
    r["W5"] = {"decision_equal": a3["decision"] == a0["decision"],
               "gate_inputs_equal": a3["gate_inputs"] == a0["gate_inputs"]}
    r["W6_declarer_paths"] = sorted(p for pkg in (a1, a3) for p in key_paths(pkg)
                                    if any(s in p.rsplit("/", 1)[-1].lower() for s in DECLARER_KEYS))
    for k, x in r.items():
        print(f"  {k}: {json.dumps(x, sort_keys=True)}")

    consistent = lambda x: x["exit"] == 0 and (x["verdict"] or "").startswith("VERDICT  CONSISTENT")  # noqa: E731
    is_op = lambda x: x["tags"]["compute_budget"] == "OPERATOR" and x["tags"]["power_status"] == "OPERATOR"  # noqa: E731
    signed = lambda x: x["exit"] == 0 and f"authenticity=SIGNED:{IDENTITY}" in (x["verdict"] or "")  # noqa: E731
    v = {
        "W1": (consistent(r["A0"]) and consistent(r["A1"]) and is_op(r["A1"])
               and r["A0"]["tags"]["compute_budget"] == "DEFAULTED" == r["A0"]["tags"]["power_status"]),
        "W2": r["A4"]["exit"] == 1 and bool(set(r["A4"]["failed"]) & {"limitations_declared", "evidence_states"}
                                            or any("evidence" in f for f in r["A4"]["failed"])),
        "W3": r["A2"]["exit"] == 1 and "package_digest" in r["A2"]["failed"],
        "W4": consistent(r["A3"]) and is_op(r["A3"]),
        "W5": all(r["W5"].values()),
        "W6": signed(r["S_A1"]) and signed(r["S_A3"]) and is_op(r["S_A3"]) and r["W6_declarer_paths"] == [],
    }
    print()
    for k, x in v.items():
        print(f"  {k}  {'HELD' if x else 'REFUTED'}")
    held = tuple(k for k, x in v.items() if x)
    print(f"VERDICT {len(held)} of {len(v)} as registered (W7 is --sabotage; W8 is the door)")
    dg = hashlib.sha256(json.dumps({"results": r, "verdicts": v}, sort_keys=True).encode()).hexdigest()
    print(f"DIGEST {dg}")
    if "--json" in sys.argv:
        pathlib.Path(sys.argv[sys.argv.index("--json") + 1]).write_text(
            json.dumps({"results": r, "verdicts": v}, sort_keys=True, indent=1) + "\n", encoding="utf-8")
    if sabotage or RECORDED is None:
        return 0 if all(v.values()) else 1
    return 0 if (held, dg) == RECORDED else 1


if __name__ == "__main__":
    sys.exit(main() or 0)
