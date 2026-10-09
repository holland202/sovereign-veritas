# P-001 close-out package (proposed outcome; nothing here is merged, closed or tagged)

```yaml
artefact: p001/CLOSEOUT
by: Claude (Opus 5.5)        # Chad directed 2026-10-09; not reviewed line by line
frozen_contract: coordination/p001/ACCEPTANCE.md @ 1c16e661 (sha256 dc54e8c1...b4d28d)
implementation: PR #66 @ 73957ec (code 5bec876); report docs/P001_ACCEPTANCE_REPORT.md
snapshot: 2026-10-09T20:01Z (GitHub REST)
verdict: READY_FOR_OWNER_DECISION; P001_NOT_DONE until Chad decides the card in section 7
next: ChatGPT (one bounded review of this file) -> Chad (one decision card)
```

## 1. Outcome in one paragraph

W1 (signed consumer), W2 (`sv.package/1` bound to the locally trusted Gate contract) and A08 (atomic state write) are implemented in PR #66. Every frozen A and B case passes, all three planted mutants are caught, and all 55 CI checks are green on Linux, macOS and Windows. That evidence is **self-tested**: the same AI wrote the code and the tests, ChatGPT reviewed the source without running it, and no outside party has reproduced it.

The Gate's decisions did not change (4,690 vectors, digest `44823d0f…0628`). The W3 limitation (an all-DEFAULTED package gets ALLOW) is kept, and nothing about it was fixed.

What remains is owner action: merge decisions on 7 PRs, the scout, the version and the tag. Nothing technical is left open inside the frozen scope.

**Label:** NOT PRODUCTION-READY / NOT INDEPENDENTLY SECURITY-VALIDATED.

## 2. Failures and negative findings, kept (C01, C03)

