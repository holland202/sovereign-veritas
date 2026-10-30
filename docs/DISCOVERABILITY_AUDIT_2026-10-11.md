# Sovereign Veritas — public search discoverability audit

**Date:** 2026-10-11. **Type:** documentation / discoverability, not a claim of scientific validation or SEO success.
**Project status:** maintenance-only since v0.2.0; not production-ready or independently security-validated. This document makes no change to code, contract, results or release tags.

## Baseline observations

- The public README already leads with maintenance-only limitations and directly describes a permission gate for AI-driven actions, ALLOW / DEFER / REFUSE, an offline verifier, conformance vectors, and known negative results. These are the authoritative source descriptions.
- A public web search surfaced related `holland202` repositories (notably SKN-V1, SLC v12 and Principia Artificialis) through search results and GitHub topic pages. This is **not** a controlled Google-ranking study.
- Sovereign Veritas did not reliably appear in the small, sampled broad-site web searches run for this audit. This is an **observational gap**, not proof that Google's index excludes it. Search engine, regional, personalization, indexing delay, and query effects are unknown.
- No verified Google Search Console ownership, query impression counts, click-through rates, indexed coverage, or rank measurements were available. Do not claim improvement until independently measured.

## Documentation-only change proposed

- Add a short human-readable phrase near the README introduction: **AI agent governance**, **fail-closed action authorization**, **evidence-bound AI actions**, and **deterministic verification of recorded decisions**, each explicitly limited to the documented prototype.
- Add links to related, *independent* repositories, so a public reader can discover the research family without assuming those systems are integrated, deployed, or validated together.
- Retain the existing critical negative results, status warning, demos and source hashes; **do not replace honest limits with marketing promises.**
- Keep this work in a reviewable draft PR unless the maintenance-only change policy is deliberately reconsidered.

## GitHub About text — suggested, NOT automatically applied

Suggested repository description (under 350 characters):

> Experimental, fail-closed AI agent governance: evidence-bound action authorization, capability and policy checks, and deterministic offline verification of recorded decisions. Research prototype; not production-ready.

Suggested topic keywords (pick only accurate, relevant terms rather than keyword stuffing):

`ai-governance`, `ai-safety`, `ai-agents`, `agent-security`, `authorization`, `policy-as-code`, `deterministic-verification`, `audit-log`.

**The GitHub connector used for this audit can edit files and open PRs, but does not expose a repository-description/topics write action.** The above metadata suggestions are not applied.

## Measurement plan (not executed)

1. Check public, logged-out results for several named and broad terms: `"Sovereign Veritas" holland202`, `"fail-closed" "AI agent" authorization`, `"evidence-bound" "AI governance"`, `site:github.com/holland202/sovereign-veritas`.
2. Save date, query, search engine, result URL, observed rank or "not within checked window", locale and device. Do not treat other search providers' results as Google placement.
3. If Chad verifies a public website property in Search Console, collect indexed coverage, clicks, impressions and queries over a sufficiently long window; never infer causality from a single before/after result.
4. Keep a comparison arm: a no-edit project or an unchanged keyword group. SEO measurements are confounded by indexing and time; no effectiveness claim is preregistered.

## Scientific and provenance boundary

These discoverability edits change explanatory text, **not** the Gate's behavior, the authority of an LLM, the truth of recorded external state or the status of open security defects. Verified GitHub changes do not imply search indexing or external adoption.

Authorship: prepared by ChatGPT at Chad Holland's request. Any metadata changes or merging still require their own GitHub actions.
