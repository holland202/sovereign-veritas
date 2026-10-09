# Signed v1 workflow (P-001, W1 + W2)

> Status: **experimental prototype — NOT PRODUCTION-READY, NOT INDEPENDENTLY SECURITY-VALIDATED.**
> These commands are run end to end by `tests/test_p001_w2.py::test_b08_documented_commands_run_end_to_end`
> on the Linux CI runners, with a throwaway key. Where `ssh-keygen` is missing, that test is skipped and
> the platform is **NOT_TESTED**; it is never reported as a passing signature check.
> Written by Claude (Opus 5.5) under Chad Holland's direction (2026-10-09); Chad has not reviewed it line by line.

There are three different roles, and they don't substitute for each other.

| Role | Tool | What it can say | What it cannot say |
|---|---|---|---|
| **Accept** a new package (production) | `tools/consumer.py accept` | ACCEPTED: signed by an allowed key, `sv.package/1`, bound to the locally trusted Gate contract, consistent, latest witnessed, not a replay, no rollback; state updated | that the decision is true, that the key holder is honest, that the time is current |
| **Inspect** a package | `tools/verify_package.py` | CONSISTENT, `authenticity=SIGNED:ID` or `NOT_PROVEN`, a `CONTRACT BOUND:sv.gate/0` or `CONTRACT LEGACY_UNBOUND` line | ACCEPTED: it has no state and never writes any |
| **Inspect a legacy** `sv.package/0` | `tools/verify_package.py --legacy` | the historical checks, `CONTRACT LEGACY_UNBOUND` | that the package was bound to any contract: it never was |

## Trust anchors

- **Signer:** the `allowed_signers` file you choose. A signature proves that the key holder signed these exact bytes, nothing more.
- **Gate contract:** `TRUSTED_CONTRACTS` in `tools/verify_package.py`, pinned to `sv.gate/0` →
  `44823d0ff707213ae8bc310ed8b21e135f8e742fd8834e8f9474743d3a250628`. CI checks that this equals the digest
  `tools/gate_contract.py` recomputes from `contract/gate_vectors.jsonl`. A package's own `contract` field is
  compared with it and is never trusted by itself.
- **Freshness:** the witness log is order, not time. Replay and rollback protection exist only after this consumer has seen a log (first use has no anchor).

## Commands

Make a key once (it is never overwritten), and keep the printed `allowed_signers` line:

```
python tools/sign_package.py keygen IDENTITY
```

Make, sign and witness a package:

```
python tools/make_package.py --thermal-status normal
python tools/sign_package.py sign PACKAGE.json
python tools/witness.py append PACKAGE.json --log LOG
```

Inspect it:

```
python tools/verify_package.py PACKAGE.json --signature PACKAGE.json.sig --allowed-signers ALLOWED --identity IDENTITY --witness-log LOG
```

Accept it (all three signature options are required; there is no unsigned mode):

```
python tools/consumer.py accept PACKAGE.json --witness-log LOG --state STATE.json --signature PACKAGE.json.sig --allowed-signers ALLOWED --identity IDENTITY
```

Inspect a legacy package (the published v0 evidence, signed by `holland202`):

```
python tools/verify_package.py --legacy evidence/sv_package_7548237bceca.json --signature evidence/sv_package_7548237bceca.json.sig --allowed-signers keys/allowed_signers --identity holland202
```

## Compatibility

- New packages are `sv.package/1`. Existing scripts that check `schema == "sv.package/0"` must be updated; nothing promises that old scripts accept v1 unchanged.
- Archived `sv.package/0` files are not rewritten, resealed or re-signed (`tests/p001/legacy_manifest_709da9e.sha256`).
- `tools/consumer.py` refuses every `sv.package/0`, signed or not.
- The consumer writes state to a temporary file in the same directory and moves it into place with `os.replace`. An interrupted write leaves the previous state. That is atomic replacement, not durability against power loss.

## Known limits these changes do not address

- **Concurrent consumers:** two `consumer.py` processes that share one state file are not serialised. Both can read the same old state and both accept the same package, so replay protection holds per process, not across concurrent processes. A08's atomic replace prevents a torn file. It does not prevent a lost update. Not tested; no locking was added.
- **First use:** a new consumer has no anchor, so it cannot detect a rollback that happened before it first looked.
- **Signed is not true or fresh:** see the Trust anchors section. The all-DEFAULTED `ALLOW` (W3) and the OPERATOR declarer gap (PV-1) are unchanged.

