#!/usr/bin/env python3
"""sign_package.py - sign evidence packages with an ed25519 key via ssh-keygen -Y.

  python tools/sign_package.py keygen IDENTITY   create ~/.ssh/sv_package_ed25519 (never overwrites)
                                                and print the allowed_signers line for IDENTITY
  python tools/sign_package.py sign PACKAGE.json write PACKAGE.json.sig next to it

The signature covers the package file's exact bytes, namespace "sv-package". Anyone verifies with
tools/verify_package.py PACKAGE.json --signature PACKAGE.json.sig --allowed-signers FILE --identity ID
using only the public key. The private key never leaves this device and never goes in the repo.
It proves who signed a package, not when: freshness stays NOT_PROVEN.
Exit: 0 done | 1 refused (key exists, signing failed) | 2 could not run (usage, no ssh-keygen)
"""
import os, shutil, subprocess, sys

NAMESPACE = "sv-package"
KEY = os.path.expanduser(os.environ.get("SV_SIGNING_KEY", "~/.ssh/sv_package_ed25519"))


def run(args):
    exe = shutil.which("ssh-keygen")
    if exe is None:
        print("COULD NOT RUN: ssh-keygen not found (Termux: pkg install openssh)")
        sys.exit(2)
    return subprocess.run([exe] + args, capture_output=True, text=True)


def allowed_line(identity):
    with open(KEY + ".pub", encoding="utf-8") as fh:
        keytype, blob = fh.read().split()[:2]
    return f'{identity} namespaces="{NAMESPACE}" {keytype} {blob}'


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in ("keygen", "sign"):
        print(__doc__.strip().splitlines()[2] + "\n" + __doc__.strip().splitlines()[4])
        sys.exit(2)
    cmd, arg = sys.argv[1], sys.argv[2]
    if cmd == "keygen":
        if os.path.exists(KEY):
            print(f"REFUSED: {KEY} already exists; not overwriting. Its allowed_signers line:")
            print(allowed_line(arg))
            sys.exit(1)
        os.makedirs(os.path.dirname(KEY), mode=0o700, exist_ok=True)
        p = run(["-q", "-t", "ed25519", "-N", "", "-C", f"sv-package:{arg}", "-f", KEY])
        if p.returncode != 0:
            print(f"FAILED: {p.stderr.strip()}")
            sys.exit(1)
        print(f"key {KEY} (private, stays on this device)")
        print(allowed_line(arg))
        return
    if not os.path.exists(KEY):
        print(f"REFUSED: no key at {KEY}; run: python tools/sign_package.py keygen YOUR_NAME")
        sys.exit(1)
    if os.path.exists(arg + ".sig"):
        os.remove(arg + ".sig")  # ssh-keygen will not overwrite
    p = run(["-Y", "sign", "-f", KEY, "-n", NAMESPACE, arg])
    if p.returncode != 0:
        print(f"FAILED: {p.stderr.strip()}")
        sys.exit(1)
    print(f"signature {arg}.sig")


if __name__ == "__main__":
    main()
