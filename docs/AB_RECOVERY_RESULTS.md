# Amos Tipton's A/B Recovery Challenge: results

The challenge was proposed by Amos Tipton (LinkedIn, 2026-10-02). It is registered in
`docs/AB_RECOVERY_PREREG.md`, commit `7fb1c48`, pushed before the harness existed. The harness ran
against unmodified code at `facadc2`. It refuses to run if `vehicle_action.py`, `decision.py` or
`workflow.py` differ from that commit.

- Run: `python tools/ab_recovery_challenge.py`, in a Linux container, Python 3.13.15.
- Output: `results/ab_recovery/run.txt` and `results.json`.
- Not run on the S25.
- Nothing flew: the executor only records commands.

Amos's involvement is the question. It is not an endorsement of anything here.

## Read this first: "12 of 12 as registered" is not "12 of 12 passed"

Every registered prediction held. But the registration was written by reading the code, and most of
its predictions were **predictions of failure modes**. Holding means the code fails where reading it
said it would. That makes these numbers a description of the code, not a defence of it.

## What the code permitted and refused (cross-check = `max_nav_disagreement_m` 25 m)

| Case | A | B | Cross-check on: goto / rtl / land | Cross-check off |
|---|---|---|---|---|
| 1 | trusted | fresh, agrees | ALLOW / ALLOW / ALLOW | all ALLOW |
| 2 | spoofed, truly 111 m N | fresh, true position | REFUSE / REFUSE / ALLOW | all ALLOW |
| 2g | GPS-glitch flag | fresh, agrees | REFUSE / REFUSE / ALLOW | REFUSE / REFUSE / ALLOW |
| 3 | spoofed, no flag | unavailable | REFUSE / REFUSE / ALLOW | all ALLOW |
| 4 | spoofed, no flag | stale 600 s, labelled stale | ALLOW / ALLOW / ALLOW | all ALLOW |
| 5 | as 3, approval "invalidated" | unavailable | identical to 3 | identical to 3 |
| 6 | as 4, approval "invalidated" | stale | identical to 4 | identical to 4 |
| 7 | spoofed, no flag | derived from A | ALLOW / ALLOW / ALLOW | all ALLOW |
| 8 | spoofed, no flag | cached case-1 snapshot | ALLOW / ALLOW / ALLOW | all ALLOW |

A goto back to the fence centre, the "equivalent recovery path", always got the same decision as
`goto` and `rtl`. Every refusal reached the Gate as the single reason `verification_not_passed`. The
cause (disagreement, glitch, no B) survives only in the check's text inside the package.

## Classification, against the registered result categories

| Case | Result | Why |
|---|---|---|
| 1 | **Correct handling** | Baseline. |
| 2, cross-check on | **Correct handling** | The disagreement is detected and named; `rtl` and `goto` are refused. Invalidation did not become authorization (AB-P9). |
| 2g | **Correct handling** | The glitch flag refuses movement and `rtl` without needing B. |
| 3, cross-check on | **Correct handling** | Unavailable B is treated as missing, never as support or as "no contradiction" (failure mode D does not occur). |
| 2, 3, cross-check off | **Fail-closed bypass by configuration** (mode E) | The same snapshot and action are refused with the limit and allowed without it. The limit is a request field set by the requester. The package records which configuration was used, so the bypass is visible after the fact, not prevented. |
| 4, 6 | **Specification gap** (mode C) | Stale B is accepted as current. The snapshot's `xpos_age_s: 600` and a source label reading "STALE" are both ignored. Nothing in the contract asks for freshness, so this is not an implementation defect. Note how the case was built: the stale fix happens to sit where the spoofed A claims to be (the spoofer holds the belief while the vehicle drifts). |
| 7 | **Hidden dependency** (modes A and I) | B derived from A agrees with A, and the spoof passes the cross-check. The code cannot represent B's dependencies. V14g showed the same thing in the model; this shows it through the real Gate. |
| 8 | **Specification gap** (modes C and J) | A replayed pre-spoof snapshot is accepted. The verifier binds the check to the snapshot's digest, not to when it was read. |
| 5, 6 vs 3, 4 | **NOT TESTABLE UNDER CURRENT CONTRACT** | There is no approval state to invalidate. The Gate is stateless; Proposition A can only be asked as "would the same request be allowed now?". Cases 5 and 6 are byte-identical to 3 and 4 by construction (AB-P6). That proves only that the dimension has no input, and it is not counted as a pass. |
| `land`, every case | **Correct by the contract, and the open recovery question** | `land` is allowed with no evidence about position, by design ("land must never be refused for lost navigation"). Its allowance does not depend on A's status: it is allowed in case 1 too. But this is exactly Amos's dependency-inheritance concern: ArduCopter's LAND holds position on GNSS while it has a lock. So the recovery the system permits can be steered by the failed source (V14f in the model: 59.95 m). The code has no way to say "land without A". |

## Answers to the two propositions

- **Proposition A, "is the previous approval still valid?":** the code cannot represent the question.
  Approvals are not stored. What it can do is refuse a fresh identical request, and it does in cases 2,
  2g and 3 (with the cross-check on). It does not in 4, 7 and 8.
- **Proposition B, "is there sufficient trustworthy evidence to authorize recovery?":**
  - `rtl` and centre-`goto` require A, so they are refused whenever A is detectably bad. B can never
    stand in for A (R1: B is a veto only).
  - `land` requires nothing.

  So the code never turns invalidation into authorization. It also never authorizes a recovery *on
  B's evidence*: the only recovery left once A is invalid is the one that needs no evidence. And that
  one, in the real autopilot, may navigate by A.

## Limitations

- **Snapshots are constructed, not measured.** B is a stand-in everywhere, as in V12–V14. A real
  independent source, its noise and its failure modes are untested.
- **The harness copies `main()`'s wiring rather than calling it.** Control C0 shows they agree on case
  2. Other cases rely on the copy.
- **XB-1 and XB-2 (an effect with no record, duplicates on crash) are not re-tested here.** They
  apply to any ALLOW in this matrix.
- **Same author.** Claude wrote the registration, the harness and this classification. An independent
  reading of the matrix would be a stronger check.

## What would change these results (not built; each needs its own registration)

1. **Freshness for B.** A registered maximum age, with a missing or unparseable age treated as stale.
   It would turn cases 4, 6 and 8 into refusals. It would not help case 7.
2. **A dependency declaration for B,** checked against an allowlist of roots. It is only as good as the
   declaration: a lying B still passes. That is the epistemic boundary, not a fixable defect.
3. **A policy-pinned cross-check,** so the requester cannot drop the limit. It closes the R2 bypass.
4. **A landing mode that does not navigate by A,** or a refusal to call a landing a recovery when it
   does. That one is outside this repository: it depends on the autopilot.

## Credit

The question is Amos Tipton's. Matrix: Chad Holland. Mapping, registration, harness and this write-up:
Claude (Opus 5.5).
