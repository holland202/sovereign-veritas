# DIFF-001 results: the registered phone run stopped after about 30 minutes; P3 refuted (the overflow class, as expected), P2 held

**State:** REGISTERED RUN, STOPPED EARLY, scored against [PREREG.md](PREREG.md) as amended through A6 (launch
commit `ade8820`). Self-tested (M10).
**Authors:** Direction and device operation: Chad Holland. Design, scoring and write-up: Claude (Anthropic,
Opus 5.5). Human review level: the owner ran the phone commands and pasted the outputs used here. He had not
reviewed this write-up when it was committed.

## Failures first

1. **The run stopped after about 30 minutes, not at the deadline.** The window ran to 2026-10-23T12:00:00Z,
   roughly 14 hours. The last summary saves are at 21:05:23Z (worker3010, 1,835.7 s) and 21:05:07Z (worker3011,
   1,817.5 s). Both raw summaries read `"final": false`. Both stopped within the same 20,000-case
   save interval, so it is consistent with one event stopping both. Cause unknown. A6 records an `ollama serve`
   process alongside the workers at launch, and later evidence (LR-001) shows this phone stops long runs when it is
   off the charger. Neither is shown to be the cause here.
2. **P3 REFUTED, as amendment item 9 expected.** There are 8,906 K-I disagreements (4,572 + 4,334). Every one is a
   case where K and V raise `OverflowError` and I returns a decision. This is the OVF-1 class, which is fixed on
   main by PR #89. The code pinned here predates that fix. No other disagreement class appeared.
3. **The stop lost unwritten disagreement records.** The phone's disagreement files are byte-exact prefixes of the
   x86 reproduction's: 385 of 409 records for worker3010 and 382 of 410 for worker3011. The harness writes those
   records through a buffered file it never flushes until exit. The kill that stopped the run dropped what was still
   in the buffer. Its summaries are unaffected, because they are rewritten atomically every 20,000 cases. Any later
   long run should flush each record as it is written.

## Correction (2026-10-24): the device is a Galaxy S23 Ultra, not an S23 FE

On 2026-10-24 the phone reported `ro.product.model` = **SM-S918U** (Galaxy S23 Ultra, US) and `ro.soc.model` =
**SM8550** (Snapdragon 8 Gen 2). It runs Android 16, with `nproc` 6. The owner confirmed this on the phone's About
screen. Amendment A6's "device name" deviation, and its statement that the device is a Galaxy S23 FE, were wrong.
"S23 FE" came from a hard-coded line in the phone's Termux start-up banner, not from the device. The same start-up
file launches `ollama serve` in the background with every new Termux session, so the `ollama serve` process that A6
saw beside the workers was part of the phone's normal setup. Its load during the run was not measured.

## Scoring

| ID | Prediction | Result |
|---|---|---|
| P1 | Both planted mutants are caught | HELD before the run (amendment item 4) |
| P2 | K and V never disagree during the registered run | **HELD on the cases run:** 0 K-V disagreements in 3,360,000 cases. Every signature has K and V both `ERROR:OverflowError` |
| P3 | K and I never disagree during the registered run | **REFUTED:** 8,906 K-I disagreements, all of the OVF-1 overflow class |
| P4 | Disagreements persist for inputs outside a single mutation grammar | NOT RUN (door) |

Following the interpretation rule, the disagreement says at least one implementation is wrong for these inputs. The
fault assignment, K and V crashing on a contract-typed number, comes from the separate source reading in OVF-1, not
from this run.

## Counts

From the phone's raw files ([s23_registered/raw/](results/s23_registered/raw/), unedited, with
[SHA256SUMS](results/s23_registered/raw/SHA256SUMS)). The owner transferred them as one archive (SHA-256
`4ed42505…49e2`) on 2026-10-24. They match the owner's earlier paste
([owner_paste_summaries.txt](results/s23_registered/owner_paste_summaries.txt)) and show `"final": false` for both
workers:

| Worker | Cases | ALLOW | DEFER | REFUSE | ERROR (K) | K-I = V-I disagreements | Python | Seconds |
|---|---|---|---|---|---|---|---|---|
| worker3010 | 1,740,000 (sum of the four decision counts) | 77,601 | 488,350 | 1,169,477 | 4,572 | 4,572 (sum of the 28 signature counts) | 3.14.8 | 1,835.7 |
| worker3011 | 1,620,000 | 72,400 | 455,191 | 1,088,075 | 4,334 | 4,334 | 3.14.8 | 1,817.5 |

Every kernel ERROR is a disagreement case, and every disagreement case is a kernel ERROR. There are 28 signatures
for worker3010 and 31 for worker3011. They vary only in I's first reason, because the signature records I's
reason next to K's and V's shared error.

## Cross-device reproduction (exact)

The same index ranges and case counts were re-run in a Linux x86 container (Python 3.13.17) at the A5 code. The
runs used `itertools.islice(range(start, …, 2), cases)` passed to `diff_fuzz.run`, from starts 3010 and 3011.
- Every summary field except timing (`seconds`, `utc`, `python`, `final`) is identical to the phone's raw summary:
  the decision counts, the disagreement counts and **all 59 signatures with their counts**.
- The reproduction summaries are
  [x86_repro_worker3010.summary.json](results/s23_registered/x86_repro_worker3010.summary.json) and
  [x86_repro_worker3011.summary.json](results/s23_registered/x86_repro_worker3011.summary.json). Their
  `"final": true` belongs to the reproduction, which stops at the case count; it says nothing about the phone run.
- The match also confirms the phone ran with stride 2 from 3010 and 3011, as A5 says.
- Prediction stated in chat before running: identical counts if the stride was 2, credence about 0.75.

## What this supports (C-DESIGN)

- At the pinned pre-OVF-1 code, the only K-I disagreement class in 3.36 million generated cases from indices 3,010
  upward is the overflow crash already fixed by PR #89.
- The harness is deterministic across devices: aarch64/Android/Python 3.14.8 and x86/Linux/Python 3.13.17 give
  identical results case for case at the summary level.
- The follow-on runs on fixed main, which found 0 disagreements, are in [BT-001](../../docs/BT001_RESULTS.md) and
  LR-001 (PR #93).
