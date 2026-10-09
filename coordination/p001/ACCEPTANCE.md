# P-001 — Acceptance contract (DRAFT v0.1, not frozen)

```yaml
artefact: p001/ACCEPTANCE
author: ChatGPT (self-declared)
phase: 2-design
status: DRAFT_FOR_CLAUDE_REVIEW; NOT_FROZEN
scope_commit: d2d7094cc3a47b593435a3f50c1041576b3e8a0e
scope_sha256: 685cd7c2e584280dd1014a17b8f9b98b7469c323a4d5e6dd1800bf79119a9974
authority: Chad owner freeze, PR #63 comment 6084483853
implementation: NOT_AUTHORIZED
request: Claude critique once and write PLAN.md; Chad freeze exact acceptance bytes
```

This document specifies *observable outcomes* for the approved Sovereign Veritas close-out. ChatGPT has **not implemented or run** these tests. Claude shall critique the contract **before** code changes. The final acceptance file must be frozen by Chad, with immutable commit and exact content SHA-256 on [PR #63](https://github.com/holland202/sovereign-veritas/pull/63), before implementation. Frozen cases remain unchanged; new adversarial cases are additive, never replacements.

## Common prerequisites and evidence semantics

- Build tests using fresh temporary directories and *throwaway Ed25519 SSH signing keys*, with explicit allowed-signers identity and `sv-package` namespace. Never use Chad's actual private key in CI; no secrets are committed. Tests are offline and deterministic wherever possible.
- Pin the exact `main` starting revision, test commands, Python/OS environments, original contract vectors and conformance digest. Verify source/evidence rather than trusting a reported green badge. `SCOPE_FROZEN` does **not** imply `ACCEPTANCE_FROZEN`.
- Distinguish `ACCEPTED` (success and state advanced), `REFUSED` (checks failed, state unchanged), and `COULD_NOT_LOOK` (required check unreadable/unavailable, state unchanged). Current CLI convention is exit 0/1/2 respectively; keep it unless an explicit, owner-reviewed CLI change is documented.
- For state nonmutation assertions, compare **exact file bytes before and after**, or assert state file absence both times. Existing consumed list and anchor are both covered. Do not count failure merely because a script prints the right text.
- **Anti-vacuity:** At least one valid authorized, signed, freshly witnessed v1 package must be accepted and persist state, and both v0 and v1 must remain inspectable under their allowed, clearly identified modes. A checker that refuses everything fails acceptance.
- Signatures attest the signed bytes under an approved key, not that the Gate decision is true, fresh or authorized by an external human. A contract digest attests version binding under local trust, not scientific/world truth.

## A — W1: production consumer refuses unauthenticated acceptance

**A01 — Positive control.** Given a newly generated `sv.package/1` whose contract fields match the trusted local contract, whose detached signature validates under a throwaway key/allowed-signers identity, and whose witness log places this package latest, `consumer accept` returns 0, reports authenticated acceptance, and writes a state file with exactly one consumed package digest and the expected witness anchor. On a second invocation with the same state/package/witness, it refuses (exit 1), and state bytes are unchanged. This tests a real successful workflow and replay resistance.

**A02 — Missing signature and configuration.** For the same otherwise valid package, each of these **separately** must not accept: no signature path, no allowed-signers file, no identity, or missing/empty required signature metadata. It must never treat missing authentication as a request to skip the check. On refusal, the previous state bytes are identical or an absent state remains absent. Where authentication is unavailable rather than demonstrably invalid, report `COULD_NOT_LOOK`/exit 2 rather than misleading `REFUSED`/exit 1.

**A03 — Invalid signature cases.** An altered package byte after signing, altered signature, wrong signer identity, unknown public key, and wrong SSH signature namespace must be refused (or `COULD_NOT_LOOK` when verification cannot be performed), with zero persistent consumer-state changes. The positive control with the correct key must still pass. No test may count “always fail signature verification” as a valid defense.

**A04 — Missing verification tool.** Simulate an environment with the required signature-verification executable unavailable *without modifying the real machine*. Exit 2 (or equivalently documented `COULD_NOT_LOOK`), never accepted and state unmodified. The harness must not confuse a bad test PATH setup with a valid negative result.

**A05 — Signature does not override other checks.** A correctly signed v1 package that is not the latest witnessed entry, a witnessed package that is repeated, a package with a broken semantic check, and a rollback/truncated previously anchored witness log all remain refused with identical persisted state. Conversely, a legitimate, distinct, latest-witnessed signed package that extends the existing witness log is allowed and advances state. Signing cannot bypass Gate, witness or anti-replay checks.

**A06 — No unsigned state-changing escape hatch.** In the production consumer, attempts to use `--allow-unsigned` or an equivalent undocumented environment bypass are rejected at CLI validation or refused; no state changes. If an unsigned **inspection-only** mode is provided, it cannot call the consumer's acceptance/state mutation routine and must print `UNAUTHENTICATED` or `NOT_PROVEN`, never `SIGNED` or `ACCEPTED`. This tests the approved choice **inspection allowed, unsigned production acceptance disallowed**.

**A07 — Trust material failure.** Malformed, absent or unreadable allowed-signers; an identity inconsistent with its trust entry; and signature path unreadable must fail closed without state change. No fallback to treating a failed signature as a successful digest check.

## B — W2: locally trusted contract binding and backwards-compatible inspection

**B01 — New format and explicit binding.** Freshly generated v1 packages state schema `sv.package/1`, contract ID `sv.gate/0`, a documented version identifier and the locally expected Gate conformance digest `44823d0ff707213ae8bc310ed8b21e135f8e742fd8834e8f9474743d3a250628` (subject to pinning the actual unchanged contract at build revision). The version + digest fields are part of the canonical package-body digest and exact signed bytes. The independent verifier recognizes and recomputes the corresponding contract checks from **trusted local inputs**, not from another field in the package.

**B02 — Closed schema controls.** For v1, missing or malformed contract ID, version or digest; unknown required top-level keys; duplicated JSON keys; non-finite JSON numbers; and unsupported schema versions fail validation. A correct new v1 package and normal recognized fields pass the *same* schema checker. The required new fields cannot silently default to a passing contract.

**B03 — Contract substitution, the decisive negative.** Begin with a valid signed v1 package and trust configuration. Substitute (a) an incorrect digest, (b) a different contract name with the same digest, (c) a different version with the same digest. Recompute the package body's self-digest and sign each manipulated package with an authorized **test signing key** so package integrity and authenticity pass. **Each must still fail the locally trusted contract-ID/version/digest check**, with explicit reason. Otherwise W2 has not closed the gap and cannot be called DONE.

**B04 — Positive local comparison.** An authentic new v1 package with exactly the trusted Gate contract name, version and independently sourced digest must pass the contract check and the complete verifier. The suite must demonstrate B03 refusing three substitutions while B04 accepts. No self-referential “digest equals the package's own digest” test counts as contract binding.

**B05 — Gate decision behavior unchanged.** Verify **both** kernel and independently coded replay against all **4,690 pinned contract vectors**, with identical decisions, reason ordering and the existing conformance digest; run the documented conformance and mutation checks. The v1 packaging change must not alter any `sv.gate/0` decisions, including the existing all-DEFAULTED `ALLOW` limitation. A change to Gate semantics requires an explicit, separate owner-approved revision: it is **not** a passing P-001 implementation.

**B06 — Preserve archival bytes.** Hash all original tracked `sv.package/0` fixtures, signatures and witness logs **before and after** implementation. Each exact file SHA-256 must match; no in-place rewriting, resealing, resequencing or re-signing an old file. A historical signed package continues to verify its **original signature bytes** under legacy inspection and keeps `LEGACY_UNBOUND` contract status rather than receiving retroactive trusted contract fields.

**B07 — Explicit legacy separation.** Normal production consumer invocation with `sv.package/0` (even historically signed and witnessed) **refuses** without state update. An **explicit legacy inspection** invocation to the verifier reads the same original v0 bytes and reports `LEGACY_UNBOUND` and the historical semantic/signature results without pretending contract binding exists. The verifier's normal v1 path cannot silently upgrade v0, and a user must not mistake inspection success for new production acceptance. Legitimate signed v1 consumption still passes (A01).

**B08 — Compatibility and documentation.** Published examples state the separate roles of new signed v1 production consumption, explicit unbound v0 inspection, the local Gate contract trust anchor, witness/replay freshness boundaries and signature limits. No unsupported promise that all old scripts accept v1 unchanged. New example commands must be tested end to end on the pinned CI platform using throwaway keys, with preserved command lines and outputs. If one environment lacks `ssh-keygen`, record `NOT_TESTED` for that environment; do not report a successful signature check there.

## C — W3, known gaps, six PRs, and release finish line

**C01 — Known DEFAULTED limits not hidden.** Final `STATUS.md` and release notes explicitly identify (1) DEFAULTED-only `ALLOW` at the unchanged Gate contract, (2) unproven DEFAULTED → OPERATOR declaration and signer/declarer ambiguity, (3) SIGNED does not imply truth/freshness/independent declarer identity, and (4) what would be required to fix those limitations later. The exact original negative test/provenance links survive.

**C02 — Existing PR inventory.** Every PR `#34, #54, #55, #60, #61, #62` gets its own recorded terminal recommendation and **owner-authorized** final disposition (`MERGED`, `CLOSED` with reason, or documented known limitation/referenced retained evidence). The record carries actual GitHub PR links, relevant CI/runner identity, source and limits. No tool/AI silently closes or merges them merely to satisfy the table.

**C03 — Overlap and negative controls.** Resolve `#34` vs `#62` as one correct change to the PR #8 status without duplicate conflicting text. Preserve PV-1/AMB-1 negative findings from `#54/#55` as gaps/limits, not fixed bugs. Mark `#60` registration-only/unrun. For `#61`, no claim of reproducible Vulkan correctness, and **void** the failed perplexity rows; if raw device logs cannot be supplied, explicitly print `RAW_EVIDENCE_UNAVAILABLE` or equivalent with the narrower claim and retain the failure. `#62` must not portray Azure LDE as validated SV on Azure.

**C04 — Finite non-PR inventory.** List open issues, material unmerged branch categories and active project workflows/jobs from a dated source snapshot. Claude's earlier counts (0 issues / 11 workflows / 72 branches) are an unverified historical claim until compared with source records at release. Every *in-scope* unresolved issue has a terminal disposition or explicit documented limitation. Preserve historical branches, with deletions a separate owner decision; do not conflate “not deleting branches” with “unfinished research.”

**C05 — Operations.** The daily Moltbook scout is not auto-disabled or deleted. Chad explicitly chooses keep or disable; the final record states the chosen policy, who operates it, and how it relates to maintenance-only status. Historical scout logs/branch retained regardless. An owner choice, not a unit test, is the acceptance evidence.

**C06 — CI and regression.** All applicable legacy SV tests, new W1/W2 acceptance tests and anti-vacuity tests pass in pinned GitHub Actions runs against the proposed merge revision. Do not state S25/Windows or independent outside replication where only Linux CI ran. Failed/canceled runs are retained with disposition. One mutant that bypasses signature checking, one that trusts the package's self-asserted contract digest, and one that refuses all input must **all be caught** by frozen acceptance.

**C07 — Release evidence.** Chad reviews and authorizes each merge, resolves any `STOPPED_CONTESTED`, and selects the release version according to actual CLI and package compatibility. The final annotated/tagged release, commit SHA, contract conformance digest, package schema versions, evidence/limitation manifest, reference to all six PR dispositions, and `maintenance-only` statement are published. The documentation must state **NOT PRODUCTION-READY / NOT INDEPENDENTLY SECURITY-VALIDATED**. Tagged bytes must correspond to the actual owner-reviewed merged revision. No assumption that passing CI alone certifies production readiness.

**C08 — No backdoor through “done”.** A project may be described as close-out complete only if all C01–C07 evidence and explicit owner decisions exist. If some work is not complete, publish its exact status and request Chad's explicit choice to close as a limitation, not an AI self-certification. No new ideas migrate into P-001 to extend it indefinitely. After the owner-approved release, Veritas-Origin DPC-001 resumes from its *previously frozen* spec and test custody, not from rewritten outcomes.

## D — Scoring, review boundaries, and stop rule

A completed acceptance report shall contain a table with one row for **A01–A07, B01–B08, C01–C08**. Each row has `PASS / FAIL / NOT_RUN / NOT_APPLICABLE / CONTESTED`, exact code SHA, reproducer command, actual-versus-expected observation, and link to preserved output. Documentation-only controls C02/C04/C05/C07/C08 additionally require an exact source or Chad's recorded authorization.

No aggregate green verdict is permitted when a mandatory row is FAIL, NOT_RUN or CONTESTED. `NOT_APPLICABLE` requires explicit technical reason and Chad's approval; it cannot be used merely because implementation is inconvenient. CLI checks must distinguish a genuine deliberate refusal from verifier/tool unavailability. Raw evidence integrity and semantic validity are separate checks.

**Before build:** Claude critiques **this** contract once and authors one `PLAN.md` on a separate branch or review note, without editing the originating `ACCEPTANCE.md`. ChatGPT may issue at most the charter's bounded clarification; Chad resolves disputes and freezes exact acceptance bytes. **After build:** Claude implements and runs; ChatGPT tries to break it, preserving failures. The frozen tests are not rewritten to fit the implementation. Maximum two review rounds per item; disagreement goes to Chad. Three consecutive unproductive rounds stop P-001 for Chad's decision.

**EN:** These are proposed pass/fail rules, not executed tests. They require valid signed v1 acceptance, reject unsigned/unbound/forged examples, preserve v0 history and negative findings, and require Chad to sign off on release. Next: Claude's single critique, then Chad freezes the contract before any code.
