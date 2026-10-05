# FI: end-to-end failure injection against the real pipeline — registration

**Status: REGISTERED, UNRUN.** Committed alone, before `tools/fault_injection.py` exists. Not edited after this
commit; results go in `docs/FI_RESULTS.md`. Method: principia-artificialis `METHOD.md` at `646eed7`.
This is item 2 of Chad Holland's reliability priority queue (end-to-end failure-injection harness).

**Provenance:** AI participation → human validation → human editing/curation → human responsibility.
- **AI participation:** Claude (Anthropic, Sonnet 5.5).
- **Human review:** direction only (Chad Holland).
- **Responsibility:** Chad Holland. **Self-tested.** No independent human has reviewed it.

## Question

When a fault is injected at each seam of the real `EvidenceWorkflow` (sensor, predictor, verifier, registry,
runtime state, executor, evidence sink) and into the stored ledger, which of three invariants hold?

- **I-A (no unjustified action).** An external effect happens only after the gate has returned ALLOW.
- **I-B (no unrecorded effect).** Every external effect has a record in the ledger after a fresh reload.
- **I-C (truthful record).** A record's `execution_status` agrees with whether the effect happened.

And, for stored-ledger faults: is the fault detected on reload, or silently accepted?

The object counted is the **external effect** (a counting executor), not ledger rows. The code under test is
real: `EvidenceWorkflow`, `Gate`, `FileLedger`, `AnchoredFileLedger`. The faults are injected at the interface
seams (`sovereign_veritas/interfaces/contracts.py`) and in the files on disk.

## What was read before this registration (exploratory)

`workflow.py`, `decision.py`, `runtime.py`, `capability.py`, `verification.py`, `file_ledger.py`,
`anchored_file_ledger.py`, the interface contracts, and the structure of `tools/xb2_boundary_probe.py`. The
predictions below rest on that reading. Nothing was run. **Findings from reading, not yet observations:**
(1) `AnchoredFileLedger` has no `require_anchor` option (the v0.1 to v0.2 migration note describes one that is
not in the code); a missing anchor file returns silently. (2) The anchored ledger needs `fcntl`, so it does not
run on Windows.

## Cells (workflow faults). Predicted (effects, records after reload, outcome, recorded decision)

A cell uses a fresh ledger. "raised X" means the exception propagates out of `run()`.

| ID | Fault | Predicted |
|---|---|---|
| U0 | none; authorized capability, verifier PASS (anti-vacuity) | 1, 1, ok, ALLOW |
| U0r | none; capability not authorized (anti-vacuity) | 0, 1, ok, REFUSE |
| U1 | sensor raises RuntimeError | 0, 0, raised RuntimeError, none |
| U2 | predictor raises RuntimeError | 0, 0, raised RuntimeError, none |
| U3 | verifier raises RuntimeError | 0, 0, raised RuntimeError, none |
| U4 | verifier returns None | 0, 0, raised TypeError, none |
| U5 | verifier returns `{}` (no status) | 0, 1, ok, REFUSE |
| U6 | verifier returns `{"status": "pass"}` (wrong case) | 0, 1, ok, REFUSE |
| U7 | verifier PASS, authorized, but `input_digest = ""` | 0, 0, raised ValueError, none |
| U8 | runtime `thermal_status = "HOT!!"` (outside the vocabulary) | 0, 1, ok, REFUSE |
| U9 | prediction `uncertainty = NaN`, verifier PASS, authorized | 0, 0, raised ValueError, none |
| U10 | registry configured, `verifier_id` omitted | 0, 1, ok, DEFER |
| E1 | executor raises before any effect | 0, 1, raised RuntimeError, ALLOW with `execution_status = FAILED` |
| E2 | executor performs the effect, then raises (timeout) | 1, 1, raised RuntimeError, ALLOW with `execution_status = FAILED` |
| E3 | sink raises OSError on `record()` after the effect | 1, 0, raised OSError, none |
| E4 | process crash (a `BaseException`) after the effect, before the record | 1, 0, raised Crash, none |
| E4r | E4, then the same `record_id` is submitted again (recovery) | total effects 2, records 1 |

U9 is the least certain (confidence about 0.6): if NaN is accepted, the cell shows 1 effect, which would be a
finding. E1, E2, E3 and E4r repeat results already registered and measured in XB-1 (X5, X6) and XB-2 (C5, C6, P4);
they are here to exercise the same invariants in one harness, not as new findings.

