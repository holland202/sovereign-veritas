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
         --signature SIG --allowed-signers FILE --identity ID
Exit: 0 accepted (state updated) | 1 refused (state unchanged) | 2 could not look, or a usage error
(argparse prints "usage:" on stderr; a usage error is not a decision)

P-001 W1 (2026-10-09): accepting a package is an authenticated action. The three signature options
are required; there is no unsigned mode. To look at an unsigned package, inspect it with
tools/verify_package.py, which never touches consumer state. Only a signed sv.package/1 whose
contract binding matches the verifier's local trust anchor (W2) can be accepted; a legacy
sv.package/0 is refused here and can only be inspected (verify_package.py --legacy).
State is written to a temporary file in the state file's directory and moved into place with
os.replace (A08): an interrupted write leaves the previous state file as it was. That is atomic
replacement, not a durability guarantee against power loss or a failing disk.

What it does not do: protect a consumer on first use (no anchor yet), or detect a rollback that
happened before this consumer ever looked.
"""
import argparse, hashlib, importlib.util, json, os, sys, tempfile

sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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


def write_state(path, state):
    """A08: write the new state to a temp file beside `path`, then os.replace it into place.

    Any failure before the replace leaves `path` exactly as it was (or still absent) and removes the
    temp file. Raises OSError/ValueError/TypeError on failure."""
    directory = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".consumer-state-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=1, sort_keys=True)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["accept"])
    ap.add_argument("package")
    ap.add_argument("--witness-log", required=True)
    ap.add_argument("--state", required=True)
    # W1: required, all three. A missing one is an argparse usage error (exit 2), never an unsigned accept.
    ap.add_argument("--signature", required=True)
    ap.add_argument("--allowed-signers", required=True)
    ap.add_argument("--identity", required=True)
    a = ap.parse_args()
    vp = load_verifier()
    try:
        with open(a.package, "rb") as fh:
            data = fh.read()
        for what, path in (("signature", a.signature), ("allowed-signers", a.allowed_signers)):
            with open(path, "rb") as fh:  # unreadable trust material is COULD NOT LOOK, not a refusal
                if not fh.read(1):
                    raise ValueError(f"{what} file {path} is empty")
        pkg = vp.loads_bounded(data.decode("utf-8"))  # same strict parser as the verifier (DK)
        if not isinstance(pkg, dict):
            raise ValueError(f"top level is {type(pkg).__name__}, not an object")
        checks = [("signature", *vp.check_signature(data, a.signature, a.allowed_signers, a.identity)),
                  ("schema_v1_only", pkg.get("schema") == vp.SCHEMA_V1,
                   f"{pkg.get('schema')}" + ("" if pkg.get("schema") == vp.SCHEMA_V1 else
                                             " is not accepted here (legacy packages: verify_package.py --legacy)"))]
        checks += vp.verify(pkg)
        entries = vp.read_witness_log(a.witness_log)
        ok_w, fresh, detail = vp.check_witness_entries(pkg, entries)
        checks.append(("freshness_witness", ok_w, f"{fresh}: {detail}"))
        state = load_state(a.state)
        ok_c, why, new = consumer_check(vp, pkg, entries, state)
        checks.append(("consumer", ok_c, why))
    except (vp.WitnessUnreadable, vp.SignatureUnavailable, OSError, ValueError, KeyError, TypeError,
            AttributeError, IndexError, RecursionError) as exc:
        print(f"COULD NOT LOOK: {type(exc).__name__}: {exc}")
        sys.exit(2)
    for name, ok, detail in checks:
        print(f"{'PASS' if ok else 'FAIL'}  {name:<34} {detail}")
    if all(ok for _, ok, _ in checks):
        try:
            write_state(a.state, new)
        except (OSError, ValueError, TypeError) as exc:
            print(f"COULD NOT LOOK: state not written ({type(exc).__name__}: {exc}); previous state unchanged")
            print("CONSUMER  NOT ACCEPTED  (state unchanged)")
            sys.exit(2)
        print(f"CONSUMER  ACCEPTED  authenticity=SIGNED:{a.identity}  contract=BOUND:{pkg['contract']['id']}"
              "  (state updated)")
        sys.exit(0)
    print("CONSUMER  REFUSED  (state unchanged)")
    sys.exit(1)


if __name__ == "__main__":
    main()
