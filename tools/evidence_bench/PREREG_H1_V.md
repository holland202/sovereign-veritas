# PREREG H1 amendment V — veto consensus

Written 2026-10-02 while the H1 suite was running, after the v0 replay exposed a defect in
the registered unanimous consensus (see `consensus_veto.py`). No H1 decomposed-arm output
existed when this was committed: the suite was still in its direct arm, at the second of
four models. Disclosure: four progress lines from the LFM2.5 *direct* arm (cases
H1-IN-02..05) had scrolled past in a log tail. None of the stance outputs these predictions
depend on had been produced.

## Defect being fixed
`consensus.unanimous` turns a disagreement on a refuting item into NEITHER, which can delete
the refutation that blocks acceptance. An exhaustive check over all two-extractor stance
assignments on 1–3 admissible items finds 140 assignments where unanimous consensus says
SUPPORTED while at least one member alone would not. In v0, case C5-02 is one of them.

## Policy
`consensus_veto.veto`: an item is TRUE only if every extractor says TRUE, FALSE if any
extractor says FALSE, otherwise NEITHER. **Theorem:** a veto SUPPORTED implies every member
alone would say SUPPORTED. The same exhaustive check finds 0 violations in 819 assignments.
This is an invariant, so it is *checked*, not predicted: veto unsafe accept ≤ each member's
unsafe accept on any case set, by construction.

## Predictions (empirical, can fail)
- **H1-V1.** Veto (Qwen3.5-2B ∧ Qwen3.5-4B) accuracy on H1 ≥ Qwen3.5-2B A2 accuracy on H1.
  In-sample on v0 it was 31/39 vs 29/39; this tests whether that holds out of sample.
- **H1-V2.** Veto (Qwen3.5-2B ∧ LFM2.5-1.2B) accuracy on H1 < Qwen3.5-2B A2 accuracy on H1.
  LFM2.5's errors should cost more through extra vetoes than they save.
- **H1-V3.** Veto (Qwen3.5-2B ∧ Qwen3.5-4B) REFUTED recall on H1 ≥ Qwen3.5-2B A2 REFUTED
  recall on H1.

Scored by `analyze.py` (veto replay from the recorded A2 H1 stances; no new model calls).
