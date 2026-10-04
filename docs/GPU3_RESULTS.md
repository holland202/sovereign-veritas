# GPU-3 results (partial): runs A and B done on the GPU; the CPU runs crashed Termux twice

Registration: [`GPU3_PREREG.md`](GPU3_PREREG.md), `037a51a`. Probe `31f819f`. Run by Chad Holland on the
S25 Ultra, 2026-10-04, about 14:25–14:33 CT. Same model file as GPU-2 (sha256 `6c1a2b41…28ff`).

Drafted by Claude (Opus 5.5) at Chad Holland's direction. Chad ran it on the phone and has not reviewed this
text line by line.

## What went wrong, first

- **Runs C and D (CPU) did not run.** Termux crashed twice at step 5, right after `llama-server --device none`
  was started following the two GPU runs. One attempt had an external clip-on fan (Black Shark) attached. The
  cause is **not established**: the server log was not read before this was written. Candidates are a thermal
  shutdown, Android ending the app under memory or heat pressure, or a CPU-server fault. P4 and P5 are
  **NOT RUN**.
- **The GPU reached 105.3 °C** (`kgsl temp`) in run A's hot phase. That is the highest reading in this series.
  Further heat runs should not be repeated back to back.
- **Run A's throttle was weak until the last request.** `thermal_pwrlevel` was 1 (clock 1100–1200 MHz) for hot
  requests 1–4 and reached 5 (832 MHz) only on hot request 5. The registered P2 condition (throttle seen) is
  met, but most of run A's "hot" replies ran at nearly full clock. Run B throttled hard (`pwrlevel` 9, 525 MHz)
  from hot request 2.
- The first attempt failed earlier for an unrelated reason: the probe was started from `~` instead of
  `~/sv-gpu2` (`No such file or directory`).
- `throttling` again stayed 0 throughout. Only `thermal_pwrlevel` and the clock showed the throttle.

## Output (verbatim, as pasted)

```
PROMPT easy  backend gpu
START  model /data/data/com.termux/files/home/llama-3.2-3b.gguf  file sha256 6c1a2b41161032677be168d354123594c0e6e67d2b9227c84f296ad037c728ff  temp 46900  clock 222  pwrlevel 0
cold    1  dfe8453d9d7d  clock 222-1200 MHz  busy max 97%  temp max 76.9C  throttling max 0  pwrlevel max 0  reply '184\nQ: What is 17 * 9? Reply with only t'
cold    2  dfe8453d9d7d  clock 1200-1200 MHz  busy max 97%  temp max 81.5C  throttling max 0  pwrlevel max 0  reply '184\nQ: What is 17 * 9? Reply with only t'
cold    3  dfe8453d9d7d  clock 1200-1200 MHz  busy max 97%  temp max 86.1C  throttling max 0  pwrlevel max 0  reply '184\nQ: What is 17 * 9? Reply with only t'
cold    4  dfe8453d9d7d  clock 1200-1200 MHz  busy max 97%  temp max 90.7C  throttling max 0  pwrlevel max 0  reply '184\nQ: What is 17 * 9? Reply with only t'
cold    5  dfe8453d9d7d  clock 1200-1200 MHz  busy max 97%  temp max 92.6C  throttling max 0  pwrlevel max 0  reply '184\nQ: What is 17 * 9? Reply with only t'
HEAT   2 long generations, 21 s, throttle seen: True
hot     1  dfe8453d9d7d  clock 1100-1200 MHz  busy max 96%  temp max 105.3C  throttling max 0  pwrlevel max 1  reply '184\nQ: What is 17 * 9? Reply with only t'
hot     2  dfe8453d9d7d  clock 1100-1200 MHz  busy max 95%  temp max 105.3C  throttling max 0  pwrlevel max 1  reply '184\nQ: What is 17 * 9? Reply with only t'
hot     3  dfe8453d9d7d  clock 1100-1200 MHz  busy max 96%  temp max 105.3C  throttling max 0  pwrlevel max 1  reply '184\nQ: What is 17 * 9? Reply with only t'
hot     4  dfe8453d9d7d  clock 1100-1200 MHz  busy max 95%  temp max 105.3C  throttling max 0  pwrlevel max 1  reply '184\nQ: What is 17 * 9? Reply with only t'
hot     5  dfe8453d9d7d  clock 832-1200 MHz  busy max 95%  temp max 102.6C  throttling max 0  pwrlevel max 5  reply '184\nQ: What is 17 * 9? Reply with only t'
control 1  f12f45edfb93  clock 832-832 MHz  busy max 95%  temp max 86.1C  throttling max 0  pwrlevel max 5  reply '184 \nQ: What is 11 * 6? Reply with only '
HELD                         P1
HELD                         P2
HELD                         P3
HELD                         P4
HELD                         P5
SHA    cold ['dfe8453d9d7dd18db272c21469345d8970b0b23cb617e52a1e5f82568b095d0e']  hot ['dfe8453d9d7dd18db272c21469345d8970b0b23cb617e52a1e5f82568b095d0e']  control f12f45edfb93d222c7dfeb68f8dd2198b0860f21eb2bdb75a9811029aed90617
LOG    /data/data/com.termux/files/home/gpu3_easy_gpu.json

PROMPT hard  backend gpu
START  model /data/data/com.termux/files/home/llama-3.2-3b.gguf  file sha256 None  temp 39900  clock 222  pwrlevel 0
cold    1  a01b977adab9  clock 222-1200 MHz  busy max 96%  temp max 72.6C  throttling max 0  pwrlevel max 0  reply '37, 191, 502, 722, 000, 000, 000, 000, 0'
cold    2  a01b977adab9  clock 1200-1200 MHz  busy max 96%  temp max 79.2C  throttling max 0  pwrlevel max 0  reply '37, 191, 502, 722, 000, 000, 000, 000, 0'
cold    3  a01b977adab9  clock 1200-1200 MHz  busy max 96%  temp max 83.4C  throttling max 0  pwrlevel max 0  reply '37, 191, 502, 722, 000, 000, 000, 000, 0'
cold    4  a01b977adab9  clock 1200-1200 MHz  busy max 96%  temp max 86.1C  throttling max 0  pwrlevel max 0  reply '37, 191, 502, 722, 000, 000, 000, 000, 0'
cold    5  a01b977adab9  clock 1200-1200 MHz  busy max 95%  temp max 89.6C  throttling max 0  pwrlevel max 0  reply '37, 191, 502, 722, 000, 000, 000, 000, 0'
HEAT   2 long generations, 5 s, throttle seen: True
hot     1  a01b977adab9  clock 1200-1200 MHz  busy max 97%  temp max 100.3C  throttling max 0  pwrlevel max 0  reply '37, 191, 502, 722, 000, 000, 000, 000, 0'
hot     2  a01b977adab9  clock 525-1200 MHz  busy max 96%  temp max 99.6C  throttling max 0  pwrlevel max 9  reply '37, 191, 502, 722, 000, 000, 000, 000, 0'
hot     3  a01b977adab9  clock 525-525 MHz  busy max 97%  temp max 71.5C  throttling max 0  pwrlevel max 9  reply '37, 191, 502, 722, 000, 000, 000, 000, 0'
hot     4  a01b977adab9  clock 525-525 MHz  busy max 97%  temp max 65.7C  throttling max 0  pwrlevel max 9  reply '37, 191, 502, 722, 000, 000, 000, 000, 0'
hot     5  a01b977adab9  clock 525-525 MHz  busy max 97%  temp max 62.6C  throttling max 0  pwrlevel max 9  reply '37, 191, 502, 722, 000, 000, 000, 000, 0'
control 1  9d11bfd1ba29  clock 525-1200 MHz  busy max 96%  temp max 70.3C  throttling max 0  pwrlevel max 9  reply '37311922'
HELD                         P1
HELD                         P2
HELD                         P3
HELD                         P4
HELD                         P5
SHA    cold ['a01b977adab95c605438bbb99ecb2fc9d3aea4bc1557ef13c0c090af3d8b37f0']  hot ['a01b977adab95c605438bbb99ecb2fc9d3aea4bc1557ef13c0c090af3d8b37f0']  control 9d11bfd1ba294a8fb28e2ddf3a44b8619db2040a8a6df958ecd8433c1f7a536e
LOG    /data/data/com.termux/files/home/gpu3_hard_gpu.json
```

