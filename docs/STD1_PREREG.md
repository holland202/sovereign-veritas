# STD-1 — agent-authorization standards at the action boundary: registration

Status: **REGISTERED, nothing run.** This file is committed alone, before any probe exists and before any
outside suite has been run here.

Drafted by Claude (Opus 5.5) at Chad Holland's direction. Chad has not reviewed it line by line.

## Question

Two parts, kept apart:

1. **Reading (not an experiment).** For eight scenarios at the action boundary, what do two IETF
   Internet-Drafts say should happen? Each answer is SPECIFIED (with the section), UNDERSPECIFIED (the text
   lets two reasonable implementations differ), or NOT ADDRESSED.
2. **Experiment.** The OpenA2A Agent Authorization Protocol (AAP) ships a conformance suite whose README
   claims: "Each negative fixture is valid in every respect except the one defect it pins, so a verifier that
   skips that verification step (and only that step) wrongly ACCEPTs it." That claim can be tested by
   removing verification steps from its reference verifier one at a time and seeing which removals some fixture
   catches. Here Sovereign Veritas is not the thing measured; its method is the instrument.

Nothing will be filed with anyone on the strength of this file. Whether any result is worth reporting upstream
is decided after the results, by Chad Holland.

## What was read before this registration (exploratory)

- `draft-klrc-aiagent-auth-03` (Kasselman et al., Informational, 6 July 2026), sections 10–14, read in full;
  grep of the whole text for idempotency, replay, retry, revocation, expiry, nonce, jti, duplicate.
- `draft-fane-opena2a-aap-02` (Fane, Standards Track, 30 September 2026), sections 7.1 and 8, read in full;
  section list.
- `draft-liu-agent-operation-authorization-02`: section list and the same grep only.
- `opena2a-standards/aap-conformance` at `95580cd`: README in full; the docstring (lines 1–80) of
  `verifiers/python/verify.py`; a count of `_reject(` call sites by category (grep); the file names in
  `fixtures/`; the head of `fixtures/cgt-compact-replayed.json`. **No verifier, fixture generator or test was
  run.**

## Part 1 — reading table (C-EXPLORE; claims about documents, not measurements)

| # | Scenario | klrc-03 | AAP-02 |
|---|---|---|---|
| 1 | authorization granted → action occurs | SPECIFIED by reference (OAuth access token; §10.2–10.3) | SPECIFIED (CGT; §4, broker default-deny §8.4) |
| 2 | authorization revoked before execution | UNDERSPECIFIED: §11 "MUST ensure that revoked or downgraded authorization is enforced without undue delay"; "undue delay" is not bounded, and a self-validated JWT is not re-checked until a signal arrives | SPECIFIED with a bound: §7.1 federation revocation within 60 s; local grant revocation list checked at every resolution. §7.1 itself: "As of the date of this revision no known implementation maintains such a list" |
| 3 | authorization expires → action doesn't occur | SPECIFIED by reference (`exp`) | SPECIFIED (`exp`; fixture `cgt-compact-expired`) |
| 4 | response lost after the effect → retry | NOT ADDRESSED | NOT ADDRESSED at the effect level. §8.1 rejects the same token twice, so a retry with the same token is refused, and the agent learns nothing about whether the first attempt ran; a retry under a freshly minted grant is a new `jti` |
| 5 | fresh request ID → still bound to the original intent? | NOT ADDRESSED. §10.5 transaction tokens bind to "a specific transaction", identified by the issuer, not to an intent that survives a new transaction | NOT ADDRESSED. Replay is keyed on `jti` (§8.1), one per token, not per intended effect |
| 6 | duplicate request → one effect or two? | UNDERSPECIFIED: §9.2.3 says implementations "MUST consider the risk of message relay or replay"; the mitigations ("nonce or unique identifier checks") are what deployments "typically" do, not a requirement | SPECIFIED for the token: §8.1 "MUST reject a repeated identifier" within the TTL. Says nothing about the effect |
| 7 | authorization names one operation → agent performs another | SPECIFIED where transaction tokens are used (§10.5: a transaction token "cannot be used ... with modified transaction details"); otherwise left to resource-server policy (§10.3) | SPECIFIED for `authorization_details` with `aap_crit` (§4.4–4.5, §8.7) |
| 8 | authorization record exists → downstream effect differs | NOT ADDRESSED. §11 audit MUST record "action requested and authorization decision", not the outcome | NOT ADDRESSED. §8.5 the broker "performs the operation, and returns only the result"; no requirement to record or check the effect |

Reading summary: scenarios 4, 5 and 8 (the ones Sovereign Veritas measured as RK-1, RK-2 and OBS-1) are
not addressed by either draft. This is the same gap raised against OWASP ACS in its issue #200. It is a reading,
by the same author who wrote those experiments, and it is not evidence that any implementation fails.

## Part 2 — predictions (AAP conformance suite at `95580cd`)

| ID | Prediction |
|---|---|
| P1 | Reproduction. `python3 verifiers/python/verify.py fixtures` prints `summary: 43 pass, 0 fail (43 fixtures)` and exits 0. `node verifiers/node/verify.mjs fixtures` (after `npm install`) prints the same summary. |
| P2 | Instrument control. Our mutation harness, run with no mutation, reports 0 failing fixtures; with the signature check removed (the single `BAD_SIGNATURE` site made a no-op) it reports `cgt-compact-bad-signature` failing. If either is false the harness is broken and P3 is not judged. |
| P3 | Mutation. Each `_reject(...)` call site in `verifiers/python/verify.py` is made a no-op in turn (54 sites by grep; the harness prints the exact count). A mutant is **killed** if any fixture's expected verdict or category is then not met, or the verifier exits non-zero for any other reason (counted separately as killed-by-crash). Prediction: **at least one mutant survives, and every survivor sits in code for a rule the README lists as "implemented ... not pinned"** (§5.4 member kinds and §4.4.1 entry types no fixture exercises, and the §4.5 producer rule). A survivor outside that list refutes P3 and is the finding this experiment exists for. |
| P4 | Parity. For every mutant, the set of failing fixtures is reported, so a reader can see which fixture kills which site. Prediction: no single fixture kills more than half of all killed sites (the suite is not one fixture doing the work). |

## Controls and limits, stated now

- **Mutation by no-op only.** Checks written as something other than a `_reject(...)` call (a `return False`, a
  branch that skips work) are not mutated. Survivors are therefore a lower bound on unpinned checks.
- **Python verifier only** for P3/P4. The Node verifier is reproduced (P1) but not mutated.
- **Container only** (Linux x86_64). Not run on the S25.
- **What this cannot show:** whether AAP prevents a second effect. The suite tests token wire form, by its own
  statement; scenarios 4, 5 and 8 sit outside it.
- Self-tested: the same author writes the harness and judges it.

## Next unrun test

Run the same mutation harness against the Node verifier and compare the survivor sets. A site that survives in
one verifier and is killed in the other would mean the two reference verifiers disagree about what is pinned.
