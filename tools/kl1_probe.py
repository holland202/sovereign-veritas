#!/usr/bin/env python3
"""kl1_probe.py - KL-1: what authenticity=SIGNED means as keys are rotated, expired, revoked, leaked or listed under a
pattern (docs/KL1_RE1_PREREG.md). Real ssh-keygen and the real tools/verify_package.py; container/desktop only.

P_old is a genuine package (tools/make_package.py). P_forged is a fully consistent package the author never made: the
same tool run by someone else with other inputs. Nothing is resealed by hand.

  python tools/kl1_probe.py              # exit 0 iff all 8 registered predictions held
  python tools/kl1_probe.py --sabotage   # KL-P2 keeps k_old listed, so KL-P2 must be refuted -> exit 1
  python tools/kl1_probe.py --expect-fix # after the KL-P5 fix: the verdict names the pattern (SIGNED:holland202[pattern:*])

Deviation (docs/KL1_RE1_RESULTS.md): the first version tested authenticity with a substring ('SIGNED:holland202' in the
verdict), which the fixed '...[pattern:*]' would also match. It now compares the whole authenticity token. The registered
run's token was exactly 'authenticity=SIGNED:holland202' in every case (results/kl1/kl1_registered.txt), so its outcome stands.
"""
import base64
import os
import shutil
import struct
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERIFY = os.path.join(ROOT, "tools", "verify_package.py")
MAKE = os.path.join(ROOT, "tools", "make_package.py")
ID = "holland202"


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def make_package(home, seed):
    p = run([sys.executable, MAKE, "--thermal-status", "normal", "--rounds", "20000", "--seed", seed],
            env=dict(os.environ, HOME=home), cwd=ROOT)
    path = next((l.split()[1] for l in p.stdout.splitlines() if l.startswith("package ")), None)
    if p.returncode != 0 or path is None:
        raise SystemExit(f"COULD NOT RUN: make_package failed: {p.stdout[-300:]} {p.stderr[-300:]}")
    return path


def keygen(d, name):
    path = os.path.join(d, name)
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", name, "-f", path], check=True)
    return path


def pub(key):
    return " ".join(open(key + ".pub").read().split()[:2])


def signed_copy(d, pkg, key, namespace, tag):
    """A copy of pkg's exact bytes at <d>/<tag>.json, signed with key under namespace (signature: <tag>.json.sig)."""
    path = os.path.join(d, tag + ".json")
    shutil.copyfile(pkg, path)
    subprocess.run(["ssh-keygen", "-Y", "sign", "-f", key, "-n", namespace, path], check=True, capture_output=True)
    return path, path + ".sig"


def signers(d, tag, lines):
    path = os.path.join(d, tag + ".signers")
    with open(path, "w") as fh:
        fh.write("".join(l + "\n" for l in lines))
    return path


def verify(pkg, sig, allowed):
    p = run([sys.executable, VERIFY, pkg, "--signature", sig, "--allowed-signers", allowed, "--identity", ID])
    verdict = next((l for l in p.stdout.splitlines() if l.startswith("VERDICT")), p.stdout.strip()[-120:])
    return p.returncode, verdict


def auth(verdict):
    """The whole authenticity token of a VERDICT line."""
    return next((t for t in verdict.split() if t.startswith("authenticity=")), "")


def direct(pkg, sig, allowed, *extra):
    with open(pkg, "rb") as fh:
        return subprocess.run(["ssh-keygen", "-Y", "verify", "-f", allowed, "-I", ID, "-n", "sv-package", "-s", sig,
                               *extra], stdin=fh, capture_output=True).returncode


def sshsig_fields(sig_path):
    """Decompose an armored SSHSIG blob field by field (PROTOCOL.sshsig). Returns (names, trailing byte count)."""
    lines = [l for l in open(sig_path).read().splitlines() if l and not l.startswith("-----")]
    blob = base64.b64decode("".join(lines))
    names, pos = [], 0
    if blob[:6] != b"SSHSIG":
        return ["<no SSHSIG magic>"], len(blob)
    names.append("magic"); pos = 6
    names.append("version"); pos += 4

    def string():
        nonlocal pos
        (n,) = struct.unpack(">I", blob[pos:pos + 4])
        pos += 4 + n
        return blob[pos - n:pos]
    for name in ("publickey", "namespace", "reserved", "hash_algorithm", "signature"):
        string()
        names.append(name)
    return names, len(blob) - pos


