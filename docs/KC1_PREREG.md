# KC-1 registration: a reused idempotency key with changed action parameters (nothing built or run under this registration)

Status: registration only. Written 2026-10-22, before `tools/kc1_probe.py` exists and before any case below has
been run. Baseline: main `db640a2` (544 passed, 1 skipped, Linux container, Python 3.13, run against this
checkout's own package). Claude-assisted (Claude Opus 5.5). Chad Holland gave direction. He has not reviewed this
text line by line. The merge decision is his.

## Origin

Joe Krausz (`draft-krausz-verification-state-03`) suggested this test on 2026-10-22, in reply to
[`RELYING_PARTY_NOTE.md`](RELYING_PARTY_NOTE.md): the same intent key comes back with changed action parameters, so
that a **conflicting reuse** can be told apart from a **plain duplicate**. RK-2 and MP-1 only ever reused a key
with the same action. This registration covers the executor's reservation store, which is the only place this code
reads an intent key. The relying-party consumer (`tools/consumer.py`) reads no key at all, and `make_package.py`
passes none (RELYING_PARTY_NOTE section 2), so the consumer is out of scope here.

## What the code does now (read from the code, not run)

- `reserve(key, lease_s)` in `sovereign_veritas/idempotency.py` takes only the key. Neither store keeps anything
  about the action the key was reserved for.
- A refusal is `ReservationRefused(f"idempotency key {key!r} is {state}: refused before execution")`. The message
  depends only on the key and its state.
- `EvidenceWorkflow.run` calls `reserve` after the Gate decides ALLOW and before `execute`. A refused reservation
  raises out of `run` before any record is written for that attempt.
- On success, the record carries the key (`metadata.idempotency_key`) and the executed action, parameters included.

## The probe (to be built after this commit)

`tools/kc1_probe.py`: the counting executor from XB-1/RK-1 (effects counted at the executor), `EvidenceWorkflow`
with a ledger sink, all runs ALLOW, one key `K`. Every case runs twice, once with `MemoryReservations` and once with
`FileReservations` on a fresh temporary directory.

| case | key state before the attempt | attempt |
|---|---|---|
| K0 | none | `K`, action `measure`/`record_result`, parameters `{"amount": 1}`, record_id `r0`. This sets the key up |
| D1 | COMPLETED (after K0) | **plain duplicate:** `K`, the same action and parameters, fresh record_id `r1` |
| C1 | COMPLETED (after K0) | **conflicting reuse:** `K`, the same action, parameters `{"amount": 2}`, fresh record_id `r2` |
| C2 | COMPLETED (after K0) | **conflicting reuse:** `K`, a different `requested` (`record_other`), parameters `{"amount": 1}`, record_id `r3` |
| D3 / C3 | IN_FLIGHT: `K2` reserved directly with a 60 s lease and never completed, standing for a holder that took the key for parameters `{"amount": 1}` and has not finished | D1's and C1's attempts against `K2` |
| D4 / C4 | UNKNOWN: `K3`'s first run, with parameters `{"amount": 1}`, raised in the executor | D1's and C1's attempts against `K3` |

For each attempt the probe records: effects added, the exception type, the exact exception message, records added
to the ledger, and the key's state and history before and after.

## Predictions

| ID | Prediction | conf. | Precisely wrong if |
|---|---|---|---|
| KC-P1 | **Safety.** Every D and C attempt adds **0 effects** and raises `ReservationRefused`, for both stores. K0 adds exactly 1 effect | 0.9 | any attempt adds an effect, or any refusal has another type |
| KC-P2 | **The gap Joe asked about (expected).** In each key state, the conflicting reuse is **indistinguishable** from the plain duplicate at refusal time: same exception type and a byte-identical message (C1 = D1, C2 = D1, C3 = D3, C4 = D4) | 0.9 | any pair differs in type or message |
| KC-P3 | **No trace afterwards.** No D or C attempt adds a ledger record or changes its key's history. For `K`, only K0's record exists, carrying `idempotency_key: K` and parameters `{"amount": 1}`. So the conflicting attempt cannot be recovered from the ledger or the store after the fact | 0.75 | any record or history entry appears for a D or C attempt |
| KC-P4 | **Anti-vacuity for KC-P2.** `--mutant tagged-refusal` patches the refusal message to include a per-call counter. The probe must then report KC-P2 **REFUTED** and exit 1. This shows the comparison can see a difference when one exists | 0.9 | the mutant run still reports KC-P2 held |
| KC-P5 | **Anti-vacuity for KC-P1.** `--mutant accept-all` swaps in a store whose `reserve` never refuses. The probe must then report KC-P1 **REFUTED** (at least one attempt adds an effect) and exit 1 | 0.9 | the mutant run still reports KC-P1 held |
| KC-P6 | **Regression.** No source file under `sovereign_veritas/` changes. The suite stays at 544 passed, 1 skipped | 0.95 | any change to that count |

**Outcome rule, fixed now:** each prediction is HELD or REFUTED by the probe's own exit logic, and the results file
quotes its output verbatim. KC-P2 holding is **not** a pass for the code. It confirms the gap: the store refuses a
conflicting reuse (fail closed), but it says the same thing it says for a harmless retry, and it keeps no record of
the attempt.

## Trigger table (CONTROLS.md)

| Trigger | Answer |
|---|---|
| C-FEAS | 10 runs per store (3 setups, 7 attempts); seconds to run |
| C-NOISE | none expected: the stores and executor are deterministic, and messages are compared byte for byte |
| C-STAT | no rates; every prediction is about specific cases |
| C-INDEP | self-tested: the same author (with Claude) wrote the code, this registration and the probe. Joe Krausz proposed the question, not the cases |
| C-EXT | Joe Krausz's suggestion, paraphrased above; no outside code |
| C-DEVICE | Linux container only. **Not run on the S25.** `FileReservations` on Android storage is untested |
| C-BUILD | the probe exits 1 if any prediction is refuted; KC-P4 and KC-P5 show it can |
| C-EXPLORE | nothing has been run under this registration |

## What it cannot show

- Anything about the relying-party consumer, which reads no key.
- Whether a caller *should* be told "conflict" rather than "duplicate". KC-1 only measures whether this code can
  tell them apart.
- Concurrency. A conflicting reuse racing the first reservation is not covered (MP-1 covers same-action races).
- Behaviour across machines, on network filesystems, or on the phone.

## Door (unrun)

**KC-2:** bind the intent to the key. Store a digest of the canonical decided action with the reservation at
`reserve` time, and refuse a mismatch with a distinct `CONFLICT` reason. Then rerun KC-1 with KC-P2 flipped (each C
message differs from its D) and KC-P1 unchanged. Where that change belongs, the public v0.2 line or the
development line, is the owner's decision.