| Finding | Where it stays | Status at close |
|---|---|---|
| W3: an honest all-DEFAULTED package gets ALLOW | PR-1 (#36), `docs/PR1_RESULTS.md`; still HELD on #66 (B05) | KNOWN LIMITATION, not fixed |
| PV-1: DEFAULTED→OPERATOR relabel verifies CONSISTENT and, if signed, SIGNED; no field names a declarer | PR #54 | confirmed gap, KNOWN LIMITATION |
| AMB-1: 5 impostor gates reproduce all 4,690 vectors; the worst false ALLOW is 1,235/10,000 | PR #55 | KNOWN LIMITATION; the 800 extra vectors are **not** adopted |
| XB-1 race (X4) and effect-without-record (X5) | `docs/EXECUTION_BOUNDARY_RESULTS.md` | open, KNOWN LIMITATION |
| EO-1: the record reports the workflow's account, not the effect | `docs/EO1_RESULTS.md` | open |
| A consistent rewrite verifies; signed ≠ true or fresh | README, `docs/P001_SIGNED_WORKFLOW.md` | by design, stated |
| Concurrent consumers, first use (P-001) | `docs/P001_SIGNED_WORKFLOW.md` | documented, not tested |
| P-001 build regressions caught by CI (EO-1 digest, `schema` guard SURVIVED, JG-2 P7), and `ietf_map.py` 12/14 | `docs/P001_ACCEPTANCE_REPORT.md` | fixed or recorded, listed first |
| VK-1: Vulkan on Adreno gives wrong output; the perplexity control failed; registered after the run; raw device logs not pushed | PR #61 | RAW_EVIDENCE_UNAVAILABLE (see section 3) |

## 3. The six older PRs (C02, C03): recommendation, evidence, condition

Trial check (container, 2026-10-09): `p001/build-w1-w2` @ `73957ec` merged with #54, #55, #60, #34 and #61 with **no conflicts**. On that merge:
- full suite: `540 passed, 1 skipped`;
- `pv1_probe.py` exit 0 (6 of 6 as registered), `--sabotage` exit 1;
- `amb1_probe.py` exit 0 (4 of 4), `--sabotage` exit 1.

So the registered results survive W1/W2. #62 was not included in the trial because it conflicts with #34 on purpose (see its row).

| PR | CI on its head | Recommendation | Why |
|---|---|---|---|
| #34 STATUS: PR #8 merged | 36/36 green | **MERGE** | A one-line fix with the exact merge commit (`73de3f7`, verified). STATUS on main still says "PR #8, open", which is false. |
| #54 PV-1 | 55/55 green | **MERGE as a finding** | A negative result with registration first (`5eaa134`), sabotage and CI. It merges a confirmed gap, not a fix. |
| #55 AMB-1 | 57/57 green | **MERGE as a finding**, without adopting the 800 vectors | Registration first (`c179025`). Its thresholds were set after a disclosed exploratory run; keep that disclosure. |
| #60 SM-1 | 55/55 green | **CLOSE**: registration only, never run | The branch is kept. Merging an unrun registration would imply work that wasn't done. |
| #61 VK-1 | 55/55 green | **CLOSE in this repo** as `RAW_EVIDENCE_UNAVAILABLE`; branch kept; move it to the S25-accelerator line if Chad pushes `results.jsonl` and `logs/` | It is not Sovereign Veritas work. Its perplexity control failed (every perplexity cell is void), its registration came after the run, and its raw data is not in the repo. The finding "Vulkan output wrong, NOT DEMONSTRATED correct" stays visible on the closed PR. |
| #62 Azure LDE note | 54 green, 1 cancelled | **CLOSE**; superseded by #34 for the shared sentence | It rewrites the same STATUS sentence as #34, which conflicts. It also adds a **different project's** (LDE) result to the top of SV's STATUS. Its own text says that result is NOT VALIDATED and not about SV. Keep it on its branch and in the LDE dataset. |

## 4. Inventory (C04), snapshot 2026-10-09T20:01Z

| Item | Count | Disposition |
|---|---|---|
| Open issues | 0 | — |
| Open PRs | 10: #34 #54 #55 #60 #61 #62 (section 3), #63 tracking, #64/#65 ChatGPT coordination, #66 build | #63–#65 merge or close with P-001 as the coordination record; #66 is Chad's review |
| Workflows | 11: amb1, dk, eo1, ep0, ep1, fault-injection, g1-4-drain, g1-recount, pv1, tests, xplat | Keep; `tests` and `red-team` are the referee. amb1/pv1 land with #55/#54 |
| Branches | 74 (38 experiment/, 17 docs/, 5 feature/, 3 fix/, 2 coordination/, plus single ones) | Untouched. Deleting branches is a separate owner decision. Not deleting them is not unfinished work |
| Tags | 1 (`archive/ab-recovery-amos-tipton`) | unchanged |
| Releases | 0 | section 6 |

Correction carried from my own earlier counts: the earlier figures were 72 branches and "17 packages in evidence/". The branch count is now 74 (the P-001 branches were added since). `evidence/` holds 9 packages plus 8 signatures; I had counted the two together as 17.

## 5. Daily Moltbook scout (C05)

It is an owner choice, so nothing has been changed. Both models recommend **disabling the daily task after close-out and keeping the `scout` branch and its records**. Without that, a repo marked maintenance-only still has a live research job attached to it.

## 6. Release proposal (C07)

- **Version: `0.2.0`.** This release breaks compatibility in two places: a new package format (`sv.package/1`), and a consumer CLI that now requires signature flags.
- **Fix the existing version mismatch at release:** `pyproject.toml` says `0.1.0` and `sovereign_veritas/__init__.py` says `0.1.1`.
- **Order:**
  1. Chad reviews and merges #66.
  2. Merge #34, #54 and #55. CI must stay green on `main` after each one.
  3. Close #60, #61 and #62 with the reasons in section 3.
  4. Apply the STATUS and release-note text below and the version bump, in one docs PR.
  5. Chad creates an annotated tag `v0.2.0` on the merged commit. Claude's proxy cannot push tags, and the tag should be Chad's act anyway.
  6. Add a maintenance-only notice to README and STATUS.
- **Release notes (draft):**
  > **v0.2.0 — signed, contract-bound evidence packages (research prototype).**
  > - New packages are `sv.package/1`. They carry `contract: {id: "sv.gate/0", conformance_digest}` inside the signed body. The verifier checks it against its own pinned trust anchor.
  > - `tools/consumer.py accept` requires `--signature --allowed-signers --identity`, accepts only `sv.package/1`, and writes state atomically.
  > - Legacy `sv.package/0` files are unchanged and can be inspected with `verify_package.py --legacy` (`CONTRACT LEGACY_UNBOUND`).
  > - Gate decisions are unchanged.
  > - Known limitations: W3, PV-1, AMB-1, XB-1 X4/X5, EO-1, concurrent consumers, first use, and signed ≠ true or fresh.
  > - Self-tested by one author with AI tools (Claude, ChatGPT). **NOT PRODUCTION-READY / NOT INDEPENDENTLY SECURITY-VALIDATED.** Not validated on the S25 for this release.
- **STATUS addition (draft):** the same text as a dated "Latest (2026-10-xx): P-001 close-out" block, linking `docs/P001_ACCEPTANCE_REPORT.md`, `docs/P001_SIGNED_WORKFLOW.md` and this file.

## 7. The one decision card for Chad (C08)

| # | Decision | Recommended default |
|---|---|---|
| D1 | Approve #66 after your review (W1/W2/A08) | merge |
| D2 | The six older PRs as in section 3 | merge #34 #54 #55; close #60 #61 #62 |
| D3 | Scout | disable after close-out, keep the records |
| D4 | Version and tag | `v0.2.0`, annotated, tagged by you after the merges |
| D5 | Mark the repo maintenance-only, then resume Veritas-Origin | yes |

Not decided by any model: whether your review of #66 is complete. A reply of "approve defaults" covers D2–D5 once D1 is done.

## 8. Not done and not claimed
- S25 run of the P-001 build.
- Independent reproduction.
- An outside security review.
- The assessor-evidence research (ChatGPT's proposal on #63): a separate future track, not in P-001.
- John Rodriguez's points (immutable records and process, FIPS, MFA, stronger crypto): external feedback, kept as feedback and not treated as verified findings. They are backlog items for that track.