## Cells (stored-ledger faults). Setup: 3 records written through the real workflow

| ID | Fault | `FileLedger` reload | `AnchoredFileLedger` reload |
|---|---|---|---|
| S1 | last line cut mid-JSON (torn write) | raises ValueError "invalid JSON at ledger index" | same |
| S2 | one character of record 1 changed | raises ValueError "tampered" | same |
| S6 | the last line appended a second time | raises ValueError "chain broken" | same |
| S3 | last line removed (truncation) | **loads, 2 records, undetected** | raises ValueError "truncated relative to anchor" |
| S4 | older copy restored (1 record) | **loads, 1 record, undetected** | raises ValueError "truncated relative to anchor" |
| S5 | last record replaced by a different, validly chained record | **loads, 3 records, undetected** | raises ValueError "mismatch against anchor" |
| S7a | anchor file deleted, ledger intact | n/a | **loads, 3 records, undetected** |
| S7c | anchor deleted **and** last line removed | n/a | **loads, 2 records, undetected** |
| S7b | anchor and ledger both deleted | n/a | **loads, 0 records, undetected** (documented limit) |
| S8 | ledger has 4 valid records, anchor says 3 (crash window) | n/a | loads, 4 records (documented behaviour) |

## Predictions

| ID | Prediction |
|---|---|
| FI-1 | **Anti-vacuity.** U0 and U0r produce exactly the tuples above. The harness can see an effect and can see none |
| FI-2 | **Fail closed upstream.** U1–U10 each produce exactly the tuples above, and every one has 0 effects (10 of 10) |
| FI-3 | **At the effect.** E1–E4 and E4r produce exactly the tuples above |
| FI-4 | **Invariants.** Over all workflow cells: I-A violated in **0** cells; I-B violated in exactly **{E3, E4}** (and E4r's first run); I-C violated in exactly **{E2}** |
| FI-5 | **Detected storage faults.** S1, S2, S6 raise on reload, with the messages above, for both ledgers |
| FI-6 | **Undetected on the plain ledger.** S3, S4, S5 load without error on `FileLedger` (2, 1 and 3 records). On `AnchoredFileLedger` all three raise |
| FI-7 | **The anchor is optional.** S7a, S7c, S7b load without error on `AnchoredFileLedger` (3, 2 and 0 records): an attacker who also removes the anchor defeats it. S8 loads with 4 records |
| FI-8 | **Simplest rival (ungoverned baseline).** An `UngovernedWorkflow` (sensor, predictor, execute, record; no verifier, gate or registry) has effects > 0 in exactly the cells where the governed workflow has 0 effects **and** the sensor and predictor succeed: **{U0r, U3, U4, U5, U6, U7, U8, U9, U10}**, i.e. 9 of the 11 cells U0r and U1–U10. Governed: 0 of 11. Unjustified-action rate: governed 0/11, ungoverned 9/11 |
| FI-9 | **Determinism.** Two runs of the whole harness give identical observations (digest equal) |

Observations are exact integers, strings and message prefixes. No tolerance, no sampling.

## Anti-vacuity and sabotage

`--sabotage` plants a bypass in the governed arm: the sensor also calls the executor before the gate. FI-4 must
then be REFUTED (I-A violated in U0r and other cells) and the harness must exit 1.

## Trigger table

| Trigger | Answer |
|---|---|
| Feasibility | No. Fixed code, no data |
| Noise | No. Deterministic; FI-9 checks it |
| Statistics | No. Exact counts over a fixed set of cells |
| Evidence | No. Integrity and fail-closed behaviour of stored artifacts and the workflow, not a rule's handling of fresh, stale or replayed evidence (E4r replays a record id, as XB-1 did) |
| Independence | No independence is claimed |
| External | No outside material relied on. The priority queue is Chad Holland's |
| Device | **Yes.** Not run on the S25: NOT VALIDATED on device. `AnchoredFileLedger` needs `fcntl`: anchored cells are NOT RUN on Windows, and CI for this harness covers Linux and macOS only |
| Verdict code | **Yes** (C-BUILD): the harness fails closed; a missing import, or an anchored cell on a platform without `fcntl`, is exit 2 (COULD NOT RUN), not a pass |
| Exploration | **Yes**: the reading listed above |
| Method comparison | No |

## Next unrun test

Concurrent writers and process kill at each fsync boundary (real subprocess kills, not simulated exceptions).
Run the harness on the S25.
