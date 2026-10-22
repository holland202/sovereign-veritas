# DIFF-001: do three sv.gate/0 implementations decide alike beyond the published vectors?

**State:** REGISTERED, NOT RUN. Committed before the harness has been executed even once, and before any generated case has been observed.
**Authors:** Direction: Chad Holland (2026-10-22). Design and harness: Claude (Anthropic, Opus 5.5). Human review level: direction only. Everything run here is **self-tested** (M10).

**The independent implementation under test** is by Putluru Sandeep (@sunny-kavixo, SV PR #86, head `4fddb8b`). This branch is that head plus a merge of `main` (`3ff59ef`). Before writing this file, its source was read in full: a pure function plus a stdin/stdout line runner, with no network, file or subprocess use.

**Prior fact, observed while writing this registration** (a re-run of a check the contributor had already reported): `python3 tools/gate_contract.py --check-command python3 ports/python_independent/independent_gate.py` → `VERDICT CONFORMS`, digest `44823d0f…0628`. This reproduces the contributor's reported 4,690/4,690 result on this merged tree.

## Question

The published 4,690 vectors show that the kernel Gate (K), the package verifier's `replay_gate` (V) and Sandeep's independent port (I) agree on those inputs. **Do they still agree on many more inputs** that stay inside the contract's declared types but were never published?

## Instrument

[`diff_fuzz.py`](diff_fuzz.py). Case *i* is generated deterministically from seed 20261022 and *i*:
- start from a random published vector;
- apply 1 to 6 type-preserving mutations: statuses, truthy-ish values, numbers including -0.0, 0.49999, 1.00001, 1e300 and 10**400, step counts, parents, registries, runtime words and policy lists;
- keep registry keys equal to entry names, so the kernel adapter's by-name registration cannot create artificial disagreements.

Each implementation gets a deep copy of the case. Its outcome is `(decision, reasons)`, or `("ERROR", exception type)`. A disagreement is any case where the three outcomes are not identical, reasons and their order included. Any disagreement can be re-generated with `--replay INDEX`.

## Predictions

| ID | Prediction | Credence | Precisely wrong if |
|---|---|---|---|
| **P1 (anti-vacuity)** | Each of two planted mutants of I (`steps-ge`: `>` becomes `>=`; `insufficient-is-pass`: the INSUFFICIENT_EVIDENCE reason is dropped) produces at least one K-I disagreement within 100,000 cases. `--mutant` exits 0 only if it does | high | either mutant survives 100,000 cases |
| **P2** | K and V (same author) never disagree during the registered run | high (about 0.85) | any K-V disagreement |
| **P3** | K and I never disagree during the registered run | **uncertain (about 0.5)** | any K-I disagreement. The likeliest sources are number formatting inside reason strings (`repr`, `:.4f`), overflow at 10**400 and type edges |
| P4 (door, unrun) | Disagreements found here persist when the inputs come from outside a single mutation grammar | — | — |

**Interpretation rule, fixed now:** a disagreement shows that **at least one** implementation, or the contract text, is wrong or ambiguous for that input. It does **not** say which one is wrong. Assigning fault needs a separate source reading per signature, reported case by case.

## Run plan

- **Smoke check here (Linux container):** P1 with both mutants (100,000 cases each), plus a 2,000-case unmutated run that checks the harness works. These numbers are reported, not hidden.
- **Registered run:** one new Azure VM (Central US), 2 workers (interleaved indices), from start until **2026-10-22T20:30:00Z** (15:30 CDT). The total case count is whatever fits; no count is promised.
- Outputs: per-worker summary JSON and up to 1,000 full disagreement records per worker.

## Trigger table (M16)

| Trigger | Control | Answer |
|---|---|---|
| Feasibility | C-FEAS | yes: throughput unknown, so only existence predictions are made |
| Noise | C-NOISE | no: the implementations are deterministic, cases are seeded, and any case replays exactly |
| Statistics | C-STAT | no rates claimed; P2/P3 are "no disagreement in the cases actually run" |
| Evidence | C-EVID | n/a: the gates' evidence semantics are what is under test, not the harness's |
| Independence | C-INDEP | yes: I is by a different author than K and V. The harness is by Claude, a third party to I and not to K/V's tooling. Self-tested |
| External | C-EXT | yes: contributor code from SV PR #86, read in full before running |
| Device | C-DEVICE | yes: Azure ARM64 Ubuntu 24.04 VM (Python 3.12). Container smoke on x86 Python 3.13 |
| Verdict code | C-BUILD | yes: `--mutant` exits 1 if the harness fails to catch a planted defect |
| Exploration | C-EXPLORE | no run of any kind before this commit |
| Method comparison | C-METHCOMP | no |

## Amendments and disclosed smoke observations (appended before the registered run; C-EXPLORE)

1. **Smoke 1** (original generator, 2,000 cases, Linux x86, Python 3.13): decisions **1,990 REFUSE / 10 DEFER / 0 ALLOW**, 0 disagreements. The generator almost never reached the ALLOW/DEFER paths, because 4,616 of the 4,690 base vectors are REFUSE and the mutations mostly broke inputs.
2. **Amendment A1 (generator).**
   - Each mutation now picks a contract-valid value 85% of the time.
   - 70% of cases start from one of the 74 non-REFUSE vectors.
   - 1 to 4 mutations per case, instead of 1 to 6.
3. **Smoke 2** (A1, 2,000 cases): decisions 89 ALLOW / 572 DEFER / 1,336 REFUSE / 3 ERROR. **3 disagreements, all one class:**
   - `min_evidence_quality = 10**400` (a valid JSON number) makes **K and V raise `OverflowError`**;
   - I returns DEFER with reason `evidence_quality_below_threshold:…<inf`.
   - So P3 is effectively refuted before the registered run. It will still be scored on the registered run, as registered. The kernel crashing on a contract-typed number is a candidate defect in K and V, reported separately with source analysis.
4. **P1 (anti-vacuity) on A1:** `steps-ge` → 1,307 K-I disagreements in 100,000 cases; `insufficient-is-pass` → 7,799. Both mutant runs exit 0. **P1 HELD.**
5. **Amendment A2 (recording only; the generator is unchanged).**
   - Save up to 20 examples **per disagreement signature**, so the frequent overflow class cannot fill the record and hide rarer classes.
   - The summary now lists all signatures, not just the top 25.
   - Made after smoke 2 showed one dominant class.
6. **Smoke 3** (A1+A2, 3,000 cases, which include smoke 2's 2,000 indices): 9 disagreements, all K-I/V-I, with K and V raising errors (9 kernel ERROR outcomes). `steps-ge` re-check on 20,000 cases: caught (exit 0).
7. **Reproductions for the owner-requested #86 review** (2026-10-22 ~15:20Z, outputs in [results/reproductions_2026-10-22.txt](results/reproductions_2026-10-22.txt), helpers in [repro/](repro/)):
   - the contract pin `d3a9a881` is blob-identical to `main` for CONTRACT.md, the vectors and the checker;
   - the #86 port conforms (digest `44823d0f…`);
   - the always-ALLOW control is rejected (4,675/4,690 differ);
   - #86's 22 hand-derived boundary cases pass against the port, the kernel and the verifier.

   Smoke-2 and mutant summaries are in [results/](results/).
8. **Amendment A3 (schedule).** The Azure run could not start before 20:30Z: regional core quota was exhausted in Central US and West US 2. The registered run will start later, and the `--until` deadline is given in the launch command and recorded here before results are read. The predictions are unchanged.
9. **Follow-up.** The overflow class from smoke 2/3 became OVF-1: registered, fixed and tested in sovereign-veritas PR #89. Against the fixed K/V, this harness found 0 disagreements in 3,000 cases (OVF-1 R7). P2/P3 in the registered run stay scored against the code at this branch's pinned commit. That code does **not** include the OVF-1 fix, so the overflow class is expected to recur there.
