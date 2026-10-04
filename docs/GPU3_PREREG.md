# GPU-3 — the GPU-2 follow-up: a prompt the model gets right, a repeat, and the CPU. Registration

Status: **REGISTERED, nothing run.** Committed before the probe's new options exist. GPU-2 (`GPU2_RESULTS.md`,
`9c93ad4`) is the only result read before this.

Drafted by Claude (Opus 5.5) at Chad Holland's direction. Chad has not reviewed it line by line.

## Why

GPU-2 showed that throttling did not change the reply. But the reply was wrong, and the run was single. A
throttle that changed a wrong answer into another wrong answer would matter less than one that changed a right
action into a wrong one. And one run can be luck.

## Setup

Same phone, same model file (`llama-3.2-3b.gguf`, sha256 `6c1a2b41…28ff`), same request settings as GPU-2
(temperature 0, seed 1, `cache_prompt` false, 32 tokens). Two prompts:

- **easy**: `Q: What is 23 * 8? Reply with only the number.\nA:` (correct answer: 184).
- **hard**: GPU-2's prompt, unchanged (7338 × 5099; correct answer: 37,416,462).

Four runs, in this order, each with `tools/gpu2_probe.py`:

| Run | Server | Probe |
|---|---|---|
| A | `llama-server-adreno` (OpenCL) | `--prompt easy` (cold 5, heat to throttle, hot 5, control) |
| B | same server, right after A | `--prompt hard` (a repeat of GPU-2) |
| C | `llama-server --device none` (CPU) | `--prompt easy --cpu` (5 requests + control, no kgsl judgement) |
| D | same CPU server | `--prompt hard --cpu` |

The GPU state is still read for C and D, and printed only.

## Predictions

| ID | Prediction |
|---|---|
| P1 | Run A's cold reply contains `184` (the model gets the easy one right on the GPU). **May fail.** If it does, P2 is still judged, but it can no longer show a right action turning wrong. |
| P2 | Run A: the hot replies are byte-identical to the cold replies (throttle reached, as GPU-2's P2 requires). |
| P3 | Run B repeats GPU-2: every reply (cold and hot) has the GPU-2 hash `a01b977adab9…`. |
| P4 | CPU versus GPU, easy: run C's reply bytes equal run A's. |
| P5 | CPU versus GPU, hard: run D's reply bytes differ from run B's. This is the 2026-09-26 Qwen pattern (Q1'), predicted to hold for this model too. |
| P6 | Instrument checks, as in GPU-2: GPU busy ≥ 50 % in A and B cold requests; each run's control reply differs from its temperature-0 reply. |

## Limits

One phone, one model, two prompts, one run each. Run order is fixed (A, B on the GPU; then C, D on the CPU),
so the CPU runs start on a warm phone. That is recorded, not controlled. Self-tested.

## Next unrun test

A second model (the Qwen2.5-1.5B from `PLATFORM_TESTS.md`) through the same four runs.

## Amendment 1 (2026-10-04, before runs C and D; the text above is unchanged)

Runs C and D crashed Termux three times when the CPU server started: twice right after the GPU runs, and once on
a cool phone (GPU 37.6 °C), so heat is not the main cause. Each time, the server log stopped at
`llama threadpool init, n_threads = 8` with no error. The GPU server's log shows that it sized its own memory as
`n_slots = 4, n_ctx_slot = 13568, kv_unified = 'true'`. `free -h` showed 4.3 GiB available, out of 10 GiB.
Inference, not established: the CPU server reserves a similar KV cache in ordinary memory, and Android kills
Termux when memory runs out.

Change, made before C and D run: the CPU server is started with `-c 2048 -np 1` (one slot, 2048-token context).
The prompts and replies are under 100 tokens, so this should not change the arithmetic. But runs A and B used the
GPU server's own sizing, so P4 and P5 now compare runs with **different context settings**, and a difference
could come from that rather than from the CPU versus GPU split. That limit will be stated next to P4 and P5.
