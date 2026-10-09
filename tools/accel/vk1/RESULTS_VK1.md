# VK-1 RESULTS: llama.cpp Vulkan on the S25 Ultra's Adreno 830

Run: Chad Holland's S25 Ultra (SM-S938U), Termux, 2026-10-06, preflight `2026-10-06T12:38:22-0500`.
Registration: [`VK1_PREREG.md`](VK1_PREREG.md), sha256 `99e048102150cf4ce040b62f0547381340ccaaed28935582238d4a0aec313bd9`.
Harness as run: [`vk1_probe.py`](vk1_probe.py), sha256 `e823f2a3da9bf2d1aeb02a8b265096645f978a3b585b8080d4fdf74e684ecd7e`.
Raw output, pasted unedited: [`run_2026-10-06.txt`](run_2026-10-06.txt).
`results.jsonl` and the per-cell logs are still on the device (see "Still open").

**Bottom line:** llama.cpp 0.6.0 Vulkan on this Adreno 830 executes, but it produces **wrong
decode output** for both Q4_0 and Q4_K_M. There is also a separate, deterministic abort
in the Q4_K mat-vec pipeline once more than one layer is offloaded. "Vulkan inference with
correct output" is **NOT DEMONSTRATED**. The perplexity instrument failed its own anti-vacuity
control, so this run says nothing about batched (mat-mat) correctness.

---

## What could have gone wrong, first

1. **The perplexity instrument is broken, and the control caught it (P2a REFUTED).**
   CPU TinyLlama perplexity on coherent English came out as **26244199.822**, and the scrambled
   control as **11284845.151**: *lower*, ratio **0.43** where ≥ 3.0 was required. No working
   language model scores coherent text in the tens of millions. The q40 and qwen_q4km CPU
   references are similar (**7045803223.079**, **26577930162.123**). Every `ppl_*` cell's
   CORRECT/INCORRECT label is therefore uninformative. The cause is unknown. The per-chunk
   numbers are in the device logs, which have not been examined yet.
2. **P5's "REFUTED" is mechanical, not evidence.** `ppl_vk1_tinyllama` matched the CPU value
   exactly (**26244199.822** both), so the harness called it CORRECT. With the instrument broken,
   that says nothing about whether batched evaluation on Vulkan is right. The equality to every
   printed digit is itself unexplained. Either the perplexity tool did not use the GPU at ngl 1,
   or the broken metric saturates. **Registration gap:** VK1_PREREG.md did not state that P5
   depends on P2a holding. That dependency is recorded here, and the registration is unchanged.
3. **The harness's label section printed "correct output" for those ppl cells.** That is a
   harness defect: the label logic did not require P2a to hold. Those lines in the raw output
   are to be disregarded. The harness is left as run. The fix belongs in a VK-2 harness.
4. **The TinyLlama CPU reference is degenerate.** Greedy CPU generation emitted end-of-text as
   its first token, and the captured text is the literal marker `[end of text]`. So:
   - **P2b** held by comparing two empty generations. It shows the comparator can return
     CORRECT, but on trivial input.
   - **P3** held mechanically for TinyLlama, which generated zero tokens. It is meaningful
     only for the two Qwen models.
   - **P4** rests on a single token: the GPU's first argmax was not end-of-text. That is a real
     mismatch, but it is thin evidence. The Qwen references (P6, P7) are the strong ones.
5. **The six exploratory `GGML_VK_DISABLE_*` runs produced byte-identical output** to the
   unflagged run (`Analysis Research Lab Research Lab Analy`). Either none of those switches
   touches the faulty path, or the variable never reached the process. The flags are recorded
   in each log header on the device, and nobody has checked them yet. Against a degenerate
   reference, these cells could not have shown a fix anyway.
6. **The registration was committed after the run.** Its sha256 was logged by the device before
   the first cell and published in the working session before the run, but it carries no git
   timestamp from before the run.
7. **Self-testing.** The registration and harness were written by Claude Opus 5.5. The sandbox
   tests used fake llama binaries, and those fakes could not have exposed a broken perplexity
   tool. Chad Holland ran the harness on the device and supplied the output. The code was not
   reviewed line by line.

## Predictions

| ID | Registered | Outcome | Reading |
|---|---|---|---|
| P1 | Adreno listed under Vulkan | **HELD** | `Vulkan0: Adreno (TM) 830` |
| P2a | PPL(scrambled)/PPL(text) ≥ 3.0 | **REFUTED (kept)** | 0.43. The PPL instrument is broken |
| P2b | CPU repeat = CORRECT | **HELD** | weak: both runs were end-of-text |
| P3 | CPU gen works, all models | **HELD** | TinyLlama generated 0 tokens. Qwen ×2 real |
| P4 | `gen_vk1_tinyllama` INCORRECT | **HELD** | rests on the first token only |
| P5 | `ppl_vk1_tinyllama` INCORRECT | **REFUTED (void)** | instrument failed P2a |
| P6 | `gen_vk1_q40` INCORRECT | **HELD** | strong |
| P7 | `gen_vk1_qwen_q4km` INCORRECT | **HELD** | strong |
| P8 | ngl-99 abort deterministic | **HELD** | 3/3 `mul_mat_vec_q4_k_f32_f32` |
| P9 | abort monotone in ngl, ngl 1 completes | **HELD** | onset at **ngl 2** |

