# GPU-2 — does the Adreno GPU's thermal state change the model's reply? Registration

Status: **REGISTERED, nothing run.** Committed alone, before `tools/gpu2_probe.py` exists.

Drafted by Claude (Opus 5.5) at Chad Holland's direction. Chad has not reviewed it line by line.

## Question

`docs/PLATFORM_TESTS.md` (2026-09-26) showed that, on the S25, which reply a model gives depends on the backend.
On the hard prompt, CPU and Qualcomm OpenCL gave different wrong answers; the Vulkan path corrupted output.
It did not test whether the **same** backend gives the same bytes when the GPU is hot and throttled as when it is
cold. If it does not, the action a model proposes on this phone depends on how warm the GPU is, which is a
runtime condition the Gate would then have to treat as evidence.

## What was read before this registration

- `docs/PLATFORM_TESTS.md` (OpenCL setup, `llama-server-adreno`, the 2026-09-26 results).
- On the S25 (Chad's terminal, 2026-10-04), readable **without** Shizuku in `/sys/class/kgsl/kgsl-3d0`:
  `clock_mhz 222`, `max_clock_mhz 1200`, `throttling 0`, `thermal_pwrlevel 0`, `temp 42600`,
  `gpu_busy_percentage 0 %`, `devfreq/cur_freq 222000000`, `gpu_model Adreno830v2`. The meaning of `throttling`
  and `thermal_pwrlevel` is taken from their names, not from documentation.

Nothing has been run for this experiment.

## Setup (fixed now)

- Server: `llama-server-adreno` (OpenCL, `-ngl 99`), started by Chad, one model for the whole run. The probe
  records the server's `/props` and, if given `--model-file`, the model file's sha256.
- Request: `POST /completion` with the fixed prompt
  `Q: What is 7338 * 5099? Reply with only the number.\nA:`, `n_predict` 32, `temperature` 0, `seed` 1,
  `cache_prompt` false. The reply's identity is the sha256 of its `content` bytes.
- During every request the probe polls `clock_mhz`, `gpu_busy_percentage`, `temp`, `throttling` and
  `thermal_pwrlevel` every 0.1 s and records min/max.
- Phases: **cold**, 5 requests as soon as the run starts. **Heat**: back-to-back long generations
  (`n_predict` 256, `temperature` 0.7, a different seed each time) until a request sees `throttling` > 0 or
  `thermal_pwrlevel` > 0, or 600 s pass. **Hot**: 5 requests identical to the cold ones, immediately after.
  **Control**: one request identical except `temperature` 0.8, `seed` 2.

## Predictions

| ID | Prediction |
|---|---|
| P1 | The 5 cold replies are byte-identical. |
| P2 | The heat phase reaches a throttled state (`throttling` > 0 or `thermal_pwrlevel` > 0 during at least one hot request) within 600 s. **May fail.** If it does, P3 is reported NOT RUN: hot then only means "after load", not "throttled". |
| P3 | The 5 hot replies are byte-identical to the cold replies. A lower clock changes speed, not arithmetic. |
| P4 | Instrument check: the GPU did the work. Peak `gpu_busy_percentage` during cold requests is at least 50. If not, the replies were not shown to come from the GPU, and P1–P3 are not judged. |
| P5 | Instrument check: the comparison can say DIFFERENT. The control reply's sha256 differs from the cold reply's. |

## Controls and limits

- A self-test (`--selftest`) runs the probe against a fake server and a fake kgsl directory twice: once with a
  server whose hot replies change, where P3 must be REFUTED and the probe must exit 1, and once without.
- One phone, one model, one prompt. "Throttled" is whatever these two files report; a throttle the files do not
  show is not detected.
- If the phone is already hot at the start, "cold" means the start of the run. The starting temperature is
  printed.
- Self-tested: the probe's author judges it.

## Next unrun test

The same on the CPU (`--device none`), where a thermal effect on bytes would be even less expected. And with a
second prompt whose correct answer the model gets right, so a change would turn a right action into a wrong one.
