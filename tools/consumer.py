#!/usr/bin/env python3
"""consumer.py - the consumer's side of an evidence package: act once, and never go backwards.

The verifier (tools/verify_package.py) has no memory, so it cannot see a replay (the same package
acted on twice) or a rollback (a witness log with its newest entries deleted). A consumer can. It
keeps a small state file with two things:

  consumed  the package digests it has acted on; a repeat is refused
  anchor    the longest witness log it has seen: (entries, sha256 of those entry lines); a log that
            does not start with exactly those lines is refused

Registered as round 3 in docs/ATTACK_HARNESS.md (P13-P15), G1-3 in docs/SV_GATE_1_SCOPE.md.

  python tools/consumer.py accept PACKAGE.json --witness-log LOG --state STATE.json
         [--signature SIG --allowed-signers FILE --identity ID]
Exit: 0 accepted (state updated) | 1 refused (state unchanged) | 2 could not look
What it does not do: protect a consumer on first use (no anchor yet), or detect a rollback that
happened before this consumer ever looked.
"""
import argparse, hashlib, importlib.util, json, os, sys, time

sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

LOCK_TIMEOUT_S = 30.0


class LockTimeout(Exception):
    """Could not claim the state lock in time: another consumer is running, or a crashed one left
    a stale lock file. Never silently proceeds without the lock (RP-1, docs/RP1_RESULTS.md, P6/P7:
    load-check-write with no lock let 100% of a forced-interleaving trial double-accept)."""


def _acquire_lock(lock_path, timeout=LOCK_TIMEOUT_S, poll=0.01):
    """Exclusive claim on lock_path: os.open(O_CREAT|O_EXCL), the same atomic-create idiom
    sovereign_veritas/idempotency.py's FileReservations already uses for keys (RP1_RESULTS.md's
    own proposed fix). Portable: no fcntl/msvcrt needed, so this runs the same way on every
    platform consumer.py is tested on (Linux, macOS, Windows)."""
    deadline = time.monotonic() + timeout
    while True:
        try:
            os.close(os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            return
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise LockTimeout(
                    f"could not claim {lock_path!r} within {timeout}s "
                    "(another consumer running, or a stale lock left by a crash)"
                )
            time.sleep(poll)


def _release_lock(lock_path):
    try:
        os.remove(lock_path)
    except OSError:
        pass


def _write_state(path, state):
    """Atomic replace (temp file + os.replace), not a truncating open(path, 'w'): a crash
    mid-write must never leave a torn file where an intact one was (RP1_RESULTS.md P8 saw this
    non-atomic write produce a torn state file live, during the very race this lock closes)."""
    tmp = f"{path}.tmp-{os.getpid()}"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=1, sort_keys=True)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def load_verifier():
    spec = importlib.util.spec_from_file_location("vp_consumer", os.path.join(ROOT, "tools", "verify_package.py"))
    vp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vp)
    return vp


def prefix_digest(entries):
    return hashlib.sha256("\n".join(f"{s} {d}" for s, d in entries).encode("utf-8")).hexdigest()


def load_state(path):
    if not path or not os.path.exists(path):
        return {"consumed": [], "anchor": None}
    with open(path, encoding="utf-8") as fh:
        st = json.load(fh)
    if not (isinstance(st, dict) and isinstance(st.get("consumed"), list)):
        raise ValueError("state file is not a consumer state")
    return st


def consumer_check(vp, pkg, entries, state):
    """(ok, why, new_state) using one already-read witness snapshot."""
    anchor = state.get("anchor")
    if anchor is not None:
        n = anchor["entries"]
        if len(entries) < n or prefix_digest(entries[:n]) != anchor["prefix_sha256"]:
            return False, f"witness log does not extend the {n} entries this consumer has seen (rollback or rewrite)", state
    digest = pkg.get("package_sha256")
    if digest in state["consumed"]:
        return False, "already acted on this package (replay)", state
    new = {"consumed": state["consumed"] + [digest],
           "anchor": {"entries": len(entries), "prefix_sha256": prefix_digest(entries)}}
    return True, f"first use; anchor now {len(entries)} entries", new


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["accept"])
    ap.add_argument("package")
    ap.add_argument("--witness-log", required=True)
    ap.add_argument("--state", required=True)
    ap.add_argument("--signature")
    ap.add_argument("--allowed-signers")
    ap.add_argument("--identity")
    a = ap.parse_args()
    vp = load_verifier()
    lock_path = a.state + ".lock"
    try:
        _acquire_lock(lock_path)
    except LockTimeout as exc:
        print(f"COULD NOT LOOK: {exc}")
        sys.exit(2)
    try:
        with open(a.package, "rb") as fh:
            data = fh.read()
        pkg = vp.loads_bounded(data.decode("utf-8"))  # same strict parser as the verifier (DK)
        checks = vp.verify(pkg)
        if a.signature:
            checks.append(("signature", *vp.check_signature(data, a.signature, a.allowed_signers, a.identity)))
        entries = vp.read_witness_log(a.witness_log)
        ok_w, fresh, detail = vp.check_witness_entries(pkg, entries)
        checks.append(("freshness_witness", ok_w, f"{fresh}: {detail}"))
        # Read the state only after the lock is held (RP-1 P6): a snapshot read before the lock
        # could already be stale by the time this process would have written it.
        state = load_state(a.state)
        ok_c, why, new = consumer_check(vp, pkg, entries, state)
        checks.append(("consumer", ok_c, why))
        # Write while still holding the lock: the check and the write are one claim, not two
        # (the gap between them is exactly what let a second process see the pre-write state).
        if all(ok for _, ok, _ in checks):
            _write_state(a.state, new)
    except (vp.WitnessUnreadable, vp.SignatureUnavailable, OSError, ValueError, KeyError) as exc:
        print(f"COULD NOT LOOK: {type(exc).__name__}: {exc}")
        sys.exit(2)
    finally:
        _release_lock(lock_path)
    for name, ok, detail in checks:
        print(f"{'PASS' if ok else 'FAIL'}  {name:<34} {detail}")
    if all(ok for _, ok, _ in checks):
        print("CONSUMER  ACCEPTED  (state updated)")
        sys.exit(0)
    print("CONSUMER  REFUSED  (state unchanged)")
    sys.exit(1)


if __name__ == "__main__":
    main()
