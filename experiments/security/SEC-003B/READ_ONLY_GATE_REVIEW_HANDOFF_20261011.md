# SEC-003B/C read-only gate review and security campaign handoff — 2026-10-11

**Status:** source inspected; actual authorization security tests **NOT EXECUTED** in this review. This is not an attestation, certification, or authorization to merge or execute actions.

## Provenance

- Repository: `holland202/sovereign-veritas`
- Owner's Termux checkout: `~/sovereign-veritas`
- Owner-reported checkout HEAD: `d83ef9d` on `redteam/round1-contract-boundary`.
- Connected GitHub source inspected from `security/sec-003a-stack-fuzz`, including `sovereign_veritas/decision.py`, `sovereign_veritas/capability.py`, and `experiments/security/SEC-003A/README.md`. The displayed local `decision.py` portion agrees with the retrieved source, but byte-identical local-vs-remote verification **was not performed**.
- The separate SEC-003A planted stack-overflow experiment was pushed as commit `21a6409a89a01f5ad7ecd2606dfa930f0a5f51b6` and put up for review as **draft PR #77**. The committed record includes source, crash input, manifest and replay status. No compiled binary was committed, and cross-substrate independent reproduction remains incomplete.
- Prior SEC-002 toy heap-overflow experiments: user-reported LLVM libFuzzer discovery, stored six-byte crash input `53564e4e2453`, separate-process ASan replay, and local manifest SHA-256 `b3b4a6123e3988beb384a1dcc95afa3af83ab2bbbc5d7d4e67e01c3d0233bc16`. These **local SEC-002 bytes were not uploaded or independently checked** in this closeout; do not describe as remote-preserved.

## Actual gate interface

`Gate.evaluate(evidence: EvidenceRecord, capability: Capability | None, runtime: RuntimeState, policy: dict | None = None, registry: CapabilityRegistry | None = None) -> Decision` in `sovereign_veritas/decision.py`.

Source-observed behavior:
- Missing `evidence.input_digest` => `REFUSE`.
- Certain verification failures => `REFUSE`; insufficient verification evidence accrues `DEFER`, permitting later `REFUSE` precedence.
- Missing or non-boolean-True authorization => `REFUSE`; declared parent needs an authorized registry entry.
- Nonempty mismatched action capability => `REFUSE`.
- Unavailable runtime => `REFUSE`; unhealthy runtime accrues `DEFER`.
- Required evidence fields must have value **identical** to Python `True`; otherwise `DEFER`.
- Out-of-range/nonfinite evidence quality accrues `DEFER` when a threshold is configured.
- Invalid `step_count` accrues `DEFER`; exceeding maximum => `REFUSE`.
- Noncollection `policy.allow_only` => `REFUSE`. For **truthy** `action.requested`, a value outside an allowlist => `REFUSE`. An empty/missing `requested` bypasses this particular membership check; whether the overall request contract rejects it elsewhere is **not established**.
- If no outstanding reasons, returns `ALLOW`.

These are source observations, **not executed regression results**, and no exploitable production weakness is claimed.

## Preregister before the next run

1. Read `EvidenceRecord`, `RuntimeState`, and `VerificationStatus` contracts plus caller-side input validation and execution separation.
2. Define explicit expected `ALLOW`/`DEFER`/`REFUSE` for malformed or missing `action.requested`, absent `action.capability`, truthy non-boolean attestations, invalid and overflowing steps, unavailable/unhealthy runtime, insufficient verification + unauthorized capability, parent revocation, and invalid policy.
3. Test **the actual gate** through in-memory objects with execution adapters disabled; retain control/mutant cases and separate crashes from wrong decisions.
4. Archive source revision, test code, commands, per-case outcomes, failures, exit codes, and SHA-256; obtain independent reproduction before any platform-level validation claim.

## Local-file safety / preservation

The user's working tree showed these untracked paths; they were **not** examined or uploaded and remain under the owner's control:
- `evidence/veritas-agent-integration/`
- `sv_new_data_test.py`
- `sv_real_inference_results.json`

No merge, deletion, package install, Shizuku change, or local checkout modification was performed in this closeout. **Shizuku remains OFF** for nonprivileged baseline testing.
