# IM registration: sovereign-veritas against draft-krausz-verification-state-03 (nothing run under this registration)

Status: registration only. Written 2026-10-04, before `tools/ietf_map.py` exists. Baseline main 2c825b8.
Claude-assisted (Claude Opus 5.5). Chad Holland gave direction. He has not
reviewed this text line by line.

## Source and its standing
The draft is "The verification.* Constraint Family: Pre-Action Fail-Closed Gates for AI Agent Decisions", J. Krausz
(TK Collective LLC), 1 October 2026: https://www.ietf.org/archive/id/draft-krausz-verification-state-03.html. It is
an **individual Internet-Draft, intended status Informational**. It is not an IETF standard or a working-group
document. It was brought to this project by another AI's research summary on 2026-10-04. The requirements below were
read from the draft through a fetch tool and quoted from it. They have not been checked against the draft by a
person.

## What this measures
For each mappable requirement, the probe runs this repository's code on a concrete case and records CONFORMS,
DIFFERS, or NOT COVERED (the draft's normative text does not reach the case, but its stated principle does). The
"relying party" is mapped to `tools/consumer.py accept` with the published witness log, and the verifier is
`tools/verify_package.py`. Packages, keys and the witness log are the published ones in `evidence/`, `keys/` and
`witness/`. The draft's receipts are JWS/JWT. Ours are JSON packages with optional SSH signatures. Wire formats are
not compared.

## Requirements, cases, predictions
| ID | Draft requirement (quoted or closely paraphrased) | Case | Predicted |
|---|---|---|---|
| M1 | 6.3: a missing receipt MUST be treated as halt | consumer on a file that does not exist | CONFORMS: exit 2, not accepted (0.95) |
| M2 | 6.3: a malformed receipt MUST be treated as halt | consumer on a package with broken JSON | CONFORMS: exit 2 (0.9) |
| M3 | 6.3 / 7.2: an expired or stale receipt MUST be treated as halt | consumer, witness log given, a package 2 entries behind the latest | CONFORMS: exit 1 (0.9) |
| M4 | 6.3: a signature-invalid receipt MUST be treated as halt | consumer with another package's signature | CONFORMS: exit 1 (0.9) |
| M5 | 5.1 / 6.3: receipts are signed, and one that cannot be verified halts | consumer on the latest package with **no signature supplied** | **DIFFERS: exit 0, accepted** (0.9) |
| M6 | 5.2: receipts MUST bind to a content-addressed decision mapping (`v_gate_mapping_hash`); absence is malformed and halts | does a package carry the Gate's contract digest or any rule-version hash? | **DIFFERS: absent** (0.9) |
| M7 | 6.1: only `verified` (plus conditions) acts; `indeterminate` and `not_evaluated` halt | Gate with INSUFFICIENT_EVIDENCE, a missing status, and an unknown status | CONFORMS: DEFER, REFUSE, REFUSE, so nothing executes (0.9) |
| M8 | 6.1: an un-probed adversarial state is not `resilient` and halts | Gate with PASS and no adversarial check at all | **DIFFERS: ALLOW** (0.9) |
| M9 | 6.3 principle, "anything ambiguous halts"; the normative text names error conditions only | Gate with runtime fields left at their defaults (nobody supplied them) | **NOT COVERED by normative text, contrary to the principle: ALLOW** (0.9) |
| M10a | 11.1: an environment HALT MUST NOT be masked by a verification ACT | Gate with PASS and an unhealthy runtime | CONFORMS: DEFER (0.9) |
| M10b | 4.2: environment constraints MUST be evaluated before verification | Gate with REFUTED and an unhealthy runtime: which reason comes first? | **DIFFERS in order: verification is evaluated first**; the outcome still halts (0.85) |
| M11 | 3.1: distinguish an instrument failure from an evaluated result | verifier on malformed JSON compared with a tampered decision | CONFORMS: exit 2 COULD NOT LOOK compared with exit 1 (0.85) |
| M12 | 5.4: a relying party recomputes the gate decision locally | verifier on a genuine package | CONFORMS: `gate_replay` passes (0.95) |
| M13 | (beyond the draft, which specifies no nonce or jti replay protection) | consumer accepts the same package twice | SV goes further: the second is refused, exit 1 (0.85) |

**Anti-vacuity:** `--sabotage` supplies the genuine signature in M5. M5 then conforms, its prediction fails, and the
probe exits 1. That shows the probe can report CONFORMS where DIFFERS was predicted.

## What it cannot show
- Wire-format conformance (JWS, JWKS, `kid`, the `evidence_set` members). Our format is different by design.
- Calibration anchors (section 8). SV has no probabilistic confidence threshold of that kind.
- Whether the draft is right, or whether conforming to it is a goal. It is one author's informational draft.
- Container only. NOT VALIDATED on the S25.
