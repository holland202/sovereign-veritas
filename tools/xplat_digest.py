#!/usr/bin/env python3
"""xplat_digest.py - cross-platform comparator for docs/XPLAT_PREREG.md. Stdlib only.

  python tools/xplat_digest.py digest LEG_DIR             print "<sha256>  <file>" per normalized *.txt
  python tools/xplat_digest.py compare LEG_DIR [...]      P2 pinned digests on every leg, P3 one sha256 per file
  python tools/xplat_digest.py --selftest                 anti-vacuity: the comparator must be able to fail

Exit: 0 holds | 1 violated | 2 could not run.
Normalization is fixed by the registration and must not grow after results:
  1. remove "\\r"   2. drop lines starting "gate_constraint v"   3. drop lines starting "target "
"""
import hashlib, os, shutil, sys, tempfile

DROP_PREFIXES = ("gate_constraint v", "target ")
EXPECTED_FILES = ("gate.txt", "contract_kernel.txt", "contract_verifier.txt", "packages.txt",
                  "attacks.txt", "corridor.txt", "recovery.txt", "xb1.txt")
PINNED = {  # P2: (file, exact substring that must appear)
    "gate.txt": "DIGEST    ab816905b1faf69aeaf24119b207cf7b80fcebd2ffcddac80d3edfa5e4da2d65",
    "contract_kernel.txt": "conformance digest 44823d0ff707213ae8bc310ed8b21e135f8e742fd8834e8f9474743d3a250628",
    "contract_verifier.txt": "conformance digest 44823d0ff707213ae8bc310ed8b21e135f8e742fd8834e8f9474743d3a250628",
    "corridor.txt": "DIGEST   4f09350ea05ee3d30ee9e2cd69c62d5fd459ddcb5984cd700c94509369afa665",
}


def normalize(raw):
    text = raw.replace(b"\r", b"").decode("utf-8")
    return "\n".join(ln for ln in text.split("\n") if not ln.startswith(DROP_PREFIXES)).encode("utf-8")


def read_norm(path):
    with open(path, "rb") as f:
        return normalize(f.read())


def leg_digests(leg_dir):
    return {n: hashlib.sha256(read_norm(os.path.join(leg_dir, n))).hexdigest()
            for n in sorted(os.listdir(leg_dir)) if n.endswith(".txt")}


def compare(leg_dirs, out=print):
    legs = {os.path.basename(os.path.normpath(d)): d for d in leg_dirs if os.path.isdir(d)}
    if not legs:
        out("FAIL no legs")
        return False
    ok = True
    out("P2 pinned values")
    for leg, d in legs.items():
        missing = []
        for name, needle in PINNED.items():
            p = os.path.join(d, name)
            if not os.path.exists(p) or needle not in read_norm(p).decode("utf-8"):
                missing.append(name)
        ok &= not missing
        out("  %-26s %s" % (leg, "HOLD" if not missing else "MISSING " + ", ".join(missing)))
    out("P3 one normalized sha256 per file across legs")
    digests = {leg: leg_digests(d) for leg, d in legs.items()}
    for name in EXPECTED_FILES:
        hashes = {leg: dg.get(name) for leg, dg in digests.items()}
        distinct = set(hashes.values())
        agree = len(distinct) == 1 and None not in distinct
        ok &= agree
        out("  %-22s %s %s" % (name, "AGREE" if agree else "SPLIT", next(iter(distinct))[:12] if agree else ""))
        if not agree:
            for leg, h in hashes.items():
                out("      %-24s %s" % (leg, h[:12] if h else "MISSING"))
    out("VERDICT  " + ("P2+P3 HOLD on %d legs" % len(legs) if ok else "P2/P3 VIOLATED"))
    return ok


def selftest():
    quiet = lambda *_: None
    with tempfile.TemporaryDirectory() as tmp:
        a, b = os.path.join(tmp, "A"), os.path.join(tmp, "B")
        os.makedirs(a)
        for name in EXPECTED_FILES:
            body = "line one\n" + PINNED.get(name, "VERDICT  ok") + "\n"
            if name == "gate.txt":
                body = "gate_constraint v2 | python 3.14 aarch64\ntarget /x/y\n" + body
            with open(os.path.join(a, name), "w", newline="\n") as f:
                f.write(body)
        shutil.copytree(a, b)
        with open(os.path.join(b, "gate.txt"), "rb") as f:  # platform lines differ, \r\n line endings
            g = f.read().replace(b"python 3.14 aarch64", b"python 3.12 s390x").replace(b"/x/y", b"C:\\w").replace(b"\n", b"\r\n")
        with open(os.path.join(b, "gate.txt"), "wb") as f:
            f.write(g)
        same = compare([a, b], quiet)
        with open(os.path.join(b, "attacks.txt"), "ab") as f:  # one byte more
            f.write(b"X")
        split = not compare([a, b], quiet)
        with open(os.path.join(b, "attacks.txt"), "rb") as f:
            fixed = f.read()[:-1]
        with open(os.path.join(b, "attacks.txt"), "wb") as f:
            f.write(fixed)
        for leg in (a, b):  # same file on both legs, pinned digest absent: P3 agrees, P2 must fail
            with open(os.path.join(leg, "corridor.txt"), "w", newline="\n") as f:
                f.write("line one\nDIGEST   0000\n")
        pinned_fails = not compare([a, b], quiet)
    print("selftest  identical legs (platform lines and \\r\\n differ only): %s" % ("AGREE" if same else "SPLIT"))
    print("selftest  one byte added to one file: %s" % ("SPLIT reported" if split else "NOT REPORTED"))
    print("selftest  pinned digest missing on both legs: %s" % ("P2 failure reported" if pinned_fails else "NOT REPORTED"))
    good = same and split and pinned_fails
    print("VERDICT  " + ("comparator can agree and can fail" if good else "COMPARATOR IS VACUOUS OR BROKEN"))
    return good


def main(argv):
    if argv[:1] == ["--selftest"]:
        return 0 if selftest() else 1
    if len(argv) == 2 and argv[0] == "digest":
        for n, h in leg_digests(argv[1]).items():
            print(h + "  " + n)
        return 0
    if len(argv) >= 2 and argv[0] == "compare":
        return 0 if compare(argv[1:]) else 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
