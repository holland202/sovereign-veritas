#!/usr/bin/env python3
"""field_sweep.py - which package fields can an attacker change without the verifier noticing?

Mutates every leaf field of a package one at a time, recomputes every digest (the attacker's
best move), and runs tools/verify_package.py. Prints every field whose change still verifies.
Deterministic, stdlib only, no network, no model. Writes nothing.

  python tools/field_sweep.py PACKAGE.json
Exit: 0 swept | 2 could not look (the input package does not verify, or is unreadable)

Survivors are not automatically bugs. A CONSISTENT package claims consistency, not authenticity:
a field no check recomputes, or one the Gate's decision does not depend on, can be rewritten.
This tool makes that set explicit instead of leaving it for an attacker to find.
"""
import copy, importlib.util, json, os, sys

sys.dont_write_bytecode = True
SKIP = {"package_sha256", "record_digest", "previous_digest"}


def load_verifier():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "verify_package.py")
    spec = importlib.util.spec_from_file_location("verify_package", path)
    vp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vp)
    return vp


def leaves(node, path=()):
    if isinstance(node, dict):
        for k, v in node.items():
            if k not in SKIP:
                yield from leaves(v, path + (k,))
    elif isinstance(node, list) and node:
        for i, v in enumerate(node):
            yield from leaves(v, path + (i,))
    else:
        yield path, node


def mutated(v):
    if isinstance(v, bool):
        return not v
    if isinstance(v, int):
        return v + 1
    if isinstance(v, float):
        return v * 1.5 + 1.0
    if isinstance(v, str):
        return v + "X"
    if v is None:
        return "X"
    return None  # empty list or dict: nothing to mutate


def reseal(vp, p):
    prev = None
    for e in p["provenance"]["chain"]:
        e["record"]["previous_digest"] = prev
        e["record_digest"] = prev = vp.sha(vp.canon(e["record"]))
    p["package_sha256"] = vp.sha(vp.canon({k: v for k, v in p.items() if k != "package_sha256"}))
    return p


def accepted(vp, p):
    try:
        return all(ok for _, ok, _ in vp.verify(p))
    except Exception:  # a crash is a rejection, never an acceptance
        return False


def pattern(path):
    """Collapse per-zone and per-byte indices so one field reads as one line."""
    return "/".join("*" if isinstance(k, int) and "zones" in path else str(k) for k in path)


def sweep(vp, pkg):
    total, survivors = 0, {}
    for path, val in leaves(pkg):
        new = mutated(val)
        if new is None:
            continue
        p = copy.deepcopy(pkg)
        node = p
        for k in path[:-1]:
            node = node[k]
        node[path[-1]] = new
        total += 1
        if accepted(vp, reseal(vp, p)):
            key = pattern(path)
            survivors[key] = survivors.get(key, 0) + 1
    return total, survivors


def main():
    if len(sys.argv) != 2:
        print(__doc__.strip().splitlines()[5])
        sys.exit(2)
    vp = load_verifier()
    try:
        with open(sys.argv[1], encoding="utf-8") as fh:
            pkg = json.load(fh)
    except (OSError, ValueError) as exc:
        print(f"COULD NOT LOOK: {exc}")
        sys.exit(2)
    if not accepted(vp, copy.deepcopy(pkg)):
        print("COULD NOT LOOK: the input package does not verify")
        sys.exit(2)
    total, survivors = sweep(vp, pkg)
    n = sum(survivors.values())
    print(f"{total} single-field rewrites (every digest recomputed): {n} verified, "
          f"{len(survivors)} distinct fields")
    for key, count in sorted(survivors.items()):
        print(f"  {key}" + (f"  (x{count})" if count > 1 else ""))


if __name__ == "__main__":
    main()
