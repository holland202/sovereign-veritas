# JG-1: five input-handling defects reported by James Greenwood — registration

**Status:** REGISTERED 2026-10-03, in a commit of its own. No fix or harness exists yet. This file is
not edited after this commit; results go in `docs/JG1_RESULTS.md`.

**Method:** principia-artificialis `METHOD.md` at `646eed7`, which is SWAY Amendment 3.

**Credit:** Denzil "James" Greenwood found and reported the five defects, working with Gemini (Google;
version not recorded). His report is preserved verbatim in
`docs/external/greenwood_2026-10-03_challenge-and-audit-report.md` (sha256 of the `.docx`:
`57c09a3c…`). The credit is for the findings. The design, the predictions, the fixes and this text are
this project's. Nothing here implies endorsement or validation by him, Gemini or Google.

**Provenance:** AI participation → human validation → human editing/curation → human responsibility.
- **AI participation:** Claude (Anthropic, Opus 5.5) reproduced the findings and wrote this
  registration.
- **Human review:** direction only (Chad Holland).
- **Responsibility:** Chad Holland.
- **Self-tested.**

## Question

For each reported behaviour, does a fail-closed fix remove it while leaving every existing behaviour
and the Gate's conformance unchanged?

## What was observed before this registration (exploratory; these are retrodictions, not predictions)

These were run on 2026-10-03 against the unmodified `main` (`4eda7d4`), in a container on Linux with
Python 3.13. The output is pasted:

```
JG1 branch_factor: critical 0 | CRITICAL 4 | bogus 4 | None 4 | budget EXHAUSTED 4
JG2 governor on unregistered: returned None | recorded decision ALLOW | records 1 | registry has it: None
JG3 AssessedEvidenceState(state='supported', assessed_by=None): CREATED, state='supported'
JG3 AssessedEvidenceState(state='SUPPORTED', assessed_by=None): REFUSED AttributeError: 'str' object has no attribute 'value'
JG3 AssessedEvidenceState(state=<EvidenceState.SUPPORTED: 'SUPPORTED'>, assessed_by=None): REFUSED ValueError: EvidenceState.SUPPORTED requires assessed_by to be non-empty
JG4 AssessedDomainReview(REVIEWED, reviewed_by=None): CREATED
JG5 coverage_target=None: quality 0.5
JG5 coverage_target=0.9: quality 0.7
JG5 coverage_target=True: quality 0.7
JG5 coverage_target=1: quality 0.7
JG5 coverage_target='0.9': quality 0.7
ours: interval (-inf, inf) quality 0.7 | nonconformity inf quality 0.6
```

**Findings, attributed:**

| # | Reported by James Greenwood | Reproduced here | Found here (ours) |
|---|---|---|---|
| J1 | `ResourcePolicy.branch_factor`: an uppercase, unknown or `None` status returns the full search breadth (4) | yes | `"hot"`, a status in `evidence_states.py`'s own vocabulary, also returns 4; budget `"EXHAUSTED"` returns 4 |
| J2 | `CapabilityGovernor.authorize` records `ALLOW` for a capability that was never registered | yes. The registry is unchanged, so the record contradicts what happened | — |
| J3 | `AssessedEvidenceState`: lowercase `"supported"` gets past the `assessed_by` requirement | yes | a plain `"SUPPORTED"` string is refused only by accident: an `AttributeError` while formatting the error message |
| J4 | `AssessedDomainReview`: `REVIEWED` is accepted without `reviewed_by` | yes | — |
| J5 | `normalize_uncertainty`: `coverage_target=True` raises quality from 0.5 to 0.7 | yes | strings (`"0.9"`) also earn credit; infinite intervals and infinite `nonconformity` are scored as finite (the comment says "finite"; the check is NaN-only) |

