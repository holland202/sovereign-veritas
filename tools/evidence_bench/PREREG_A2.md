# PREREG amendment A2 — decomposed arm (model extracts, deterministic gate decides)

Written 2026-10-02 before any decomposed-arm output existed. Pushed to GitHub before the run.
The A1 Qwen3.5-4B direct run was in progress when this was written; its partial output had
been seen, so A2 makes no prediction that depends on the 4B direct numbers beyond
"decomposed vs direct for the same model".

## Change under test
Direct arm (v0/A1): one model call decides the whole verdict from the full prompt.

Decomposed arm (A2), `run_decomposed.py` + `gate.py`:
- the model sees **one admissible item's content** and the proposition, and answers
  TRUE / FALSE / NEITHER about that content at face value;
- it never sees the source, verified flag, date, other items, or the requester note;
- inadmissible items (unverified or dated before 2026-09-01) are never sent to the model;
- `gate.decide()` (pure Python) applies admissibility, conflict, and the verdict.
  Unparseable model output counts as NEITHER (fails toward NOT_SUPPORTED).

Gate controls (run before this file was written): hidden gold stances → 39/39;
all-NEITHER → 18/39 (= always-NOT_SUPPORTED); flipped stances → 18/39.

## Known structural advantage, stated up front
5 cases (C6-01, C6-02, C6-03, C11-01, C11-02) have no admissible item, so the gate answers
them correctly with no model involvement. The fair comparison is therefore on the **34
model-dependent cases**. Requester notes (C8) never reach the extractor in A2, so C8
immunity is also structural. These are properties of the architecture, not of any model,
and are reported as such.

Direct-arm accuracy on the 34 (from v0 data, rep 0): Qwen2.5-1.5B 0.2941, LFM2.5-1.2B
0.2353, Qwen3.5-2B 0.5000. Always-NOT_SUPPORTED on the 34: 0.3824.

## Fixed conditions
Same cases, container, llama.cpp `b1-bed0a85`, CPU, 2 threads, ctx 2048, temperature 0,
seed 0, thinking disabled, max 8 tokens, 2 reps. Models: Qwen2.5-1.5B, LFM2.5-1.2B,
Qwen3.5-2B, Qwen3.5-4B, all Q4_K_M, same files and hashes as v0/A1.

## Predictions
- **A2-P1.** For every model, decomposed accuracy on the 34 > its direct accuracy on the 34.
- **A2-P2.** For every model, decomposed UNSAFE_ACCEPT (all 39) ≤ its direct UNSAFE_ACCEPT.
- **A2-P3.** Qwen3.5-2B decomposed REFUTED recall ≥ 4/12 (the collapse is at least partly
  the three-way label format, not only capacity).
- **A2-P4.** Qwen3.5-2B decomposed accuracy (all 39) ≥ 0.75.
- **A2-P5.** LFM2.5-1.2B still lands on the injected label in ≥ 2 of 4 injection cases
  (in-content injection still reaches the extractor; decomposition does not remove it).
- **A2-P6.** At least half of Qwen3.5-2B's decomposed misses fall in numeric_edge,
  quantifier, or insufficient (the residue is reading errors, not boundary errors).
- **A2-P7 (UNRUN — the door).** On the S25, the decomposed arm with Qwen3.5-2B completes
  all 39 cases with median per-case latency under 5 s.

## What this does and does not show
A2 measures whether moving admissibility and conflict out of the model and into code
reduces wrong acceptances. It does not validate Sovereign Veritas: here the metadata the
gate trusts (verified, date) is supplied by the test harness. In a real system that
metadata must itself come from independent verification, and that is where the hard
problem moves.
