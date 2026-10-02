# REVIEW_LOG — outside reviews and what was done with them

On 2026-10-02 Chad Holland asked five AI systems to review the published version of this
bench (Hub revision `fb80b2d`): **ChatGPT, Grok, Perplexity, Gemini and Copilot**. Each review
was treated as a set of claims to check, not as a verdict. A review counts as evidence only
after its claim has been checked against the files, the Hub, or a rerun.

The review texts belong to the person who requested them and are not reproduced here. A claim
is attributed to a named reviewer only where the attribution is certain. Everything else is
marked "a review".

## Claims that were checked and found false

| claim | source | check | disposition |
|---|---|---|---|
| The raw model outputs are not published | Gemini | `results/container/*.jsonl` and `results/container/decomposed/*.jsonl` hold every raw output (312 direct rows, 296 item answers). The dataset viewer shows them. | **false**; no change needed |
| The account has 8 Spaces | a review, reading a profile screenshot | The Hub lists 0 Spaces for `holland202`. The "8" was the Spaces icon, misread in a text copy of the screenshot. | **false** |
| The REFUTED collapse is a fine-tuning flaw in the models | a review | The same models, asked a narrower question in the decomposed arm, produced REFUTED in up to 10 of 12 gold-REFUTED cases (Qwen3.5-2B and Qwen2.5-1.5B). The collapse depends on the question format, so it cannot be only a property of the weights. | **contradicted by the data**; kept as a hypothesis about the *direct* format only |

## Claims that could not be verified

| claim | source | check | disposition |
|---|---|---|---|
| Comparable prior benchmarks named "SovereignPA-Bench" and "OE-EV-2026-01" exist | a review | Hub search on 2026-10-02 found neither. | **not found**; not cited |

## Claims that were checked and acted on

| claim or suggestion | check | what changed |
|---|---|---|
| The published percentages should be recomputable from the raw logs | They are. Rebuilding them exposed six problems in the earlier write-ups. | `analyze.py`, `STATS.md`, `verify_claims.py`; dated correction notes in `RESULTS.md` and `RESULTS_A1_A2.md` |
| A similar project, "sovereign evidence observatory", exists | It does: `Thorsu/sovereign-evidence-observatory` (dataset and Space, Apache-2.0). | Cited as related work in `README.md`, with no priority or novelty claim |
| The dataset card lacks an abstract, a schema, links to the code and preregistrations, a replication status and a citation | Correct. | `README.md` rewritten; viewer configs added for the held-out cases and a derived predictions table |
| Results on 39 cases that the follow-ups were designed after cannot show generalisation | Correct, and already listed as an open door in `RESULTS_A1_A2.md`. | H1: 110 new cases, preregistered (`PREREG_H1.md`) before any H1 output |
| The tools themselves should be tested | Building the tests found a real defect: the gate reads an unreadable answer as "no opinion" (`STATS.md` item 7). | `tests/`, `mutate.py`, `gate_strict.py` |

## Problems found while acting on the reviews (not raised by any reviewer)

These are listed in full in `STATS.md`:

- the output parsers failed open
- the Monte Carlo control depended on which other result files existed
- the registered unanimous-consensus rule can delete a refutation
- the gate fails open on unreadable answers
- the speed columns did not measure throughput
- one of my own claims ("decomposition made the 4B less safe") was stronger than the data, and is withdrawn

The reviews prompted the re-analysis, but most of what changed was found by re-running the
numbers, not by reading the reviews. Both are recorded here because both are how this bench
got better.
