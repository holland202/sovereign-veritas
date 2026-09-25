#!/usr/bin/env python3
"""package_recovery_sim.py - can a damaged package ever be accepted?

Takes a real package and feeds the independent verifier every strict prefix (a torn write) and
N seeded single-byte flips (corruption). Exit 0 only if none of them verifies CONSISTENT.
Writes nothing. Stdlib only; imports tools/verify_package.py, not sovereign_veritas.

  python tools/package_recovery_sim.py PACKAGE.json [--flips 200] [--seed 7]
"""
import argparse, importlib.util, json, os, random, sys

sys.dont_write_bytecode = True
_spec = importlib.util.spec_from_file_location(
    "verify_package", os.path.join(os.path.dirname(os.path.abspath(__file__)), "verify_package.py"))
vp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vp)


def accepted(data: bytes) -> bool:
    try:
        return all(ok for _, ok, _ in vp.verify(json.loads(data.decode("utf-8"))))
    except Exception:  # unreadable is rejected, never accepted
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("package")
    ap.add_argument("--flips", type=int, default=200)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    with open(a.package, "rb") as fh:
        data = fh.read()
    if not accepted(data):
        print("COULD NOT LOOK: the input package itself does not verify")
        sys.exit(2)
    torn = [k for k in range(len(data)) if accepted(data[:k])]
    rng = random.Random(a.seed)
    flips = []
    for _ in range(a.flips):
        i = rng.randrange(len(data))
        b = bytearray(data)
        b[i] ^= 1 << rng.randrange(8)
        if accepted(bytes(b)):
            flips.append(i)
    print(f"package {len(data)} bytes, seed {a.seed}")
    print(f"TRUNCATION  {len(torn)} of {len(data)} strict prefixes accepted")
    print(f"CORRUPTION  {len(flips)} of {a.flips} single-bit flips accepted {flips[:5]}")
    print(f"VERDICT     {'nothing damaged was accepted' if not torn and not flips else 'DAMAGED PACKAGE ACCEPTED'}")
    sys.exit(0 if not torn and not flips else 1)


if __name__ == "__main__":
    main()