`VERDICT 8 of 10 determinate predictions held as registered.` P4, P6 and P7 are predictions
of *failure*, so "8 of 10 held" does not mean anything passed.
`DIGEST e464c9443057b6626f1fb94aa0d12c672255dec41700bad98d0261447f8055a4`

## What the run shows

**1. Vulkan decode is wrong, and the fault is not specific to K-quants.** These are greedy
outputs (first 40 characters as reported):

| cell | output |
|---|---|
| `gen_cpu_q40` (Q4_0, CPU) | `Evidence is the information or data that` |
| `gen_cpu_qwen_q4km` (Q4_K_M, CPU) | `Evidence is the information or data that` |
| `gen_vk1_q40` (Q4_0, 1 layer on GPU) | `Iteration遮 s 除外mark he hehe hehehehehehe` |
| `gen_vk1_qwen_q4km` (Q4_K_M, 1 layer on GPU) | `apixeleoneoneoneoneoneoneoneoneoneoneone` |
| `gen_vk99_q40` (Q4_0, all layers on GPU) | `anca圈 gr gr gr granton apology apology A` |

The two quantizations agree with each other on CPU, and both are corrupted as soon as one
layer runs on the GPU. Under the interpretation key fixed in advance ("P6 held → suspicion
shifts to llama.cpp 0.6.0 Vulkan × the Adreno driver generally"), this is the reading the
registration committed to. It is **not** yet a diagnosis of which op is wrong.

**2. Two distinct faults, not one.**
- *Wrong output* appears for every quant tested, starting at 1 layer.
- *Abort* occurs only on the Q4_K mat-vec pipeline. TinyLlama Q4_K_M aborts from ngl 2 upward
  (2, 11, 21, 22, 23 and 99 all abort; ngl 1 completes). qwen Q4_K_M aborts at ngl 99. The Q4_0
  model does **not** abort at ngl 99: it completes, with wrong output.

**3. The abort does not look like memory exhaustion.** MemAvailable before every aborting cell
was 5183–5814 MiB (4946–5857 MiB across all 34 cells), and the abort is 3/3 deterministic. That disfavours the
resource-exhaustion hypothesis raised after the earlier `ngl 99` crash. It does not exclude it,
since the driver's internal limits are not visible from here.

**4. The Vulkan backend executes.** The ngl-1 outputs differ from CPU, and the aborts come from
inside `ggml_vulkan`. The harness's own "Vulkan in log" detector found no `Vulkan0` or
`ggml_vulkan` string in the ngl-1 perplexity logs. That detector is too narrow for this build's
quiet logging, and per point 2 above, the perplexity tool may not have used the GPU at all.

## What it does not show

It shows nothing about why the output is wrong (which shader or op), and nothing about whether
batched evaluation is correct (the instrument is broken). It is not evidence about other
llama.cpp versions or other Adreno driver builds. It says nothing about speed or energy: battery
current and temperature were recorded as a proxy only. And it does not show that the GPU itself
is faulty. The fault lies in the combination of llama.cpp 0.6.0's Vulkan shaders and Qualcomm
driver `f61dec9117`.

Measured on the S25: yes, this whole document reports a device run. Model results are from
local GGUF models. Nothing here is a real-world deployment claim.

## Candidate next steps (proposals, not decisions)

- **Fix the instrument before trusting any ppl cell.** Read `logs/ppl_cpu_tinyllama.log` for the
  per-chunk values and the token count. Plausible causes, all untested: a 128-token context too
  short for this tool's scoring window, or a BOS or tokenization mismatch.
- **VK-2 (to be registered):** use a non-degenerate TinyLlama reference by applying the chat
  template or a different prompt, so P4 tests more than one token. Use a fixed perplexity
  instrument that has to pass the scrambled control first. Make the label logic depend on that
  anti-vacuity result.
- **Op isolation:** use llama.cpp's `test-backend-ops` (if the Termux package ships it) to compare
  each Vulkan op against CPU on this driver. That names the faulty op directly.
- **Alternative backend:** llama.cpp's OpenCL backend is the path Qualcomm targets for Adreno, but
  it currently sees 0 platforms in Termux. Making the vendor OpenCL ICD visible would be an
  intervention and would need its own registration.

## Still open

- `~/sv-lab/runs/vk1/results.jsonl` and `logs/` are on the device and not yet committed. Once they
  are, a CI step can re-derive the pinned digest from them.
- The cause of the perplexity failure.
- Whether the exploratory environment variables reached the process (check the log headers).

---

Provenance: device run and output by Chad Holland (2026-10-06). The registration, harness and
this analysis were drafted by Claude Opus 5.5 (Anthropic) under Chad's direction. Human review
level: the device run's output was examined in session; the code and this document were not
reviewed line by line. Human responsibility for the final artifact: Chad Holland.
