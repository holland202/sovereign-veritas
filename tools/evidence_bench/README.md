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

| model (Q4_K_M) | accuracy | unsafe accept | beats controls |
|---|---|---|---|
| Qwen2.5-1.5B-Instruct | 33.3% | 40.0% | no |
| LFM2.5-1.2B-Instruct | 25.6% | 86.7% | no |
| Qwen3.5-2B | 53.8% | 26.7% | narrowly |
| always NOT_SUPPORTED | 46.2% | 0% | — |

## Files
| file | what it does |
|---|---|
| `make_cases.py` | builds `cases.jsonl` deterministically |
| `oracle.py` | re-derives every gold label from hidden structure; exits 1 on any mismatch |
| `prompt.py` | the exact system prompt, rendering, and label parser |
| `run_bench.py` | starts `llama-server`, runs all cases, writes resumable JSONL + manifest (model SHA-256, prompt-set SHA-256, llama.cpp build, threads, seed) |
| `score.py` | accuracy, unsafe-accept, constant baselines, shuffled-gold control, rep determinism |

Stdlib Python only. No GPU/NPU claims: every run is CPU and the manifest says so.

## Reproduce on a phone (Termux), one command at a time

```
pkg install python git llama-cpp
```
If `llama-cpp` is not in your Termux repo, build llama.cpp from source instead.

```
cd ~/sovereign-veritas
```
```
git fetch origin bench/evidence-boundary-pilot
```
```
git checkout bench/evidence-boundary-pilot
```
```
mkdir -p ~/models
```
```
curl -L -o ~/models/LFM2.5-1.2B-Instruct-Q4_K_M.gguf https://huggingface.co/LiquidAI/LFM2.5-1.2B-Instruct-GGUF/resolve/main/LFM2.5-1.2B-Instruct-Q4_K_M.gguf
```
```
sha256sum ~/models/LFM2.5-1.2B-Instruct-Q4_K_M.gguf
```
Must print `b1b3de114215d9507409a662a501a631095a479a419584e8a2ded6304b19b4f5`. A size check is
not enough on Android (null-byte downloads have the right size).

```
termux-wake-lock
```
```
cd ~/sovereign-veritas/tools/evidence_bench
```
```
python run_bench.py --model ~/models/LFM2.5-1.2B-Instruct-Q4_K_M.gguf --label s25 --threads 6
```
If Android kills the run, re-run the same command: finished cases are skipped.

```
python score.py s25
```

The other two models (same pattern):

| file | Hub repo | SHA-256 |
|---|---|---|
| `qwen2.5-1.5b-instruct-q4_k_m.gguf` | `Qwen/Qwen2.5-1.5B-Instruct-GGUF` | `6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e` |
| `Qwen_Qwen3.5-2B-Q4_K_M.gguf` | `bartowski/Qwen_Qwen3.5-2B-GGUF` | `57a1085840f497d764a7fc5d346922dbde961efb54cc792ea81d694fd846a1d8` |

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
cd ~/sovereign-veritas/tools/evidence_bench
```
```
hf upload holland202/sovereign-evidence-bench . . --repo-type dataset --exclude "*.server.log" --exclude "__pycache__/*"
```
