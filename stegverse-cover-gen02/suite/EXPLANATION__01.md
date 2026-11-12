# SOVEREIGN VERITAS — WHAT IT DEMONSTRABLY DOES, THEN THE COVERING

StegVerse Build Lane, 2026-11-12. ProjectID LINKEDIN-SOVEREIGN-VERITAS-EVAL.
Abilities first, in the subject's own published terms; the covering second;
the subject's core is unmodified throughout.

## What Sovereign Veritas demonstrably does (EVIDENCED, reproduced)

Every item below was executed by a non-author on 2026-11-12 from the public
checkout (holland202/sovereign-veritas); the full outputs are carried in this
suite as INDEPENDENT__REPRODUCTION__01.

- **A fail-closed permission Gate with a published contract** (`sv.gate/0`):
  thirteen ordered rules producing ALLOW / DEFER / REFUSE, first-match,
  monotone toward refusal; sealed evidence packages an independent verifier
  checks by RECOMPUTING the decision from recorded inputs (gate_replay).
  A policy edited after sealing fails package_digest; an authorization
  revoked and the digests resealed still fails gate_replay (demo cases 2–3).
  Demo: DEMO PASS.
- **A published decision-vector conformance contract**: 4,690 vectors ship in
  the repository as the conformance corpus for the Gate's decision surface.
- **Execution-boundary self-knowledge, preregistered and reproduced**: the
  XB-1 probe's eight cases land exactly as registered (8 of 8). Sequential
  duplicate record_ids are refused BEFORE execution (X1–X3, closed by the
  project's own fix); the executor runs exactly the frozen decided action
  (SV-FIX-001 F1).
- **Opt-in idempotency reservations (RK-2/RK-3)** of production quality:
  reserve-before-effect under per-key OS locks, holder tokens, late-holder
  events, and honest UNKNOWN semantics — an executor failure under a key is
  recorded UNKNOWN and held for a person, never relabeled FAILED or silently
  retried. Boundary-relevant tests: 33/33.
- **An observed-effect checker (EO-2)** that compares a record against a
  before/after observation of the target's state and returns a verdict
  vocabulary (OK / UNAUTHORIZED_EFFECT / NO_EFFECT / WRONG_EFFECT /
  EFFECT_DESPITE_FAILURE / BINDING_MISMATCH) — the machinery the covering
  reuses for its attestations.
- **A stated-limits discipline rare in any codebase**: failures published
  first, claims graded, refuted notes kept. The covering below exists because
  the project's own documents name, precisely, what remains open.

## What remains open — in the project's own words

- XB-1 X4 (concurrent duplicate record_id → two effects): "OPEN — needs an
  atomic reservation."
- XB-1 X5 (effect lands, record write fails → one effect, zero records):
  "OPEN — needs a durable intent before the effect, plus a way to learn
  what happened." The world changed and the evidence chain does not know.
- Sinks without `has_record` get no pre-check, by choice: the repository's
  own regression test asserts the unguarded duplicate produces 2 effects.
- RK-1/EO-1: the evidence record reports the workflow's account of the
  execution (SUCCEEDED = the executor returned without raising). EO-2's
  observation check exists but is opt-in — "nothing in the workflow or
  package calls it" — and the package verifier does not require effect
  evidence: EO-1's construction (executor ran under a broken guard; the
  record says no execution) verifies CONSISTENT. RK-3 names the direction:
  a fence "checked by the action's target" (OBS-1).
- One author for kernel and verifier alike: no non-author implementation or
  executed reproduction existed before this suite.

## The covering (this suite; unmodified core, his idiom)

The diagnosis the covering is built on: the remaining gaps are not defects
in the Gate, the ledger, or any component — they are what a
decide → execute → record sequence cannot express. In that sequence the
record is an account written after the act, and every open case lives in a
gap between the three steps. The StegVerse grammar has no such sequence:
an action is a manifest-bound state transition, and the disposition is the
receipted transition — decision, act, and record are one object, so the
gaps have no surface to open on. The covering gives Sovereign Veritas that
form around its unmodified core:

- **transition_ledger.py** — a hash-chained append-only ledger of
  transitions. INTENT is written durably BEFORE any effect, one per
  record_id ever, the duplicate refused atomically under an OS lock —
  for every caller, with no idempotency key and no sink cooperation
  (closes X4 and the has_record-less configuration). COMPLETION carries
  the effected side's attestation. UNKNOWN holds a failed transition open
  for a person. An INTENT with neither is an OPEN transition: enumerable,
  never silence (closes X5's "the chain does not know").
- **guarded_workflow.py** — two proxies around EvidenceWorkflow, swapped
  in for one run and restored after. The executor proxy writes the INTENT
  before delegating (the workflow calls execute() only on ALLOW, with the
  frozen decided action), then reads back the target's state through a
  probe that does not go through the executor and computes the EO-2
  verdict at completion time. The sink proxy appends the COMPLETION
  BEFORE the evidence record is delegated, so a failing record write
  leaves the completion standing and nameable.
- **verify_transition.py** — an offline verifier sharing no code with the
  writer path beyond the published formats. It checks the PAIR (V1–V6):
  chain integrity; no duplicate INTENT; every SUCCEEDED claim backed by a
  COMPLETION whose EO-2 verdict recomputes and attests; every COMPLETION
  matched by its evidence record (a lone completion is NAMED, X5's
  asymmetry made visible); no COMPLETION standing behind a record that
  claims no execution (EO-1's construction FAILS here); open and UNKNOWN
  transitions listed, never counted as success.

## Covering results (executed, carried in this suite)

run_cover_tests.py — COVER VERDICT PASS, 7/7 as registered: anti-vacuity
(2 effects, pair CONSISTENT); duplicate refused with a has_record-less sink
(1 effect, where the unguarded configuration gives 2); the X4 race (exactly
1 effect); X5 (completion stands, the verifier names the asymmetry); the
EO-1 construction (pair mismatch FAILS V5); an unattested SUCCEEDED claim
(FAILS V3); executor failure (UNKNOWN held, retry refused before the
executor is reached).

## What the covering does not do

It does not make the record prove the world. A completion attests that an
observer read back the target's state and the EO-2 verdict recomputed —
proof of the crossing as recorded, not of payload truth in the world; an
observer the executor can write to defeats it (EO-2 P5, the project's own
caveat, inherited unchanged). Authenticity is NOT_PROVEN: nothing here is
signed. Production hardening beyond the covered boundary (key custody,
observer independence in deployment, the project's own S25 validation) is
the subject's establishment to make — the slots are named in ASSESSMENT__01.

## Running it

From a Sovereign Veritas checkout, with this suite's files importable:

    PYTHONPATH=<sovereign-veritas>:<suite dir> python3 run_cover_tests.py
    PYTHONPATH=<sovereign-veritas>:<suite dir> python3 -m sv_transition_cover.verify_transition <ledger.jsonl> <records.json>
