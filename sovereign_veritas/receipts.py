"""sv.effect-receipt/1: an executor's signed, bound statement about one dispatched attempt (EX-1, docs/EX1_PREREG.md).

What a valid receipt establishes: the holder of a key listed for `executor_id` in the receipts trust store, under the
`sv-effect-receipt` namespace, stated `effect_result` about exactly this record, attempt, command and authorization.
What it does NOT establish: that the external effect happened. A receipt is the executor's attributable claim. Only an
independent observation (EffectObserver in execution.py) can move an intent past EFFECT_ATTESTED.

Purpose separation: receipts are signed and verified under NAMESPACE, packages under "sv-package". ssh-keygen binds the
namespace into the signature, so a signature made for one purpose does not verify for the other, even with the same key;
an allowed_signers line can also restrict a key to one namespace (`namespaces="sv-effect-receipt"`).
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from typing import Any

from sovereign_veritas.evidence import canonical_json

SCHEMA = "sv.effect-receipt/1"
NAMESPACE = "sv-effect-receipt"
RESULTS = ("ATTESTED", "FAILED", "UNCONFIRMED")
BINDING = ("record_id", "attempt_id", "command_digest", "authorization_digest")
FIELDS = frozenset({"schema", "receipt_id", "record_id", "attempt_id", "authorization_digest", "command_digest",
                    "executor_id", "executor_key_id", "effect_type", "effect_result", "effect_reference", "observed_at",
                    "prior_receipt_digest"})


class SignatureUnavailable(RuntimeError):
    """ssh-keygen is missing or failed to run: nothing can be attested (fail closed)."""


def _canon(value: Any) -> bytes:
    # evidence.canonical_json, the one canonicalization every digest uses (JG-2 P1), refusing NaN/Infinity.
    json.dumps(value, allow_nan=False)
    return canonical_json(value).encode("utf-8")


def body_bytes(receipt: dict[str, Any]) -> bytes:
    """The signed bytes: canonical JSON of every field except the signature."""
    return _canon({k: v for k, v in receipt.items() if k != "signature"})


def receipt_digest(receipt: dict[str, Any]) -> str:
    json.dumps(receipt, allow_nan=False)
    return "sha256:" + hashlib.sha256(canonical_json(receipt).encode("utf-8")).hexdigest()


def problems(receipt: Any) -> list[str]:
    """Structural problems with a receipt, before any signature or binding check (closed schema)."""
    if not isinstance(receipt, dict):
        return ["receipt is not an object"]
    found = []
    keys = set(receipt) - {"signature"}
    if keys != FIELDS:
        missing, extra = sorted(FIELDS - keys), sorted(keys - FIELDS)
        found.append(f"fields: missing {missing}, unknown {extra}")
    if receipt.get("schema") != SCHEMA:
        found.append(f"schema {receipt.get('schema')!r}")
    if receipt.get("effect_result") not in RESULTS:
        found.append(f"effect_result {receipt.get('effect_result')!r}")
    for k in BINDING + ("receipt_id", "executor_id", "executor_key_id", "effect_type"):
        if not isinstance(receipt.get(k), str) or not receipt.get(k):
            found.append(f"{k} is not a non-empty string")
    if not isinstance(receipt.get("signature"), str) or not receipt.get("signature"):
        found.append("no signature")
    return found


def _ssh_keygen() -> str:
    exe = shutil.which("ssh-keygen")
    if exe is None:
        raise SignatureUnavailable("ssh-keygen not found")
    return exe


def sign_receipt(receipt: dict[str, Any], key_path: str) -> dict[str, Any]:
    """Return the receipt with an ssh signature over body_bytes() under NAMESPACE."""
    exe = _ssh_keygen()
    with tempfile.TemporaryDirectory() as tmp:
        body = os.path.join(tmp, "receipt")
        with open(body, "wb") as fh:
            fh.write(body_bytes(receipt))
        p = subprocess.run([exe, "-Y", "sign", "-f", key_path, "-n", NAMESPACE, body], capture_output=True, timeout=60)
        if p.returncode != 0:
            raise SignatureUnavailable(p.stderr.decode("utf-8", "replace").strip())
        with open(body + ".sig", encoding="ascii") as fh:
            return dict(receipt, signature=fh.read())


def verify_receipt(receipt: Any, *, expected: dict[str, str], allowed_signers: str) -> tuple[bool, str, list[str]]:
    """(attested, status, reasons). attested is True only for a structurally valid receipt, bound to `expected` on every
    BINDING field, with effect_result ATTESTED and a valid NAMESPACE signature by `executor_id` in `allowed_signers`.
    status is EFFECT_ATTESTED or EFFECT_UNCONFIRMED. A FAILED receipt is not evidence that nothing happened."""
    reasons = problems(receipt)
    if reasons:
        return False, "EFFECT_UNCONFIRMED", reasons
    for k in BINDING:
        if receipt[k] != expected.get(k):
            reasons.append(f"{k} does not bind: receipt {receipt[k]!r}, expected {expected.get(k)!r}")
    if reasons:
        return False, "EFFECT_UNCONFIRMED", reasons
    exe = _ssh_keygen()
    with tempfile.TemporaryDirectory() as tmp:
        sig = os.path.join(tmp, "receipt.sig")
        with open(sig, "w", encoding="ascii") as fh:
            fh.write(receipt["signature"])
        try:
            p = subprocess.run([exe, "-Y", "verify", "-f", allowed_signers, "-I", receipt["executor_id"], "-n", NAMESPACE,
                                "-s", sig], input=body_bytes(receipt), capture_output=True, timeout=60)
        except (OSError, subprocess.SubprocessError) as exc:
            raise SignatureUnavailable(str(exc)) from exc
    if p.returncode != 0:
        msg = (p.stderr or p.stdout).decode("utf-8", "replace").strip().splitlines()
        return False, "EFFECT_UNCONFIRMED", [f"signature: {msg[0] if msg else 'ssh-keygen exit ' + str(p.returncode)}"]
    if receipt["effect_result"] != "ATTESTED":
        return False, "EFFECT_UNCONFIRMED", [f"executor reports {receipt['effect_result']} (not evidence of no effect)"]
    return True, "EFFECT_ATTESTED", []