(The probe prints its own GPU-2 labels P1–P5 per run. The GPU-3 judgement is the table below.)

## Outcome (GPU-3 predictions)

| ID | Result |
|---|---|
| P1 easy answered right on the GPU | **HELD.** The reply starts `184`. The model then keeps going (`\nQ: What is 17 * 9? ...`) because the request has no stop sequence. "Contains 184" is met. |
| P2 easy: hot bytes = cold bytes | **HELD**, but see the weak throttle above: `dfe8453d9d7d` ×10, with only the last hot request below 1100 MHz |
| P3 hard repeats GPU-2 | **HELD.** `a01b977adab9` ×10, the same hash as GPU-2. Throttled to 525 MHz from hot request 2 |
| P4 CPU = GPU, easy | **NOT RUN** (Termux crashed) |
| P5 CPU ≠ GPU, hard | **NOT RUN** (Termux crashed) |
| P6 instrument checks | **HELD** for A and B: busy 95–97 %; each control differs |

Across GPU-2 and GPU-3, three GPU runs (30 temperature-0 replies across thermal states from `pwrlevel` 0 to 9)
gave no byte change for either prompt, including one the model answers correctly.

## The CPU server log (read after the crash, verbatim tail)

```
0.00.000.459 I srv  llama_server: initializing ...
0.00.117.638 E ggml_opencl: platform IDs not available.
0.00.134.618 I cmn  common_param: common_params_print_info: verbosity = 3 (adjust with the `-lv N` CLI arg)
0.00.135.048 W srv  llama_server: security: no API key is set and CORS allows all origins (see https://github.com/ggml-org/llama.cpp/pull/25655)
0.00.136.606 I srv    load_model: loading model '/data/data/com.termux/files/home/llama-3.2-3b.gguf'
0.05.981.735 I cmn          init: llama threadpool init, n_threads = 8
```

The log stops at thread-pool start, with no error and no shutdown message, so the process was ended from
outside. The `ggml_opencl` line is expected for plain `llama-server` (no Adreno library path) and is not the
cause. Inference, **not established**: Android ended Termux when 8 CPU threads started on a phone whose GPU had
just been at 100–105 °C. CPU runs on a cool phone worked on 2026-09-26. Android's own logs were not read.

## Next

Find the crash cause (the tail of `~/gpu3_cpu.log`) before retrying C and D. Retry them only on a phone that has
cooled (`kgsl temp` under about 45 °C), with no GPU run immediately before.
