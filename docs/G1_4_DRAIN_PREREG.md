# G1-4 drain registration: where should a session budget live? (nothing built or run)

Status: registration only. Written 2026-10-03 before `tools/g1_4_drain_probe.py` exists. Claude-assisted
(Claude Opus 5.5); Chad delegated the choice of next step and has not reviewed this.

## Why this comes before building G1-4
docs/SV_GATE_1_SCOPE.md says G1-4 is "checked at the gate" and that a "drain" attack class must be added
before the rule is built. Reading the code (disclosed, C-EXPLORE) shows a design fork the scope doc does not settle:
- `Gate.evaluate` is a pure function of one request. It has no memory across requests.
- A package's `provenance.chain` holds one session: a `session-start` record and the action record.
- `tools/consumer.py` (G1-3) is the only component that keeps state across packages.
So "a cumulative limit per session and per target" has to come from somewhere outside today's Gate.

## Arms (each is a prototype inside the probe, not a kernel change)
- **G0 (rival, M14): sv.gate/0 as it is.** The real `Gate`, no budget.
- **A: consumer-side budget.** The consumer keeps counts per session and per target (like G1-3's consumed set). Not recomputable by the stateless verifier.
- **B: gate-side budget from the recorded session chain.** The count so far in this session is read from the chain the request carries, so the verifier could recompute it. Knows nothing outside that session.
- **AB: both.**

Budget in every cell: at most 5 accepted actions per session and 5 per target. Each request is individually ALLOWed by the real Gate.

## Threat model (assumption, stated)
The requester can ask for actions and, in K2, can open a new session per request. It cannot forge a chain the
runtime built (signatures and digests are out of scope here; the existing verifier covers them).

## Cells and registered accepted-counts
| cell | what | G0 | A | B | AB |
|---|---|---|---|---|---|
| K0 | control: 4 requests, one session, one target, one consumer | 4 | 4 | 4 | 4 |
| K1 | drain: 10 requests, one session, one target, one consumer | 10 | 5 | 5 | 5 |
| K2 | session-split: 10 requests, a new session each, one target, one consumer | 10 | 5 | 10 | 5 |
| K3 | consumer-split: 10 requests, one session, one target, alternating between 2 consumers | 10 | 10 | 5 | 5 |

## Predictions
- **D1 (anti-vacuity, M3):** K0 is 4 in all arms. A budget that refuses under-budget traffic is broken, not safe.
- **D2:** G0 accepts 10 in K1, K2, K3 (sv.gate/0 has no budget; the drain succeeds).
- **D3:** A fails K3 (10): a per-consumer count is split by using two consumers.
- **D4:** B fails K2 (10): a per-session count is split by opening sessions.
- **D5:** only AB holds all four cells at the registered values.
- **D6:** every cell is deterministic (two runs identical).
Confidence: high (about 0.9) for D1, D2, D6; these follow from the code. D3-D5 are about my own prototypes,
so they mostly test that the prototypes do what I meant (M10: nothing certifies itself).

## What this cannot show
Prototypes are not the built rule. Nothing here changes CONTRACT.md, the vectors or the Go port. A shared
budget across consumers (what AB needs in practice) requires shared state, which this repo does not have; the
probe gives AB a shared counter and that is an assumption, not a mechanism.

## Door (M15)
If D5 holds, the next registration is the real G1-4: which state store, how the verifier sees it, and the
contract-first sequence (CONTRACT.md, vectors, Python, Go port). Not registered yet.
