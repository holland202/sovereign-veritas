#!/usr/bin/env python3
"""JG-2 probe: section 6 of James Greenwood's report, checked against the code (docs/JG2_PREREG.md).

  python tools/jg2_probe.py              exit 0 only on the RECORDED outcome; 2 = could not run
  python tools/jg2_probe.py --sabotage   P6's byte change is skipped: P6 must be REFUTED, exit 1
  python tools/jg2_probe.py --pre-fix    P4 expects the gap that F1 closes (run once, before F1)
"""
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.dont_write_bytecode = True

from sovereign_veritas.evidence import EvidenceRecord, canonical_json  # noqa: E402

RECORDED = (True, True, True, True, True, True)  # outcomes only. The digest covers file lists that
# grow as packages and external texts are added, so it is printed but not pinned (a recorded deviation
# from WORKFLOW W4; see docs/JG2_RESULTS.md).
PACKAGES = sorted(glob.glob(os.path.join(ROOT, "evidence", "sv_package_*.json")))
SIGNERS = os.path.join(ROOT, "keys", "allowed_signers")


def could_not_run(msg):
    print(f"COULD NOT RUN: {msg}")
    sys.exit(2)


def git_attr(path):
    out = subprocess.run(["git", "-C", ROOT, "check-attr", "text", "--", path], capture_output=True, text=True)
    if out.returncode != 0:
        could_not_run(f"git check-attr failed: {out.stderr.strip()}")
    return out.stdout.strip().rsplit(": ", 1)[-1]


def ssh_verify(data, sig):
    exe = shutil.which("ssh-keygen")
    if not exe:
        could_not_run("ssh-keygen not found")
    p = subprocess.run([exe, "-Y", "verify", "-f", SIGNERS, "-I", "holland202", "-n", "sv-package", "-s", sig],
                       input=data, capture_output=True)
    return p.returncode == 0


FILE_NAME_LINE = 'return self._dir / (hashlib.sha256(key.encode("utf-8")).hexdigest() + ".json")'


def p1():
    sites, bad, names = [], [], []
    for path in sorted(glob.glob(os.path.join(ROOT, "sovereign_veritas", "**", "*.py"), recursive=True)):
        for n, line in enumerate(open(path, encoding="utf-8"), 1):
            if "hashlib.sha256(" in line or re.search(r"\bsha256_hex\(", line):
                if "def sha256_hex" in line:
                    continue
                rel = f"{os.path.relpath(path, ROOT)}:{n}"
                ok = ("canonical_json(" in line or "sha256_hex(artifact)" in line
                      or ("hashlib.sha256(data)" in line and "package.py" in path))
                # Amendment 1 (2026-10-04): a third kind, a hash used only to name a reservation file, never stored
                # as evidence. Matched to this exact line in this one file; any other new hash is still refused.
                name_only = (path.endswith(os.path.join("sovereign_veritas", "idempotency.py"))
                             and line.strip() == FILE_NAME_LINE)
                sites.append(rel)
                if name_only:
                    names.append(rel)
                elif not ok:
                    bad.append(rel)
    rec = EvidenceRecord(record_id="jg2", input_digest="d", metadata={"note": "Ω non-ASCII ü"})
    canon = hashlib.sha256(canonical_json(rec.to_dict()).encode("utf-8")).hexdigest()
    ascii_ = hashlib.sha256(json.dumps(rec.to_dict(), sort_keys=True, separators=(",", ":"),
                                       ensure_ascii=True).encode("utf-8")).hexdigest()
    detail = {"sha256_sites": sites, "file_name_only_sites": names, "sites_not_canonical_or_artifact": bad,
              "digest_is_canonical": rec.record_digest == canon, "differs_from_ascii_json": canon != ascii_}
    return detail, (not bad and detail["digest_is_canonical"] and detail["differs_from_ascii_json"])


def p3():
    paths = ["contract/gate_vectors.jsonl", "witness/packages.log", "keys/allowed_signers"]
    paths += [os.path.relpath(p, ROOT) for p in PACKAGES] + [os.path.relpath(p, ROOT) + ".sig" for p in PACKAGES]
    d = {p: git_attr(p) for p in paths}
    return {"unset": sum(v == "unset" for v in d.values()), "of": len(d)}, all(v == "unset" for v in d.values())


def p4(pre_fix):
    """Before F1 the gap is predicted (unspecified); after F1 the same paths must be unset."""
    files = sorted(os.path.relpath(p, ROOT) for p in glob.glob(os.path.join(ROOT, "docs", "external", "*.md")))
    d = {p: git_attr(p) for p in files}
    want = "unspecified" if pre_fix else "unset"
    return {"expect": want, "attrs": d}, (len(d) > 0 and all(v == want for v in d.values()))


def p5():
    key_type = open(SIGNERS, encoding="utf-8").read().split()[2]
    ok = {os.path.basename(p): ssh_verify(open(p, "rb").read(), p + ".sig") for p in PACKAGES}
    return {"key_type": key_type, "verified": sum(ok.values()), "of": len(ok)}, (key_type == "ssh-ed25519" and all(ok.values()) and len(ok) == 8)


def p6(sabotage):
    data = bytearray(open(PACKAGES[0], "rb").read())
    if not sabotage:
        i = data.index(b'"')
        data[i + 1] ^= 0x01
    still = ssh_verify(bytes(data), PACKAGES[0] + ".sig")
    return {"tampered_copy_verifies": still}, (not still)


def p7():
    out = {}
    with tempfile.TemporaryDirectory() as tmp:
        accepted = None
        for p in PACKAGES:
            state = os.path.join(tmp, os.path.basename(p) + ".state")
            r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "consumer.py"), "accept", p,
                                "--witness-log", os.path.join(ROOT, "witness", "packages.log"), "--state", state],
                               capture_output=True, text=True)
            if r.returncode == 0:
                accepted = os.path.basename(p)
                break
        out["consumer_accepts_without_signature"] = accepted
    v = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "verify_package.py"), PACKAGES[0]],
                       capture_output=True, text=True)
    m = re.search(r"authenticity=(\S+)", v.stdout)
    out["verify_without_signature_exit"] = v.returncode
    out["verify_authenticity"] = m.group(1) if m else None
    held = (accepted is not None and v.returncode == 0 and out["verify_authenticity"] == "NOT_PROVEN")
    return out, held


def main(argv):
    sab = "--sabotage" in argv
    if sab:
        print("SABOTAGE: P6 checks an untampered copy")
    obs = {"P1": p1(), "P3": p3(), "P4": p4("--pre-fix" in argv), "P5": p5(), "P6": p6(sab), "P7": p7()}
    for pid, (d, ok) in obs.items():
        print(f"{'HELD   ' if ok else 'REFUTED'} {pid}  {json.dumps(d, sort_keys=True)}")
    print("NOT RUN P2  (Android / Termux: not run here)")
    held = tuple(ok for _, ok in obs.values())
    digest = hashlib.sha256(json.dumps({k: v[0] for k, v in obs.items()}, sort_keys=True,
                                       separators=(",", ":")).encode()).hexdigest()
    print(f"VERDICT {sum(held)} of {len(held)} as registered (P2 not run)")
    print(f"DIGEST {digest}")
    if sab:
        return 0 if all(held) else 1
    if RECORDED is None or "--pre-fix" in argv:
        print("RECORDED not pinned yet")
        return 0 if all(held) else 1
    return 0 if held == RECORDED else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
