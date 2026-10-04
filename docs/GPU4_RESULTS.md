# GPU-4 results: same words, different numbers. CPU and Adreno agree on every chosen token but not on the probabilities

Registration: [`GPU4_PREREG.md`](GPU4_PREREG.md), `bb298c6`. Tool `tools/gpu4_probs.py`, `1b4b6bc`. Run by Chad
Holland on the S25 Ultra, 2026-10-04, about 14:45 CT. Model `llama-3.2-3b.gguf` (sha256 `6c1a2b41…28ff`, as in
GPU-2/3). Both servers ran with `-c 2048 -np 1`.

Drafted by Claude (Opus 5.5) at Chad Holland's direction. Chad ran it on the phone and has not reviewed this text
line by line.

## What to know first

- **P4 is REFUTED, and by a lot.** I predicted the largest log-probability difference would be under 0.05. It
  was **0.889977**, for the token `' **'` at the first generated position of the hard prompt. That token was not
  the one chosen. It is an alternative in the top 10, and its probability differs by a factor of about 2.4
  (e^0.89) between the CPU and the GPU.
- **The GPU-busy check is weaker than it looks.** The tool judged P5 on the highest busy reading across all four
  GPU requests (86 %). Per request it was 0, 48, 48 and 86 %. These requests are short (8 tokens), and the 0.1 s
  sampler can miss most of one. Indirect evidence that the GPU did the work: each backend repeats its own numbers
  exactly (P1), yet the two backends' numbers differ (P3).
- The raw JSON (`~/gpu4_gpu.json`, `~/gpu4_cpu.json`) is on the phone, not yet in the repository.

## Output (verbatim)

```
gpu easy rep 1: 8 positions, kind logprob, busy max 0%, text ' 184\nQ: What is '
gpu easy rep 2: 8 positions, kind logprob, busy max 48%, text ' 184\nQ: What is '
gpu hard rep 1: 8 positions, kind logprob, busy max 48%, text ' 37, 191, 502'
gpu hard rep 2: 8 positions, kind logprob, busy max 86%, text ' 37, 191, 502'
SAVED /data/data/com.termux/files/home/gpu4_gpu.json
cpu easy rep 1: 8 positions, kind logprob, busy max 0%, text ' 184\nQ: What is '
cpu easy rep 2: 8 positions, kind logprob, busy max 0%, text ' 184\nQ: What is '
cpu hard rep 1: 8 positions, kind logprob, busy max 0%, text ' 37, 191, 502'
cpu hard rep 2: 8 positions, kind logprob, busy max 0%, text ' 37, 191, 502'
SAVED /data/data/com.termux/files/home/gpu4_cpu.json
easy: gpu tokens [' ', '184', '\n', 'Q', ':', ' What', ' is', ' ']
easy: cpu tokens [' ', '184', '\n', 'Q', ':', ' What', ' is', ' ']
hard: gpu tokens [' ', '37', ',', ' ', '191', ',', ' ', '502']
hard: cpu tokens [' ', '37', ',', ' ', '191', ',', ' ', '502']
busy max: gpu 86%, cpu 0%
largest |delta logprob| 0.889977 at ('hard', 0, ' **')
HELD     P1
HELD     P2
HELD     P3
REFUTED  P4
HELD     P5 (busy)
```

## Outcome

| ID | Prediction | Result |
|---|---|---|
| P1 | each backend repeats its own numbers exactly | **HELD** |
| P2 | CPU and GPU choose the same token at every position | **HELD**: 16 of 16 positions |
| P3 | some log-probability differs between them | **HELD**: the hypothesis from GPU-3's controls is supported |
| P4 | the largest difference is under 0.05 | **REFUTED**: 0.89, on a non-chosen alternative |
| P5 | instrument checks | **HELD as judged by the tool**, with the per-request weakness above |

## What it means

Within one backend, the computation repeats exactly. Across backends it does not. The CPU and the Adreno OpenCL
path give the same top choice at every position tested, so greedy (temperature-0) replies match. But the
probabilities underneath differ, and for an alternative token by a factor of about 2.4. At any temperature above
0, the two backends can therefore produce different text from the same seed, which is what GPU-3's controls
showed.

For evidence: **a matching temperature-0 reply does not show that two systems computed the same thing.** It
shows only that they agreed on the top choice at each step. The more often a reply comes close to a tie between
two tokens, the less that agreement says. A package that records only the reply text cannot tell these apart.

## Next unrun test

As registered: a second model (Qwen2.5-1.5B) and a CPU thread-count change. Added from this result: record the
margin between the top two tokens at each position, to see how close the agreement came to flipping.
