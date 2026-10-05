# AMB-1 — How much of the Gate do the 4,690 contract vectors pin down? Registration

**Status:** REGISTRATION. Committed before `tools/amb1_probe.py` exists. Nothing built or run at this commit
except the feasibility counts below and the disclosed exploratory run.
**Date:** 2026-10-05. **Base:** `main` at `9e87f41`.
**Direction:** Chad Holland, 2026-10-05, after reading summaries of the exploratory run below.

## Question

"4,690 of 4,690 vectors" is SV's conformance claim for a second Gate implementation. How many *different*
programs also pass all 4,690, and how unsafely can they behave on inputs the vectors do not contain? And can a
loop that turns impostor-vs-Gate disagreements into new vectors close that gap?

## Origin and an exploratory run (disclosed, not evidence)

The question came out of a session in which Chad collected proposals from several AI systems (ChatGPT,
Perplexity, Gemini, Grok, Copilot, Google AI) and asked Claude to combine them; the impostor framing is
Claude's, related ideas are credited in the Principia note on the "Ambiguity Engine". Before this registration
Claude ran an informal version with scikit-learn decision trees (not committed): round 0, five impostors that
fit every vector said ALLOW where the Gate did not on up to 24.69% of 10,000 recombined inputs; after 460 added
vectors, 0.05%. **The thresholds in A2 and A3 were chosen after seeing that run.** This registration replaces
scikit-learn with a seeded pure-Python learner (below) so CI reproduces the outcome on every platform; its
numbers have not been seen.

## What the code can express (read before registering)

- `tools/gate_contract.py`: `kernel_gate()` and `verifier_gate()` each map a vector `input` to
  `(decision, reasons)`; `read_vectors()` loads `contract/gate_vectors.jsonl`.
- A vector input is nested JSON; flattened, it has 43 leaf paths and 158 (path, value) pairs including a
  `<missing>` value per path.
- Only 15 of 4,690 vectors expect ALLOW; 59 DEFER; 4,616 REFUSE.

## Feasibility (run before registering)

```
vectors 4690 distinct feature rows 4676 conflicting 0
decisions Counter({'REFUSE': 4616, 'DEFER': 59, 'ALLOW': 15})
leaf paths 43 one-hot features 158
kernel gate 12297 calls/s
```

## Design

- **Features:** one-hot over (leaf path, JSON value), values taken from the vectors, plus `<missing>`.
- **Impostor learner (stdlib only):** a decision tree grown on the current vector set. At each impure node,
  the split feature is chosen by `random.Random(seed)` among the features that separate the node's rows;
  leaves predict the majority decision (ties: REFUSE > DEFER > ALLOW). It fits every vector exactly (no
  conflicts exist). Five impostors, seeds 0-4.
- **Recombined inputs:** take a vector chosen by `random.Random(1)`, overwrite 2, 3 or 4 leaf paths with
  values observed at that path in the vectors. Pool S (search) and pool H (held out), 10,000 each, drawn in
  that order from the same RNG. Every input uses only values the contract already contains.
- **Truth:** `kernel_gate()` on every input. A raise counts as its own outcome, never a decision.
- **Loop:** 8 rounds. Each round: grow 5 impostors on the current vectors; count on H the inputs where an
  impostor says ALLOW and the Gate does not ("unsafe ALLOW"); then take up to 100 not-yet-used inputs from S
  where any impostor disagrees with the Gate (in `random.Random(2)` order), label them with the Gate's
  decision and add them to the vectors. H is never added.
- **Cross-implementation check:** `verifier_gate()` (the package verifier's independent re-implementation)
  on every input in H and S.
- **Simplest rival:** "4,690 vectors already pin the Gate down": then round-0 unsafe ALLOW would be ~0.

## Predictions

- **A1 (control).** Every round-0 impostor reproduces all 4,690 vector decisions.
- **A2.** Round 0: the largest of the five unsafe-ALLOW counts on H is at least 500 (5%).
- **A3.** Round 8 (after the loop): the largest count on H is at most 50 (0.5%) and at most a tenth of
  round 0's.
- **A4.** `kernel_gate()` and `verifier_gate()` agree on decision and reasons for all 20,000 recombined
  inputs.
- **A5 (`--sabotage`).** Impostors are replaced by the Gate itself. Round-0 unsafe ALLOW is then 0, so A2 is
  REFUTED and the harness exits 1.
- **A6 (door, unrun).** Whether the added vectors enter `contract/gate_vectors.jsonl` is a contract change
  and Chad's decision. What residual H inputs still fool impostors at round 8, and whether the Go port agrees
  on recombined inputs, are not run here.

## What the predictions mean if they hold

A2 holding: passing all 4,690 vectors does not certify a second implementation; a program can pass and still
ALLOW what the Gate refuses on inputs built only from the contract's own values. A3 holding: a small number of
disagreement-chosen vectors closes most of that, for this learner. A4 failing would be a new finding: kernel
and verifier diverging outside the vector set.

## Limits

- Self-tested: Claude (Opus 5.5, Anthropic) writes the registration, learner and harness.
- Container only. NOT VALIDATED on the S25.
- Decision-tree impostors exploit incidental feature correlations; a human-written port is a different and
  probably milder impostor. The rate measures the vectors against this learner, not against all programs.
- Recombination covers 2-4 field swaps from observed values only; no new values are invented.
- Nothing here says the Gate is wrong.

## Provenance

Registration by Claude (Opus 5.5, Anthropic); direction by Chad Holland, review of summaries only, no line
review before this commit. Related proposals from other AI systems are credited in the Principia note, not
reproduced here.
