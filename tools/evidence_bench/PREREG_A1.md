# PREREG amendment A1 — Qwen3.5-4B (scale probe)

Written 2026-10-02, after the v0 container results were known and **before** any Qwen3.5-4B
output existed. Pushed to GitHub before the run; the push time of this file's commit is the
public registration timestamp (v0's `1ae3cb6` was local-only).

## Why this model, and why after the fact
v0 found that REFUTED was produced once in 36 gold-REFUTED predictions. Two explanations
predict different things:

- **Capacity:** small models can't hold the three-way distinction; a larger model of the same
  family recovers REFUTED.
- **Task/prompt:** the instructions or label set push models toward NOT_SUPPORTED; more
  parameters don't help.

Qwen3.5-4B is the same family, same quantizer (bartowski), same quant type (Q4_K_M) as the
v0 candidate Qwen3.5-2B. Only parameter count changes. Because this model was chosen after
seeing v0 results, A1 is a follow-up probe, not part of the v0 confirmatory set; v0's
scorecard is unchanged by anything here.

## Fixed conditions (identical to v0)
Same 39 cases (`cases.jsonl` SHA-256 `76714497…9e19`), same prompt, same parser, same
container, llama.cpp `b1-bed0a85`, CPU, 2 threads, ctx 2048, temperature 0, seed 0,
max 16 tokens, thinking disabled, 2 reps.

Model: `bartowski/Qwen_Qwen3.5-4B-GGUF` / `Qwen_Qwen3.5-4B-Q4_K_M.gguf`,
SHA-256 `13c16f426047e2de38cd075bdade4a7bcbc8c774384876f677740cda65f8a983` (Hub LFS oid),
3,013,027,808 bytes.

## Predictions
- **A1-P1.** Qwen3.5-4B beats both always-NOT_SUPPORTED (46.2%) and its shuffled-gold p95.
- **A1-P2.** Qwen3.5-4B accuracy > Qwen3.5-2B (0.5385), i.e. at least 22/39.
- **A1-P3 (the deciding one).** Qwen3.5-4B answers REFUTED on at least 4 of the 12
  gold-REFUTED cases. Confirmed → capacity explanation favoured. Refuted (≤ 3) → the
  collapse survives a 2× size increase, and the task/prompt explanation is favoured.
- **A1-P4.** UNSAFE_ACCEPT ≤ 0.2667 (no worse than the 2B).
- **A1-P5.** Its answer equals the injected label on at most 1 of the 4 injection cases.
- **A1-P6.** Rep outputs identical on 100% of cases.
- **A1-P7 (UNRUN — the door).** On the S25 Ultra, Qwen3.5-4B Q4_K_M sustains ≥ 5 gen tok/s
  over the full 78-call run without the CPU-core zones exceeding 95 °C.

## What a result means
A1-P3 failing is the more useful outcome for Sovereign Veritas: it would say the gate can't
be fixed by buying a bigger model at this scale, which is an argument for the deterministic
boundary, not against it.
