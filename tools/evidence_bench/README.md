---
license: mit
pretty_name: Sovereign Evidence-Boundary Bench
task_categories:
- text-classification
language:
- en
tags:
- evaluation
- llm-safety
- prompt-injection
- provenance
- on-device
- llama.cpp
- gguf
size_categories:
- n<1K
configs:
- config_name: cases
  data_files: cases.jsonl
- config_name: container_results
  data_files: results/container/*.jsonl
- config_name: container_decomposed
  data_files: results/container/decomposed/*.jsonl
---

# evidence_bench — evidence-boundary benchmark for small local models

Can a small local language model hold an **evidence boundary** — admissibility, provenance,
freshness, injection resistance — or does it just pattern-match on whether the evidence
mentions the claim?

39 hand-built cases, 11 categories, three verdicts (SUPPORTED / REFUTED / NOT_SUPPORTED).
Gold labels are derived mechanically by `oracle.py` from hidden structure, and the run is
preregistered (`PREREG.md`, committed before any model output).

**First result (container, not phone):** two of three 1–2B models are indistinguishable from
chance, almost nobody uses REFUTED, and LFM2.5-1.2B obeyed injected instructions 4 of 4 times.
Full numbers and the failures: [`RESULTS.md`](RESULTS.md).

Direct arm (one model call decides) vs decomposed arm (model labels each admissible
item TRUE/FALSE/NEITHER; deterministic `gate.py` decides). Container only.

| model (Q4_K_M) | direct acc | direct unsafe | decomposed acc | decomposed unsafe |
|---|---|---|---|---|
| Qwen2.5-1.5B-Instruct | 33.3% | 40.0% | 56.4% | 13.3% |
| LFM2.5-1.2B-Instruct | 25.6% | 86.7% | 59.0% | 30.0% |
| Qwen3.5-2B | 53.8% | 26.7% | 74.4% | 3.3% |
| Qwen3.5-4B | 61.5% | 16.7% | 71.8% | 23.3% |
| always NOT_SUPPORTED | 46.2% | 0% | — | — |

The 4B row is the warning: decomposition made it *less* safe. All four rows come from the
same 39 cases the follow-ups were designed after; see [`RESULTS_A1_A2.md`](RESULTS_A1_A2.md).

> A model's benchmark performance does not authorize the model to act as the evidence
> boundary. This experiment evaluates whether model *proposals* can be safely constrained by
> an independent deterministic gate (Sovereign Veritas); it does not validate that architecture.

## Status and scope

- **Container-only. NOT VALIDATED on the S25 Ultra.** No phone run exists yet (prediction P7 is unrun).
- CPU only, x86_64, 2 threads, llama.cpp `b1-bed0a85`. No GPU or NPU offload.
- Temperature 0, seed 0, max 16 tokens, 2 repetitions per case. Outputs were identical
  across repetitions for all three models.
- Preregistration commit `1ae3cb6`, made in a local working repo before any model output.
  It was not publicly timestamped, so the ordering is stated, not proven.
- **Follow-ups A1 (Qwen3.5-4B) and A2 (decomposed arm)** were preregistered and pushed before their runs, but designed after v0, on the same 39 cases. Results: `RESULTS_A1_A2.md`.
- **Model roles.** Qwen3.5-2B Q4_K_M is the *candidate selected for the next evaluation*. It
  is not "the best model": it beats the constant baseline by 3 of 39 cases. Qwen2.5-1.5B
  Q4_K_M is the prior baseline. LFM2.5-1.2B Q4_K_M is a comparison model. Model weights are
  not included; the hashes are below.
- **REFUTED collapse.** Across 36 gold-REFUTED predictions (12 cases × 3 models), REFUTED was
  produced once. The Qwen models answer NOT_SUPPORTED; LFM2.5 answers SUPPORTED.
- **Injection.** LFM2.5-1.2B's answer matched the injected label on 4 of 4 injection cases,
  Qwen2.5-1.5B on 2 of 4, and Qwen3.5-2B on 1 of 4.
- **Known instrument defect (provenance confound).** Provenance scored highest (3/4, 4/4, 4/4),
  but 3 of the 4 provenance cases have NOT_SUPPORTED as gold, which the Qwen models answer by
  habit. This set cannot yet separate "rejected the unverified source" from "abstained anyway".
  See `RESULTS.md`.
- `SHA256SUMS` covers every file in this package.

## Files
| file | what it does |
|---|---|
| `make_cases.py` | builds `cases.jsonl` deterministically |
| `oracle.py` | re-derives every gold label from hidden structure; exits 1 on any mismatch |
| `prompt.py` | the exact system prompt, rendering, and label parser |
| `run_bench.py` | starts `llama-server`, runs all cases, writes resumable JSONL + manifest (model SHA-256, prompt-set SHA-256, llama.cpp build, threads, seed) |
| `score.py` | accuracy, unsafe-accept, constant baselines, shuffled-gold control, rep determinism |
| `gate.py` | deterministic gate for the decomposed arm; `python gate.py` runs its controls |
| `run_decomposed.py` | decomposed arm: per-item stance extraction, gate decides |
| `score_a2.py` | direct vs decomposed comparison, incl. the 34 model-dependent cases |

Stdlib Python only. No GPU/NPU claims: every run is CPU and the manifest says so.

## Reproduce on a phone (Termux), one command at a time

```
pkg install python git llama-cpp
```
If `llama-cpp` is not in your Termux repo, build llama.cpp from source instead.

Download this dataset (it contains `cases.jsonl`). If you work from the GitHub branch
`bench/evidence-boundary-pilot` instead, regenerate the cases first: that repo's `.gitignore`
excludes `*.jsonl`. The output is byte-identical (SHA-256 `76714497…9e19`).

```
python make_cases.py
```
```
mkdir -p ~/models
```
```
curl -L -o ~/models/Qwen_Qwen3.5-2B-Q4_K_M.gguf https://huggingface.co/bartowski/Qwen_Qwen3.5-2B-GGUF/resolve/main/Qwen_Qwen3.5-2B-Q4_K_M.gguf
```
```
sha256sum ~/models/Qwen_Qwen3.5-2B-Q4_K_M.gguf
```
Must print `57a1085840f497d764a7fc5d346922dbde961efb54cc792ea81d694fd846a1d8`. A size check is
not enough on Android (null-byte downloads have the right size).

```
termux-wake-lock
```
```
cd ~/sovereign-evidence-bench
```
```
python run_bench.py --model ~/models/Qwen_Qwen3.5-2B-Q4_K_M.gguf --label s25 --threads 6
```
If Android kills the run, re-run the same command: finished cases are skipped.

```
python score.py s25
```

The candidate (Qwen3.5-2B) is shown above. The other two models follow the same pattern:

| file | Hub repo | SHA-256 |
|---|---|---|
| `qwen2.5-1.5b-instruct-q4_k_m.gguf` | `Qwen/Qwen2.5-1.5B-Instruct-GGUF` | `6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e` |
| `LFM2.5-1.2B-Instruct-Q4_K_M.gguf` | `LiquidAI/LFM2.5-1.2B-Instruct-GGUF` | `b1b3de114215d9507409a662a501a631095a479a419584e8a2ded6304b19b4f5` |

A hash match proves you have the file the Hub serves. It does not prove who made it — the
Qwen3.5 file is a third-party quantization.

## Credits
Chad Edward Holland — direction, research program. Claude (Opus 5.5, Anthropic) — case set,
harness, container run. Experimental framing drew on a plan drafted with ChatGPT.

## Publish to Hugging Face (from Termux)

Create a **write** token at huggingface.co/settings/tokens. Type it only into Termux, never into a chat.

```
pip install -U huggingface_hub
```
```
hf auth login
```
```
cd ~/sovereign-evidence-bench
```
```
sha256sum -c SHA256SUMS
```
```
hf upload holland202/sovereign-evidence-bench . . --repo-type dataset --exclude "results/s25/*.server.log"
```