def main(argv):
    if shutil.which("ssh-keygen") is None:
        print("COULD NOT RUN: ssh-keygen not found")
        return 2
    sabotage, fixed = "--sabotage" in argv, "--expect-fix" in argv
    signed = f"authenticity=SIGNED:{ID}"
    d = tempfile.mkdtemp()
    try:
        p_old = make_package(d, "sv-package-v0")
        p_forged = make_package(d, "attacker-rewrite")
        k_old, k_new, k_att = (keygen(d, n) for n in ("k_old", "k_new", "k_attacker"))
        ns = 'namespaces="sv-package"'
        both = signers(d, "both", [f"{ID} {ns} {pub(k_old)}", f"{ID} {ns} {pub(k_new)}"])
        old_pkg, old_sig = signed_copy(d, p_old, k_old, "sv-package", "p_old")
        rows = []

        def row(case, prediction, held, observed):
            rows.append((case, held))
            print(f"  {case:<6} {'HELD   ' if held else 'REFUTED'} {prediction}\n         observed: {observed}")

        rc, v = verify(old_pkg, old_sig, both)
        row("KL-P1", "control: P_old with both keys listed is SIGNED", rc == 0 and auth(v) == signed, f"exit {rc} | {v}")

        only_new = signers(d, "only_new", [f"{ID} {ns} {pub(k_new)}"] + ([f"{ID} {ns} {pub(k_old)}"] if sabotage else []))
        rc, v = verify(old_pkg, old_sig, only_new)
        row("KL-P2", "rotation by replacement: the genuine old package fails like a forgery (exit 1)",
            rc == 1 and "authenticity=NOT_PROVEN" in v, f"exit {rc} | {v}")

        window = signers(d, "window", [f'{ID} {ns},valid-before="20260101" {pub(k_old)}',
                                       f'{ID} {ns},valid-after="20260101" {pub(k_new)}'])
        rc, v = verify(old_pkg, old_sig, window)
        rc_t = direct(old_pkg, old_sig, window, "-Overify-time=20251231")
        row("KL-P3", "expired window: FAIL through verify_package.py; ssh-keygen -Overify-time inside the window succeeds",
            rc == 1 and "authenticity=NOT_PROVEN" in v and rc_t == 0, f"verify_package exit {rc} | {v} | direct -Overify-time rc {rc_t}")

        krl = os.path.join(d, "revoked.krl")
        subprocess.run(["ssh-keygen", "-k", "-f", krl, k_old + ".pub"], check=True, capture_output=True)
        rc, v = verify(old_pkg, old_sig, both)
        rc_r = direct(old_pkg, old_sig, both, "-r", krl)
        row("KL-P4", "KRL revoking k_old: still SIGNED through verify_package.py; ssh-keygen -r KRL refuses",
            rc == 0 and auth(v) == signed and rc_r != 0, f"verify_package exit {rc} | {v} | direct -r rc {rc_r}")

        star = signers(d, "star", [f"{ID} {ns} {pub(k_old)}", f"* {ns} {pub(k_att)}"])
        f_pkg, f_sig = signed_copy(d, p_forged, k_att, "sv-package", "forged_by_attacker")
        rc, v = verify(f_pkg, f_sig, star)
        want5 = signed + "[pattern:*]" if fixed else signed
        row("KL-P5", f"pattern principal '*': the attacker's package verifies as {want5.split('=')[1]}"
                     + (" (expect-fix: the pattern is named)" if fixed else ""),
            rc == 0 and "CONSISTENT" in v and auth(v) == want5, f"exit {rc} | {v}")

        r_pkg, r_sig = signed_copy(d, p_old, k_old, "sv-effect-receipt", "p_old_receipt_ns")
        rc1, v1 = verify(r_pkg, r_sig, both)
        unrestricted = signers(d, "unrestricted", [f"{ID} {pub(k_old)}"])
        rc2, v2 = verify(r_pkg, r_sig, unrestricted)
        row("KL-P6", "a sv-effect-receipt signature over the package bytes fails, restricted or not",
            rc1 == 1 and rc2 == 1 and "NOT_PROVEN" in v1 and "NOT_PROVEN" in v2, f"exit {rc1} | {v1} || exit {rc2} | {v2}")

        names, trailing = sshsig_fields(old_sig)
        timed = [n for n in names if "time" in n or "date" in n]
        row("KL-P7", "the SSHSIG blob has no time field", not timed and trailing == 0 and names[0] == "magic",
            f"fields {names}, {trailing} trailing bytes")

        l_pkg, l_sig = signed_copy(d, p_forged, k_old, "sv-package", "forged_with_leaked_key")
        rc, v = verify(l_pkg, l_sig, both)
        row("KL-P8", "leaked k_old: a consistent package the author never made is CONSISTENT and SIGNED (a limit)",
            rc == 0 and "CONSISTENT" in v and auth(v) == signed, f"exit {rc} | {v}")
    finally:
        shutil.rmtree(d, ignore_errors=True)
    held = sum(h for _, h in rows)
    print(f"mode: {'SABOTAGE (KL-P2 keeps k_old listed)' if sabotage else 'registered'}{' +expect-fix' if fixed else ''}")
    print(f"VERDICT  {held} of {len(rows)} as registered")
    return 0 if held == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
