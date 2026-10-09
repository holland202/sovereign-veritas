```yaml
artefact: p001/PLAN
by: Claude (Opus 5.5)        # Chad directed; not reviewed line by line
status: DRAFT (ChatGPT critiques once); no code until ACCEPTANCE is frozen
against: ACCEPTANCE.md@69044f3 + note 004 amendments K1-K7 as Chad freezes them
base: origin/main 709da9e
```

## Order: two PRs, one per item, each merged by Chad before the next starts
**PR-W1** (consumer):
1. Make `--signature`, `--allowed-signers` and `--identity` required (K1, which also fixes K2).
2. Check the signature **first**. Existing checks are unchanged.
3. If Chad picks A08: atomic state write (K6).
4. No unsigned mode. Document `verify_package.py` as the inspection path (K7).

**PR-W2** (package v1):
1. The kernel `sovereign_veritas/package.py` and `tools/make_package.py` emit `sv.package/1` with `contract: {id, conformance_digest}` inside the canonical body. `package_sha256` and the signature then cover the contract field.
2. `verify_package.py`:
   - accepts `SCHEMAS = {"sv.package/0", "sv.package/1"}`;
   - uses a separate key set for `/1`;
   - adds `TRUSTED_CONTRACTS` (K5);
   - adds a check `contract_binding` that gives PASS or FAIL for `/1` and `LEGACY_UNBOUND` for `/0`.
3. `consumer.py` refuses anything except `/1`.
4. Existing `/0` files are never touched (B06).

## Tests (frozen cases copied verbatim; new attacks only added)
- `tests/test_p001_w1.py` and `tests/test_p001_w2.py` cover A01–A08 and B01–B07.
  - Each test generates a throwaway ed25519 key with `ssh-keygen -t ed25519 -N ''` in a temp dir.
  - State and legacy files are compared byte for byte before and after.
- `tests/p001_mutants.py` (C06). Each of these three must make at least one frozen case fail:
  - **M-sig-skip**: the signature check always passes.
  - **M-self-digest**: the trusted digest is read from the package.
  - **M-refuse-all**: the consumer always refuses.
- B05 runs both modes: `tools/gate_contract.py --check kernel` and `--check verifier`. The expected digest is `44823d0f…0628`.
- CI: added to the `tests` workflow on Linux, where the A and B cases are required. On other legs, A/B are reported NOT_TESTED if `ssh-keygen -Y` is missing (B08).

## Report
An acceptance table with one row per case (ACCEPTANCE §D), filled from CI logs only: code SHA, command and output link for each row.

## Risks I can see
- **W2 touches the kernel package builder.** Every existing test that builds a package will now get `/1`. Those tests may need updating, and that is not the same as editing a frozen case. Each such change will be listed in the PR.
- **ssh-keygen on Windows/macOS runners is unverified.** Mitigated by NOT_TESTED, not by assuming it works.
