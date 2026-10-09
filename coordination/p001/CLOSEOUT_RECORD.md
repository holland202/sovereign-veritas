# P-001 close-out record (what happened, after the tag)

```yaml
artefact: p001/CLOSEOUT_RECORD
by: Claude (Opus 5.5)        # Chad directed and approved the release plan 2026-10-09; outcome-level review
release: v0.2.0 (annotated tag 0fafe198, created and pushed by Chad) -> ecd4de97cd695d59852442f2bec80d831b296449
release_gate: NOT FULLY GREEN at tag time (two QEMU legs NOT_RUN, see C06)
state: P001_RELEASED_PENDING_QEMU_RERUN
```

This file is new, additive documentation **outside** the tagged snapshot. Nothing at `v0.2.0` is rewritten and the tag is not moved. `docs/P001_ACCEPTANCE_REPORT.md` *at the tag* is the implementation-stage report: it says `aggregate: NOT GREEN` with C01–C05, C07 and C08 `NOT_RUN`. It was accurate when written (at `5bec876`) and was not updated afterwards. This record supersedes it for the C rows.

## The seven close-out rows

| Row | Disposition | Evidence |
|---|---|---|
| C01 known limits not hidden | **DONE** | `STATUS.md` and `docs/RELEASE_NOTES_v0.2.0.md` at the tag: W3, PV-1, AMB-1, XB-1 X4/X5, EO-1, concurrent consumers, first use, signed ≠ true or fresh, plus the NOT PRODUCTION-READY / NOT INDEPENDENTLY SECURITY-VALIDATED label |
| C02 six old PRs | **DONE, one deviation** | #34 #54 #55 merged through #67; #60 and #62 closed with reasons. **#61 was merged although the approved plan said close.** It was kept after a re-check (row C03) and recorded in #68 |
| C03 overlap and negatives | **DONE, with a correction** | #34 carries the PR #8 fix; #62 closed. PV-1 and AMB-1 merged as findings. VK-1: the close-out's "raw evidence unavailable" was **wrong**. The raw files were in the PR (`11bdad2`), and `vk1_probe.py --report` re-derives the pinned digest `e464c944…` (`RECORDED match`). Perplexity cells void, registration after the run; both kept |
| C04 inventory | **DONE** | `CLOSEOUT.md` section 4 (snapshot 2026-10-09T20:01Z) |
| C05 scout | **DONE** | Scheduled task "Moltbook scout (read-only)" (`trig_011tErzpqainhU1TagNxmDVV`) has been disabled since 2026-10-04 and was confirmed disabled on 2026-10-09; the `scout` branch and its records are kept |
| C06 CI and mutants | **PASS except 2 legs NOT_RUN** | At `ecd4de9`, 31 of 33 checks pass, including tests on Linux x86/arm, macOS and Windows; red-team: `verifier_mutants` 28/28 killed and `p001_mutants` 3/3 killed. **xplat L5 s390x and L6 ppc64le: NOT_RUN.** Docker Hub `toomanyrequests` hit before any test, on `52814aa`, `94fba7c` and `ecd4de9`, and again on one rerun (run `37990718927`). Both legs passed at `709da9e`. They are neither passes nor software failures |
| C07 release evidence | **DONE, with a gate deviation** | Annotated tag by Chad on the exact merged revision, with the version reconciled to 0.2.0. **Deviation:** the approved gate was all applicable CI green on the exact SHA *before* tagging; the tag was pushed while L5/L6 were NOT_RUN. Recorded here, not waived |
| C08 no backdoor through "done" | **OPEN until the L5/L6 rerun** | P-001 closes once L5/L6 have actually run on `ecd4de9` and their result is recorded here. If either fails inside a test, it becomes a finding against v0.2.0 and Chad decides |

## Pending (scheduled, verifiable)
- **The rerun is scheduled:** task "Re-run v0.2.0 QEMU legs" (`trig_01CLo7ue3xYD1a3982uNxpes`), next run 2026-10-10T00:25:00Z (7:25 pm CDT). It fired once early on 2026-10-09 21:25Z (a known quirk), and nothing was run then because the rate-limit window had not reset. Its outcome will be appended here.
- After that: a maintenance-only notice on `main` (Chad merges it), then Veritas-Origin resumes.