**Where they sit:**
- None of the five is on the Gate's decision path. The kernel and the verifier conform on 4,690
  vectors (digest `44823d0f…`, unchanged; Greenwood's Windows run printed the same digest).
- `ResourcePolicy`, `CapabilityGovernor` and `normalize_uncertainty` are exported from the package.
- The two `Assessed*` classes are neither exported nor used anywhere in the repository. Their defects
  are reachable only by an outside caller.

## Simplest rival

**"Outside the contract: the type hints say enum or float, so the callers are wrong, not the code."**
This is tested by P6 below (the existing tests and callers keep working). It does not excuse the
behaviour:
- Python does not enforce the hints;
- `EvidenceState` is a `str` enum, so plain strings look valid;
- the method's fail-closed rule (principia `CONTROLS.md` C-BUILD, "missing means deny") applies to any
  input that returns a verdict-like value.

## Fixes (design, frozen here)

- **F1 `branch_factor`:**
  - Exact match against the vocabulary of `evidence_states.py`.
  - Thermal: `critical`, `unsafe` and `unavailable` → 0; `warning`, `high` and `hot` → constrained;
    `normal` and `cool` → normal.
  - Budget: `exhausted` and `unavailable` → 0; `constrained` and `low` → constrained; `available` →
    normal.
  - Anything else (another case, an unknown word, `None`, a non-string) → **0**.
  - The result is the minimum over the two inputs.
- **F2 `CapabilityGovernor.authorize`:**
  - If the name is not registered, it records `decision="REFUSE"` with
    `verification={"status": "FAIL", …}` and the reason "capability not registered", and returns
    `(None, record)`. The registry is untouched.
  - The registered path is unchanged.
- **F3 `AssessedEvidenceState`:**
  - `state` is coerced to `EvidenceState`. An unknown value raises `ValueError`.
  - For SUPPORTED, NOT_SUPPORTED and REFUTED, `assessed_by` must be a non-empty string.
- **F4 `AssessedDomainReview`:**
  - `status` is coerced to `DomainReviewStatus`. An unknown value raises `ValueError`.
  - REVIEWED requires a non-empty string `reviewed_by`.
- **F5 `normalize_uncertainty`:**
  - Credit goes only to real numbers (`int` or `float`, never `bool` or `str`) that are finite
    (`math.isfinite`).
  - `coverage_target` must be in (0, 1].
  - The structure of the returned dictionary is unchanged.

## Predictions (about the fixed code)

| ID | Prediction |
|---|---|
| P1 | `branch_factor` returns 0 for `("CRITICAL","available")`, `("bogus","available")`, `(None,None)`, `("normal","EXHAUSTED")`, `(5,"available")` and `("normal","normal")` (an unknown budget). It returns 2 for `warning`, `high` and `hot` with `available`, and 4 for `normal` and `cool` with `available`. `("critical","available")` returns 0 |
| P2 | `authorize("never_registered")` returns `(None, r)` with `r.decision == "REFUSE"` and `r.verification["status"] == "FAIL"`; the sink holds one record; the registry still lacks the name. A registered capability is still authorized, with `decision == "ALLOW"` |
| P3 | `state="supported"` raises `ValueError`. `state="SUPPORTED"` without `assessed_by` raises `ValueError`, not `AttributeError`. `state="SUPPORTED", assessed_by="x"` constructs, with `.state is EvidenceState.SUPPORTED`. `UNVERIFIED` without `assessed_by` constructs |
| P4 | `REVIEWED` without `reviewed_by` raises `ValueError`. The string `"REVIEWED"` with `reviewed_by="x"` constructs, with `.status is DomainReviewStatus.REVIEWED`. `NOT_REVIEWED` without a reviewer constructs. An unknown status raises `ValueError` |
| P5 | Quality, exactly: `coverage_target=True` → 0.5; `"0.9"` → 0.5; `0.9` → 0.7; `1` → 0.7; `1.5` → 0.5. `interval=(-inf, inf)` → 0.5; `(1.0, 5.0)` → 0.7. `nonconformity=inf` → 0.5; `nan` → 0.5; `True` → 0.5; `0.12` → 0.6 |
| P6 | Every existing test passes unmodified (450 passed, 1 skipped, before the new tests are added). The kernel and the verifier conform with digest `44823d0ff707213ae8bc310ed8b21e135f8e742fd8834e8f9474743d3a250628` |
| P7 | **Anti-vacuity:** `python tools/jg1_probe.py --sabotage` swaps each of the five fixed functions for a shim that reproduces its pre-fix behaviour. P1–P5 are then each REFUTED, and the probe exits 1 |

The probe (`tools/jg1_probe.py`) imports the real functions. It prints one HELD or REFUTED line per
prediction, a `VERDICT` line and a `DIGEST`, and is then pinned per WORKFLOW W4.

## Trigger table (METHOD.md §3)

| Trigger | Answer |
|---|---|
| Feasibility | No. All the cases are constructed |
| Noise | No. Deterministic |
| Statistics | No |
| Evidence | **No.** These are input-validation questions about assessment records, not about freshness or source; the ladder does not apply |
| Independence | **Yes** (C-INDEP). Greenwood's report re-ran this repository's tools on Windows: a re-run by another person, AI-assisted. Our reproduction of his five findings is ours, and is self-tested. Neither is independent validation of the fixes |
| External | **Yes** (C-EXT). The report is preserved verbatim with sha256; permission was given; his factual claims are checked above (section 5) and are not yet checked (section 6) |
| Device | No. Container only; NOT VALIDATED on the S25 |
| Verdict code | **Yes** (C-BUILD). This is exactly the "missing means deny" rule |
| Exploration | **Yes** (C-EXPLORE). The pre-fix outputs were seen before registration (listed above as retrodictions). P1–P7 concern code not yet written |
| Method comparison | No |

## Limits

- Five components outside the Gate path. Nothing here changes `CONTRACT.md` or the Gate.
- `CapabilityGovernor.revoke` on an unregistered name still records `REFUSE` for a revocation that did
  nothing. That is the fail-closed direction, and it is left as a door.
- Section 6 of the report is not checked here.

## Next unrun test

Check section 6 of Greenwood's report line by line. In particular: does every evidence record go
through `canonical_json`, and is signature verification actually required on every consumer path?
