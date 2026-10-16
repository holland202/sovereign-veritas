# Sovereign Veritas v0.2.1: maintenance release for SV-ATTACK-001 Q1 and Q3

**EXPERIMENTAL research prototype. NOT PRODUCTION-READY. NOT INDEPENDENTLY SECURITY-VALIDATED.**

**Release state: PREPARED, NOT TAGGED.** The tag is held until the independent review of the SV-FIX-001 protocol
that is under discussion has been agreed in writing and done, or until Chad Holland decides otherwise. Chad
creates the tag on the merged commit. Until then, `v0.2.0` is the latest release, and it is affected by both
findings below.

This is a maintenance release under the maintenance-only rule set at v0.2.0: security fixes only, no new
features.

## What it fixes

| Finding (found 2026-10-09, `36b324a`) | v0.2.0 behaviour | Fix | Verification |
|---|---|---|---|
| **SV-ATTACK-001 Q1**: an ALLOW covers parameters the caller changes after the decision | `EvidenceWorkflow.run()` decided on a frozen copy, then executed the caller's original, mutable object | **F1** (`sovereign_veritas/workflow.py`, +7/−2): the executor receives an action rebuilt from the frozen decision record, so a later change cannot reach it | F1 PASS (R1, R8 mutant caught) |
| **SV-ATTACK-001 Q3**: the offline verifier did not compare the commands sent with what was authorized | A package whose `commands_sent` differed from the authorized parameters verified `CONSISTENT` | **F2** (`tools/verify_package.py`): `vehicle_check_bound` fails when recorded commands are not the authorized ones | F2 PASS (R4, R9 mutant caught) |

Registration, code and results: [SV_FIX_001_PREREG.md](SV_FIX_001_PREREG.md) (`b390562`), fix `d63d3fd`, results
[SV_FIX_001_RESULTS.md](SV_FIX_001_RESULTS.md). Merged in #71 (`fff4f68`). The original failures stay published
in [STATUS.md](../STATUS.md) and `results/sv_attack_001/`.

## Compatibility

- **Package format unchanged.** `sv.package/1` stays the production format, and `sv.package/0` stays legacy-only,
  inspected with `--legacy`. The CLI is unchanged.
- **Gate decisions unchanged.** `gate_contract.py --check kernel` and `--check verifier` both print
  `VERDICT  CONFORMS` against the 4,690 vectors (digest `44823d0f…0628`).
- **Every committed package re-verified with the v0.2.0 and v0.2.1 verifiers** (`tools/release_compat.py v0.2.0`,
  output `results/release_v0.2.1/compat_v0.2.0_vs_main.txt`):

  ```
  packages compared: 56 (old = v0.2.0, new = working tree, both with --legacy)
    exit 0->0: 48
    exit 0->1: 2
    exit 1->1: 4
    exit 2->2: 2
  verdict changed: 2
  ```

  The two changed verdicts are the SV-ATTACK-001 substitution packages (`results/sv_attack_001/run1/packages/B1.json`
  and its home copy), which now fail as intended. No other package changes exit code or verdict line. Control: the
  same tool comparing the release branch with itself reports `verdict changed: 0`
  (`results/release_v0.2.1/compat_control_HEAD_vs_main.txt`).
- **Who is affected.** Code that relied on `run()` executing the caller's object after the decision, or on a package
  verifying while its sent commands differed from the authorization, now behaves differently. Both were the defects.

## What this release does not claim

- **The fixes are self-tested.** Claude (Opus 5.5) wrote the attack, the fixes, the registration and the driver, and
  ran the verification once, in one Linux x86-64 container. It was not run on the S25. ChatGPT did not audit the run,
  and no human has reviewed the code line by line.
- **R6 is weaker than it looks** (see the results file). Without `--legacy`, the regression packages already failed
  for other reasons. The supplementary `--legacy` comparison was not registered. The 56-package comparison above was
  also done for this release, after the fix, and is not registered.
- **Bounded fixes, not complete execution-time authorization.** Nothing here observes real-world effects, resists a
  malicious executor, or closes XB-1's race (X4) and effect-without-record (X5) cases.
- All known limits of v0.2.0 still apply unchanged: W3 DEFAULTED-only ALLOW, PV-1, AMB-1, XB-1, EO-1, concurrent
  consumers, first-use anchor, and signatures not proving truth or freshness. See
  [RELEASE_NOTES_v0.2.0.md](RELEASE_NOTES_v0.2.0.md) and [STATUS.md](../STATUS.md).

## Release checklist (for Chad)

1. Independent review of the SV-FIX-001 protocol agreed in writing and done, or Chad's explicit decision to release
   without it.
2. Merge the release PR.
3. Full CI on the merge commit, all workflows including `xplat`. Record any leg that is `NOT_RUN` (for example, a
   Docker Hub rate limit before any test) as `NOT_RUN`, not as a pass.
4. Annotated tag `v0.2.1` on that exact commit, created by Chad.

## Provenance

Drafted by Claude (Anthropic, Opus 5.5) at Chad Holland's direction on 2026-10-16 → human validation: not
performed → human editing/curation: direction only (version, contents and the held tag were delegated to Claude;
the hold for independent review is Chad's decision) → human responsibility: Chad Holland.
