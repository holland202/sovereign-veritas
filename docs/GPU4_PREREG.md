# GPU-4 — same reply, same computation? CPU and Adreno token probabilities. Registration

Status: **REGISTERED, nothing run.** Committed before `tools/gpu4_probs.py` exists.

Drafted by Claude (Opus 5.5) at Chad Holland's direction. Chad has not reviewed it line by line.

## Why

GPU-3 found byte-identical temperature-0 replies on the CPU and the Adreno OpenCL path. But the temperature-0.8
controls differed between the two for the same seed (an unregistered observation, `GPU3_RESULTS.md`). One
explanation is that the backends compute slightly different numbers that never change the top token but shift
the probabilities that sampling uses. If that is right, an identical temperature-0 reply is not evidence of an
identical computation. That matters for any check that treats "same output" as "same process".

## Setup

- Same phone and model file as GPU-3 (`llama-3.2-3b.gguf`, sha256 `6c1a2b41…28ff`).
- **Both servers start with `-c 2048 -np 1`**, so the two backends now share context settings (the GPU-3
  Amendment 1 limit does not apply here). GPU: `llama-server-adreno`. CPU: `llama-server --device none`.
- Requests: GPU-3's easy and hard prompts; `temperature` 0, `seed` 1, `cache_prompt` false, `n_predict` 8,
  `n_probs` 10. Each prompt is sent **twice** on each backend. The probe stores the raw `/completion` response and
  the GPU busy peak during each request.
- Comparison: for each generated position, the chosen token and the log-probabilities the server reports for
  its top tokens. Values are compared exactly, then by absolute difference for tokens present in both.

## Predictions

| ID | Prediction |
|---|---|
| P1 | Repeatability: on each backend, the two requests for the same prompt report identical tokens and identical probability values (exact equality). |
| P2 | Same choices: CPU and GPU pick the same token at every generated position, for both prompts (consistent with GPU-3). |
| P3 | Different numbers: for at least one prompt, at least one reported log-probability differs between CPU and GPU. **This is the hypothesis.** If P3 is refuted, the temperature-0.8 difference in GPU-3 has some other cause, and that is reported as the finding. |
| P4 | Small: the largest absolute log-probability difference between CPU and GPU is below 0.05. |
| P5 | Instrument checks: GPU busy peak ≥ 50 % on the GPU requests and ≤ 10 % on the CPU requests; and a self-test (`--selftest`) on synthetic data shows the comparison reports both "identical" and "different" when they are true. |

## Limits

One model, two prompts, 8 tokens each. What the server reports is taken as given; a difference introduced by
how the server rounds or formats probabilities would look like a backend difference. The reported format is
recorded raw so this can be checked. Self-tested.

## Next unrun test

The same comparison on a second model (Qwen2.5-1.5B), and on the CPU with a different thread count.
