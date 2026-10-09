# AMB-1 — results: passing all 4,690 vectors does not pin the Gate down

**Status:** Draft, self-tested. 4 of 4 as registered; A5 (`--sabotage`) exit 1 as registered.
**Registration:** `docs/AMB1_PREREG.md` (`c179025`). **Harness:** `tools/amb1_probe.py`, as run and pinned on
this branch. **Base:** `main` at `9e87f41`.

## What could have gone wrong, first

1. **Self-tested.** Claude (Opus 5.5, Anthropic) chose the question, wrote the learner, the harness and this
   file. Nobody independent has run it.
2. **Thresholds were set after an exploratory run** (scikit-learn trees, disclosed in the registration). The
   registered learner is a different, stdlib one; its numbers were first seen in this run.
3. **The registered learner gave different numbers from the exploratory one.** Round 0 max 1,235 (12.35%)
   here against 2,469 (24.69%) exploratory; round 8 max 28 (0.28%) here against 0.05%. Both cross the
   registered thresholds; the 0.05% figure from the conversation should not be quoted for this result.
4. **The decline is not monotonic.** Round 2's max (273) is higher than round 1's (213). Individual impostors
   jump around; only the max over five is tested.
5. **Decision-tree impostors are a harsh stand-in.** They exploit incidental feature patterns that a
   human-written port probably would not. The rate is a property of the vectors against this learner.
6. **Container only.** NOT VALIDATED on the S25. The Go port was not run on recombined inputs.
7. No deviations from the registration.

## Raw output (`results/amb1/run.txt`)

```
AMB-1 | registered run | python 3.13.16
  round 0: vectors  4690  unsafe ALLOW on H [423, 103, 62, 96, 1235]  added 100
  round 1: vectors  4790  unsafe ALLOW on H [48, 213, 88, 60, 157]  added 100
  round 2: vectors  4890  unsafe ALLOW on H [167, 63, 273, 99, 88]  added 100
  round 3: vectors  4990  unsafe ALLOW on H [34, 80, 54, 60, 57]  added 100
  round 4: vectors  5090  unsafe ALLOW on H [73, 33, 43, 22, 27]  added 100
  round 5: vectors  5190  unsafe ALLOW on H [27, 49, 36, 39, 50]  added 100
  round 6: vectors  5290  unsafe ALLOW on H [55, 37, 20, 21, 15]  added 100
  round 7: vectors  5390  unsafe ALLOW on H [24, 28, 44, 21, 26]  added 100
  round 8: vectors  5490  unsafe ALLOW on H [12, 22, 20, 28, 26]
  truth on H {'ALLOW': 12, 'DEFER': 96, 'REFUSE': 9892}  kernel/verifier mismatches on 20000: 0

  A1  HELD
  A2  HELD
  A3  HELD
  A4  HELD
VERDICT 4 of 4 as registered (A5 is --sabotage; A6 is the door)
DIGEST 4cb0e9095963584326466cc515082c5f148c97a0e31e2ce339fb3d4ca04547cd
```

Sabotage (`results/amb1/sabotage.txt`): A2 REFUTED, `VERDICT 3 of 4`, exit 1. Full suite on the branch:
`481 passed`.

## Predictions

| | prediction | outcome |
|---|---|---|
| A1 | every round-0 impostor reproduces all 4,690 vectors | HELD |
| A2 | round-0 max unsafe ALLOW on H ≥ 500 | HELD (1,235) |
| A3 | round-8 max ≤ 50 and ≤ round 0 / 10 | HELD (28; 1,235 / 10 = 123.5) |
| A4 | kernel and verifier agree on all 20,000 recombined inputs | HELD (0 mismatches) |
| A5 | `--sabotage` exits 1 | HELD |
| A6 | adopt the added vectors; residual inputs; Go port | door, unrun |

## What this shows

- **Implementation claim:** five programs each reproduce every one of the 4,690 contract vectors, and one of
  them says ALLOW where the Gate refuses or defers on 1,235 of 10,000 inputs built only from values the
  contract already contains. "4,690 of 4,690" does not certify a second implementation as safe.
- **The loop works for this learner:** 800 disagreement-chosen vectors (+17%) bring the worst impostor to 28 of
  10,000. Not to zero.
- **A4 is a positive finding about SV:** the kernel and the package verifier's re-implementation agree on all
  20,000 recombined inputs, which lie outside the vector set.

## What it does not show

That the Gate is wrong; anything about a human-written port; inputs with values the contract never uses;
behaviour on the S25.

## Candidate next steps (proposals)

- Adopting the 800 added vectors into `contract/gate_vectors.jsonl` is a contract change, so Chad's decision.
  They are recoverable from the harness (seeded).
- Run the Go port on the same 20,000 inputs.
- Publish the worst-impostor rate beside the vector count as the contract's strength.

## Provenance

AI participation: Claude (Opus 5.5, Anthropic) wrote the registration, harness and this file. The framing came
from a session combining proposals Chad collected from several AI systems (credited in the Principia note).
Human validation: Chad Holland directed the work on 2026-10-05; review was of summaries, not line by line.
Chad is responsible for the final artifact.
