# Lineage — influence claims, in both directions, treated as claims

An influence claim ("X shaped Y") is handled like any other claim in this repository: it has evidence, a
status, and it can be wrong. This applies equally to claims that outside work shaped Sovereign Veritas and to
claims that Sovereign Veritas shaped someone else's system.

## What the principles are, and are not

Fail-closed defaults, separating authorization from execution, reference monitors, separation of duty,
independent verification, append-only audit and idempotent effects are **established ideas** in security and
distributed-systems engineering. They predate this project. Sovereign Veritas does not claim to have originated
any of them. What it can be credited for is **its formulation and implementation**: the evidence-package
format, the Gate contract (`sv.gate/0`, `CONTRACT.md`), the separate verifier, the registered experiments, and
the published failures.

## Suggested acknowledgment for systems that draw on this work

> **Methodological lineage:** This system draws on the formulation and implementation of evidence-bound
> authorization, separation of authorization from execution, fail-closed governance, and independent
> verification in Chad Holland's open-source Sovereign Veritas research
> (https://github.com/holland202/sovereign-veritas).

Use it only if it is true for your system. The MIT license requires the copyright notice on copies of the
code; this acknowledgment is a request, not a license term. Citation format: `CITATION.cff`.

## How a lineage claim is assessed

**Claim:** "Work A influenced system B."

| Evidence (strongest first) | Example |
|---|---|
| Code lineage | copied or ported files, identical identifiers, the same contract vectors or digests |
| Explicit citation | B's documentation cites A by name or URL |
| Dated precedence plus specific shared detail | A's dated public commit has a distinctive detail that B later has |
| Copied terminology | A's own coinages (not generic terms) appear in B |
| Correspondence | messages showing B's author saw A |
| Timing alone | B appeared after A was public — **not sufficient by itself** |

**Status:** **SUPPORTED** (direct evidence of code lineage or citation, or dated precedence plus a specific
shared detail) · **NOT SUPPORTED** (the evidence points elsewhere, or the shared parts are generic prior art) ·
**INDETERMINATE** (plausible, not shown). Generic principles from the section above never support a claim on
their own.

## Inbound: what shaped this repository

| Claim | Evidence | Status |
|---|---|---|
| Davorin Popović's report prompted XB-1 (execution boundary) | his AI-assisted private review/report (2026-10-02) citing `386716a` (wording per his review, 2026-10-06); `docs/EXECUTION_BOUNDARY_PREREG.md` quotes it before the probe existed; his reply confirming it | **SUPPORTED** — credit for the report, not the reproduction or fixes |
| Davorin Popović's question prompted XB-2 | his reply to the XB-1 results, quoted in `docs/XB2_PREREG.md` | **SUPPORTED** — the question; designs and predictions are this project's |
| Nicholas Kouns' breaks shaped fixes `2902a2c`, B4/B11 | issues #4 and #5, `docs/ISSUE_4_RESPONSE.md`, `docs/ISSUE_5_RESPONSE.md` | **SUPPORTED** |
| eace's mutation method shaped `tools/verifier_mutants.py` | `docs/INTEGRATION.md`, eace `1991750` | **SUPPORTED** (same author) |
| evidence-ledger's vocabulary shaped `evidence_states` | `docs/INTEGRATION.md`, evidence-ledger `ccf9144` | **SUPPORTED** (same author) |
| The "Dependent Evidence" proposal shaped V14 | the proposal text, critiqued in `docs/V14_CORRIDOR_PREREG.md`; concept Chad Holland's by his account; drafter of the text not recovered | **INDETERMINATE** as to who drafted the text; see `docs/V14_CORRIDOR_RESULTS.md`, provenance correction |
| Perplexity's external analyses (2026-10-02) shaped the attack-surface test plan | the three texts verbatim in `docs/external/`, with hashes; `docs/EXTERNAL_CRITIQUE_PERPLEXITY.md` | **SUPPORTED** as to authorship and influence on the plan; Perplexity's own claims are checked row by row there, not adopted |
| Amos Tipton's public A/B recovery question prompted the A/B recovery challenge | his original public question, preserved verbatim in `docs/external/amos-tipton_2026-10-02_ab-recovery-question.md`; A/B preregistration `7fb1c48`; A/B results `8e31454` | **SUPPORTED**, as to the challenge question only. He did not design the experiment, predictions, harness or results; those are this project's. The claim implies no endorsement, validation or independent verification by him or HYBRID WAYSS. V15 (`eaacb55`) later formalized and extended the same challenge (`docs/V15_RECOVERY_RESULTS.md`); that is not a separate influence claim. Follow-up (2026-10-03): after opening the linked material, he reviewed the attribution and experiment history and described his contribution as a documentation review; he has not re-run the harness. **SUPPORTED — external documentation review / attribution acknowledgment** (correspondence relayed by Chad Holland; attributed paraphrase in `docs/V15_RECOVERY_RESULTS.md`, "Documentation review by Amos Tipton"). Not independent verification, reproduction or validation of the A/B result, and not an endorsement of Sovereign Veritas or of V15. |
| Sougata Roy shaped XB-1 | the XB-1 PREREG once named "Davorin / Sougata" | **NOT SUPPORTED** — corrected in `docs/EXECUTION_BOUNDARY_RESULTS.md`; his authorized-vs-justified feedback is separate and not yet the basis of any experiment here |
| James Greenwood's audit (2026-10-03, with Gemini) found the five input-handling defects fixed in JG-1 | his report, verbatim with sha256, in `docs/external/greenwood_2026-10-03_challenge-and-audit-report.md`; the JG-1 registration (`8a1f06e`) reproduces each finding on unmodified `main` before any fix | **SUPPORTED**, for the five findings only. The report is AI-assisted (Gemini). The fixes, predictions and probe are this project's. No endorsement or validation by him, Gemini or Google is implied |

## Outbound: systems this work is claimed to have shaped

None recorded. A row is added only with evidence from the table above, and the default status of a claim
without evidence is INDETERMINATE, not SUPPORTED.

| Claim | Evidence | Status |
|---|---|---|
| — | — | — |
