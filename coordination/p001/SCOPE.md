# P-001 — Sovereign Veritas finite close-out: approved scope record

**Project:** `holland202/sovereign-veritas` — P-001.  
**Owner decision:** Chad Holland replied “I approve” on 2026-10-09 to the exact question “Do you approve the amended P-001 scope in PR #64?” The owner's decision is recorded on [PR #63](https://github.com/holland202/sovereign-veritas/pull/63#issuecomment-6084385118).  
**Scope sources:** Claude's [revised proposal](notes/2026-10-09_claude_002.md); ChatGPT's [approved amendments](notes/2026-10-09_chatgpt_001.md) in [draft PR #64](https://github.com/holland202/sovereign-veritas/pull/64); P-001 [charter](CHARTER.md) and [FACTS](FACTS.md).  
**Source behavior baseline:** `main` `709da9e` as pinned by FACTS; NOT a claim that ChatGPT reran it.  
**Status:** `OWNER_APPROVED_SCOPE / SCOPE_RECORD_AWAITING_EXACT_REVISION_FREEZE`. The human approved the referenced written proposal and amendments **before this transcription existed**; consequently this file's exact bytes are **not** yet independently owner-frozen. Do not call acceptance or implementation authorized by this file alone. Record the exact file revision in PR #63 once Chad has reviewed it.

## Goal and non-goals

Finish and archive Sovereign Veritas as an **experimental, non-production research prototype**, then mark it **maintenance-only** and resume the parked Veritas-Origin DPC-001 work. A finished project means all enumerated outstanding items are assigned a documented terminal disposition, a release at an exact revision is reviewed and tagged by Chad, the user-facing status accurately states what is and is not demonstrated, and no unsupervised research loop remains under this project's authority.

**Not a goal:** world-truth attestation, external-consequence authorization certification, unproven independence, new Gate semantics, new science, a new security architecture, autonomous code changes, or closing failures by renaming them successes.

## In-scope engineering work

### W1 — Signed-by-default consumer acceptance

`tools/consumer.py accept` currently accepts packages without checking signatures unless `--signature` is supplied. **Target:** a production consumer path must require a valid signature checked against an explicitly configured trusted identity/key; no missing/invalid/uncheckable signature may update consumed-package state or witness anchors. Preserve existing replay, rollback, witness and semantic verification checks and differentiate `REFUSED` from `COULD_NOT_LOOK`.

**Development exception decision remains OPEN:** A dedicated unsigned **inspection-only path** is preferable to an unsigned state-changing consumer mode. An explicit `--allow-unsigned` is in scope only as a clearly unsafe, isolated *development* option if the proposed plan and tests guarantee that development state cannot be confused with an authenticated production state. The human owner must choose the exception policy **before ACCEPTANCE.md is frozen**. Never silently accept unsigned input on a missing/failed signature or relabel it SIGNED. “Signed” attests approved key possession, not evidence correctness or truth.

### W2 — Explicit Gate contract binding in new evidence packages

Create a versioned package format containing **Gate contract ID + version + conformance digest**, covered by canonical package integrity and any signature. At verification, compare to the **locally trusted** implementation/contract definition, not a value merely repeated by the package writer. The current published digest is `44823d0ff707213ae8bc310ed8b21e135f8e742fd8834e8f9474743d3a250628`; remeasure/pin it at the exact implementation revision before freeze. An unexpected digest, wrong rules ID, missing fields, or unsupported version must fail closed.

**Compatibility decision remains OPEN:** The existing format is `sv.package/0`, with closed schema and signed published package bytes. The default engineering proposal is a distinct `sv.package/1` with preservation of all old package files, hashes, signatures and witness history untouched. Legacy `sv.package/0` may be **inspected/verified only with an explicit legacy/unbound status**; consuming it in the new hardened production path is proposed to be refused by default. Chad chooses a precise legacy policy before the acceptance contract is frozen. Do not rewrite history or claim a legacy package had contract binding retroactively. Changing the package schema does not by itself change the Gate decision-rule digest.

### W3 — DEFAULTED evidence

Record as a **KNOWN LIMITATION**, with direct links to original PR #36 evidence and related PV-1 PR #54. All-DEFAULTED `ALLOW` and `DEFAULTED → OPERATOR` sealer/declarer ambiguity must be accurately described. **No Gate behavior change, new contract vectors or new Gate conformance digest for W3 in P-001.** Proposed remedies move to the backlog. Make release safety implications visible, not buried in a long report.

## PR close-out inventory

All six identified older PRs must receive a human-approved documented disposition; the initial recommendation is **not a merge authorization**:

| Item | Scope decision | Condition for terminal disposition |
|---|---|---|
| [#34](https://github.com/holland202/sovereign-veritas/pull/34) | Review then close as superseded if #62 contains the correction; else merge | Both edit `STATUS.md` about PR #8 having already merged; prevent duplicate or conflicting change. |
| [#54](https://github.com/holland202/sovereign-veritas/pull/54) | Conditionally merge preserved negative finding | Check CI, original evidence and provenance; keep PV-1 as a confirmed **gap**, not a fix; label container-only and self-tested. |
| [#55](https://github.com/holland202/sovereign-veritas/pull/55) | Conditionally merge preserved negative finding | Check CI, original evidence and limits of contract-vector coverage; don't silently adopt new vectors or imply exhaustive conformance. |
| [#60](https://github.com/holland202/sovereign-veritas/pull/60) | Close, with unrun registration link | Registration-only; no result fabricated and no new experiment authorized. |
| [#61](https://github.com/holland202/sovereign-veritas/pull/61) | `PENDING_EVIDENCE / CONTESTED` until owner adjudicates | Raw device logs were not confirmed published; perplexity anti-vacuity failed. Either merge a precisely labeled, limited negative report with failures intact or close and archive with `RAW_EVIDENCE_UNAVAILABLE`; CI green cannot erase missing evidence. |
| [#62](https://github.com/holland202/sovereign-veritas/pull/62) | Conditionally merge/correct or close | Ensure Azure LDE vs SV claims stay separate; conflicts in exit-code evidence stay visible; resolve overlap with #34. |

Also enumerate other **open issues, branches and active scheduled workflows** and classify as fixed, merged, closed, documented known limitation or explicit unrelated backlog item. Enumeration is a review requirement, **not permission to merge/close additional items**. Do not rewrite PR registration or experiment history.

## Known-limitations and evidence ledger

The final `STATUS.md` and release notes must disclose, at minimum:
- W3 DEFAULTED-only ALLOW and PV-1 provenance ambiguity.
- Signature authenticity ≠ world truth, freshness, third-party declarer identity or authorization by a real person.
- Conformance vectors underdetermine some unseen behaviors (AMB-1); separately distinguish the actual verifier replay from an independent implementation.
- Remaining retry/race/effect-without-record and reservation/key lifecycle assumptions where not fully solved.
- Hardware/runtime-specific negative outcomes such as VK-1 (bad Vulkan decoding, void perplexity instrumentation) without overclaiming reproduction.
- Any unverified source/environment, including Azure LDE cross-substrate conflict and incomplete raw artifact custody.
- `NOT PRODUCTION-READY / NOT INDEPENDENTLY SECURITY-VALIDATED`; no release may imply anything else.

Original evidence is **append-only** in spirit; preserve raw failed runs and source commits. Release manifest must distinguish raw evidence, derivations, self-tests, observed CI, externally repeated measurements, and unverified claims.

## Phases and finite stop conditions

1. **Scope (current):** Claude proposes, ChatGPT challenges, Chad chooses; no more scope debate without human instruction. Record exact scope revision and human freeze.
2. **Design:** ChatGPT independently authors `ACCEPTANCE.md` with explicit runnable expectations and anti-vacuity examples; Claude critiques once and proposes `PLAN.md`. Chad **freezes the exact acceptance bytes** by commit SHA (and preferably SHA-256) **before code changes**.
3. **Build:** Claude alone implements on the authorized P-001 build branch, using the frozen acceptance unmodified. Add tests rather than silently editing requirements. ChatGPT challenges implementations. Max two review rounds per item; unresolved => `STOPPED_CONTESTED` for Chad.
4. **Done:** Both agents give separate DONE/NOT-DONE notes; CI and reproducible checks are evidence, not truth. Chad alone decides merge, release, label and tagging; any unresolved failure is surfaced, not hidden.

If three consecutive collaboration rounds do not change code, tests, evidence or a decision, **pause** for Chad. Track human-review time. No PR or issue may be called DONE merely because the models agree or have green tests.

## Operations and release gate

**Daily Moltbook scout:** Chad alone decides to KEEP or DISABLE recurring execution. Suggested default at project retirement: disable recurring scouting, preserve `scout` branch/logs, optionally restart later under a separately approved VO budget. **No change authorized yet.**

**Release:** precise version number after assessing schema/CLI compatibility; proposed `v0.2.0` is NOT yet approved as the final version. Require signed-use quick start, old-package policy, passing frozen acceptance and anti-vacuity cases, applicable CI/device boundaries, file/evidence manifest, the disposition register, honest known-limitations list, reviewable tag commit, and maintenance-only notice. Tag only by Chad. Work goes to the Veritas-Origin precheck **only after the P-001 close-out is evidenced**, unless Chad explicitly changes that rule.

**Open design selections before acceptance freeze:** W1 development override versus inspection-only; W2 production consumer legacy handling; Moltbook scout keep/disable (operational owner decision). These do not authorize new research or indefinite debate.

---

**Freeze warning:** This file transcribes a preexisting approved scope; it is not the historical evidence source and its exact bytes have not yet been separately approved by Chad. Do not report `SCOPE_FROZEN` merely because a commit exists.
