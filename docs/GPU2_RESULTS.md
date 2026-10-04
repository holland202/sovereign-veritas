# GPU-2 results: throttling the Adreno 830 to half its clock did not change a single reply byte

Registration: [`GPU2_PREREG.md`](GPU2_PREREG.md), `1a51f7e`, committed before the probe existed. Probe:
`tools/gpu2_probe.py` at `52c386d`. Run by Chad Holland on the **Samsung Galaxy S25 Ultra** (Termux,
`llama-server-adreno`, Qualcomm OpenCL), 2026-10-04 at about 14:15 CT. Model: `llama-3.2-3b.gguf`, sha256
`6c1a2b41161032677be168d354123594c0e6e67d2b9227c84f296ad037c728ff`.

Drafted by Claude (Opus 5.5), which wrote the registration and the probe, at Chad Holland's direction. Chad ran
it on the phone and has not reviewed this text line by line.

## What to know first

- **"Cold" was not cold.** The phone started at 52.3 °C, and the GPU temperature passed 80 °C in the first
  request and reached 96.9 °C in the fifth. As registered, "cold" means the start of the run. What the run
  actually compares is **unthrottled (1200 MHz, `thermal_pwrlevel` 0)** against **throttled (525–660 MHz,
  `thermal_pwrlevel` 8–9)**.
- **The heat phase was almost empty.** Throttling began after 2 long generations (6 s), because the cold phase
  had already heated the GPU.
- **`throttling` never left 0.** Only `thermal_pwrlevel` and the clock showed the throttle. A check that relied
  on `throttling` alone would have missed it.
- **The GPU offload line was not found in the server log.** Step 4's grep for `GPUOpenCL|offload` printed
  nothing. GPU use rests on P4: busy 96–97 % and the clock rising to 1200 MHz during requests.
- **The answer is wrong both times.** 7338 × 5099 = 37,416,462. The model gives
  `37, 191, 502, 722, 000, ...` at temperature 0, and `37311922` in the control. This experiment tests whether
  the reply is **stable**, not whether it is correct.
- The run log `~/gpu2_run.json` stays on the phone and is not in the repository.

## Output (verbatim, line breaks restored)

```
START  model /data/data/com.termux/files/home/llama-3.2-3b.gguf  file sha256 6c1a2b41161032677be168d354123594c0e6e67d2b9227c84f296ad037c728ff  temp 52300  clock 222  pwrlevel 0
cold    1  a01b977adab9  clock 222-1200 MHz  busy max 51%  temp max 80.7C  throttling max 0  pwrlevel max 0  reply '37, 191, 502, 722, 000, 000, 000, 000, 0'
cold    2  a01b977adab9  clock 1200-1200 MHz  busy max 97%  temp max 86.9C  throttling max 0  pwrlevel max 0  reply '37, 191, 502, 722, 000, 000, 000, 000, 0'
cold    3  a01b977adab9  clock 1200-1200 MHz  busy max 97%  temp max 90.3C  throttling max 0  pwrlevel max 0  reply '37, 191, 502, 722, 000, 000, 000, 000, 0'
cold    4  a01b977adab9  clock 1200-1200 MHz  busy max 97%  temp max 95.3C  throttling max 0  pwrlevel max 0  reply '37, 191, 502, 722, 000, 000, 000, 000, 0'
cold    5  a01b977adab9  clock 1200-1200 MHz  busy max 96%  temp max 96.9C  throttling max 0  pwrlevel max 0  reply '37, 191, 502, 722, 000, 000, 000, 000, 0'
HEAT   2 long generations, 6 s, throttle seen: True
hot     1  a01b977adab9  clock 525-525 MHz  busy max 97%  temp max 65.3C  throttling max 0  pwrlevel max 9  reply '37, 191, 502, 722, 000, 000, 000, 000, 0'
hot     2  a01b977adab9  clock 525-525 MHz  busy max 97%  temp max 63.8C  throttling max 0  pwrlevel max 9  reply '37, 191, 502, 722, 000, 000, 000, 000, 0'
hot     3  a01b977adab9  clock 525-607 MHz  busy max 97%  temp max 63.8C  throttling max 0  pwrlevel max 9  reply '37, 191, 502, 722, 000, 000, 000, 000, 0'
hot     4  a01b977adab9  clock 607-607 MHz  busy max 97%  temp max 62.6C  throttling max 0  pwrlevel max 8  reply '37, 191, 502, 722, 000, 000, 000, 000, 0'
hot     5  a01b977adab9  clock 607-607 MHz  busy max 97%  temp max 64.6C  throttling max 0  pwrlevel max 8  reply '37, 191, 502, 722, 000, 000, 000, 000, 0'
control 1  9d11bfd1ba29  clock 607-660 MHz  busy max 97%  temp max 62.6C  throttling max 0  pwrlevel max 8  reply '37311922'
HELD                         P1
HELD                         P2
HELD                         P3
HELD                         P4
HELD                         P5
LOG    /data/data/com.termux/files/home/gpu2_run.json
```

## Outcome

| ID | Prediction | Result |
|---|---|---|
| P1 | 5 cold replies byte-identical | **HELD**: `a01b977adab9` ×5 |
| P2 | throttled state reached within 600 s | **HELD**: `thermal_pwrlevel` 9, clock 1200 → 525 MHz, after 6 s of heat |
| P3 | hot replies byte-identical to cold | **HELD**: `a01b977adab9` ×5 at 525–607 MHz |
| P4 | GPU busy ≥ 50 % during cold requests | **HELD**: 51–97 % |
| P5 | the control reply differs | **HELD**: `9d11bfd1ba29` |

On this phone, model and prompt, cutting the Adreno 830's clock to 44–51 % of maximum under thermal
throttling changed how fast the reply came, not what it said. This is a result for one model, one prompt and
one run. It does not cover other backends (Vulkan corrupted output on 2026-09-26) or the CPU.

The `temp` reading fell from 96.9 °C to about 63–65 °C within seconds of throttling. Which sensor `kgsl temp`
reports, and why it drops so fast, was not checked.

## Next unrun test

As registered: the same on the CPU (`--device none`), and a prompt the model answers correctly, so that any
change would turn a right action into a wrong one.
