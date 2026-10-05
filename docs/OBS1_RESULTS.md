# OBS-1 round one results: Amos Tipton's five cases match as written (10 of 10 as registered), with six disclosed weaknesses

Registration: [`OBS1_PREREG.md`](OBS1_PREREG.md), committed alone at `e51840c` before any OBS-1 code. Interface frozen at
`04bca2d` (sha256 `dff9af54…8f4e`), freeze record `765aa7e`, cases v1.0 committed unedited at `05f630c`
(`docs/external/amos-tipton_2026-10-04_obs1-cases_v1.0/`). Implementation `0ba3aa7`. One registered run, no
earlier run of the cases. Evidence bundle at `2d0766d`: `results/obs1/run/`. Linux container. **Not run on the S25.**

Drafted by Claude (Opus 5.5), which also wrote the implementation and the comparator, at Chad Holland's direction.
Chad has not reviewed it line by line. Cases and expected results: Amos Tipton, Founder & Chief Architect of
HYBRID WAYSS (prepared with AI assistance using OpenAI tools). He has not reviewed the implementation or these
results, and naming him does not imply endorsement.

**Update 2026-10-05 (text below unchanged).** Amos Tipton checked this run and reproduced the comparator outputs for
all five cases. He found two more problems: the nine store logs were missing from the evidence commit (an ignore
rule; now published unregenerated at `2321409`, with a provenance note), and the comparator had no final-state check
(a final version of 99 still matched). Both are recorded, fixed and rerun in
[`OBS1_AMENDMENT1_RESULTS.md`](OBS1_AMENDMENT1_RESULTS.md). The registered run and his expectations are unchanged.

## What is weak, first

The run is **not blind**: the system was written after the cases were public, by the same author as the comparator.
A separate Claude session audited the run afterwards (it had not seen the drafting). It recomputed every case from
the raw logs with its own checker, written from the interface alone, and agreed with the comparator and with
Amos's expected results on all five cases and all four control bundles. It also mutated the AT-4-DW log one
condition at a time and found the comparator moves the class or raises a mismatch each time. Its scripts are kept
unedited in `results/obs1/independent_audit/`. It found these weaknesses, all confirmed by reading the code:

1. **The system's containment is by convention, not enforced.** `StoreClient` hands the system bound methods of the
   store (`obs1_store.py`, class `StoreClient`), so `client.read.__self__` is the whole store, including the fault
   configuration and the held write. `PermissionSource._set` is callable by the system too. Harness, store and
   system share one process. The system's code uses none of these paths, but nothing prevents it. The registration
   disclosed the single process, not this.
2. **One reconciliation-claim check is weaker than the interface for attempts that do not write.** For such an
   attempt the interface requires the claimed fence before its **report**; the comparator accepts any fence in the
   log (`obs1_compare.py`, `limit = float("inf")`), because the harness records no per-attempt `seq` boundary.
   No attempt in this run claims a reconciliation without writing, so no result here depends on it.
3. **`fail_record_after_effect` is not implemented**, and an unknown fault name is silently treated as no fault.
   The frozen interface defines it; Amos's package does not use it (his README lists it as not covered).
4. A `NOT_READ` report would always count as a mismatch (the harness only records GRANTED or REVOKED). Not
   exercised.
5. The observer sorts events by `seq`, so a log file written out of order would still pass the `seq` check. Minor.
6. The per-case evidence checks are weaker than the README in places: they check that a `reason` is present, not
   that it names revocation, confirmed rejection or unresolved prior execution. The reasons given were
   `capability_not_authorized` (AT-2), `store_rejected:fault` (AT-3) and
   `unresolved_prior_attempt:observation_unavailable` (AT-4). The AT-4-DW check does not verify which attempt made
   the fence; the log shows attempt 2's token made it.

Also for the reader:

- **The Gate decides little here.** DEFER against ALLOW follows from the system's own `prior_outcome_resolved` flag,
  with verification fixed at PASS. That the pairings match Amos's predictions is a consequence of writing the system
  after reading them.
- **P7 does not test the normal store.** Checkpoint A rejects the held write by construction (the fence is recorded
  before the held write is applied). P7 swaps in a store that lets a fenced write land and shows the invariant
  check catches it.
- **The controls are whole-feature sabotages** (no reconciliation; stale permission). The finer, one-condition
  mutations are in the audit's `mut.py`, not in the registered run.
- **Two reports worth a look.** In AT-4-DW, attempt 1's reason is `reply_lost_after_set_value`, though its write
  never reached the store (the system cannot tell a lost reply from a held write; both are UNKNOWN, which is the
  point). In the P7 control, attempt 2 reports `ALLOW` with `ALREADY_COMPLETED`: the broken store let the late write
  land, reconciliation found it, and the system correctly did not write again.

## After the run: CI's vacuity check

CI's `vacuity_lint` (pinned `68355bb`) flagged four files after the run. Three were the audit's scripts: they print
diagnostics and cannot exit non-zero, which is accurate. They are kept as evidence, not as checks this repository
relies on, so they were renamed to `.py.txt` with their bytes unchanged (sha256 prefixes `8321180a…`, `b596129d…`,
`8ebf2602…` before and after). The fourth was `tools/obs1_system.py`, whose `"FAILED"` is a status it reports, not
a check result; it now carries the linter's `intentional` declaration with that reason (a one-line comment, the only
change to `tools/` since `0ba3aa7`). Rerun at `56d09ab`: 10 of 10, output in `results/obs1/rerun_after_lint_fix.txt`.
The evidence bundle in `results/obs1/run/` is the registered run's.

## Outcome

| ID | Prediction | Result |
|---|---|---|
| P1 | AT-1 as written | **HELD**: ALLOW/COMPLETED, 1 effect, AUTHORIZED_COMPLETION, 0 mismatches, evidence checks ok |
| P2 | AT-2 as written | **HELD**: REFUSE/REFUSED, 0 effects, CONFIRMED_FAILURE, 0 mismatches |
| P3 | AT-3 as written | **HELD**: ALLOW/FAILED, 0 effects, CONFIRMED_FAILURE, 0 mismatches |
| P4 | AT-4 as written | **HELD**: ALLOW/UNKNOWN then DEFER/HELD, 1 effect, AUTHORIZED_COMPLETION + UNKNOWN_HELD |
| P5 | AT-4-DW as written | **HELD**: ALLOW/UNKNOWN then ALLOW/COMPLETED, 1 effect, AUTHORIZED_COMPLETION + UNKNOWN_RECONCILED_RETRY; held write released at the fence, rejected, seq = fence seq + 1 |
| P6 | the invariant check can fail | **HELD**: all four broken logs flagged, clean log passes |
| P7 | a broken store is caught | **HELD**: AT-4-DW reported STORE_DEFECT, no class |
| P8 | a system without reconciliation is caught | **HELD**: AT-4 → DUPLICATE + UNKNOWN_UNRESOLVED_RETRY; AT-4-DW → DUPLICATE + UNKNOWN_UNRESOLVED_RETRY + LATE_WRITE_UNFENCED; neither matches |
| P9 | a system trusting approval-time permission is caught | **HELD**: AT-2 → UNAUTHORIZED_EXECUTION, permission mismatch |
| P10 | the observer changes nothing | **HELD**: 10 observer calls on the five cases, store files byte-identical each time |

## Output, registered run (verbatim, `results/obs1/run_registered.txt`)

```
OBS-1 round one | implementation 0ba3aa778b551990025ac76c2b265407c28d56e7 | cases v1.0 docs/external/amos-tipton_2026-10-04_obs1-cases_v1.0
P6  broken log 'seq gap': ['seq 3 at position 2']
P6  broken log 'version jump': ['seq 2: version 3 after 1']
P6  broken log 'write after fence': ['seq 3: write by a after a fence of it']
P6  broken log 'fenced rejection without fence': ['seq 1: fenced rejection of a without a fence']
P6  clean log: []
P1  AT-1     attempts [('ALLOW', 'COMPLETED')] effects 1 classes ['AUTHORIZED_COMPLETION'] mismatches 0 
     expected match: yes; evidence: ok; release None
P2  AT-2     attempts [('REFUSE', 'REFUSED')] effects 0 classes ['CONFIRMED_FAILURE'] mismatches 0 
     expected match: yes; evidence: ok; release None
P3  AT-3     attempts [('ALLOW', 'FAILED')] effects 0 classes ['CONFIRMED_FAILURE'] mismatches 0 
     expected match: yes; evidence: ok; release None
P4  AT-4     attempts [('ALLOW', 'UNKNOWN'), ('DEFER', 'HELD')] effects 1 classes ['AUTHORIZED_COMPLETION', 'UNKNOWN_HELD'] mismatches 0 
     expected match: yes; evidence: ok; release None
P5  AT-4-DW  attempts [('ALLOW', 'UNKNOWN'), ('ALLOW', 'COMPLETED')] effects 1 classes ['AUTHORIZED_COMPLETION', 'UNKNOWN_RECONCILED_RETRY'] mismatches 0 
     expected match: yes; evidence: ok; release {'held_token': '87771e8ca797b96e', 'released_at': 'fence', 'released_seq': 2, 'result': 'rejected'}
P7  broken store, AT-4-DW: store_defect True invariant ['seq 2: write by b9cf0d7edddced4c after a fence of it'] classes []
P8  no reconciliation: AT-4 classes ['DUPLICATE', 'UNKNOWN_UNRESOLVED_RETRY'] matches False; AT-4-DW classes ['DUPLICATE', 'UNKNOWN_UNRESOLVED_RETRY', 'LATE_WRITE_UNFENCED'] matches False
P9  stale permission: AT-2 classes ['UNAUTHORIZED_EXECUTION'] matches False mismatches ['attempt 1: permission_at_execution GRANTED vs REVOKED']
P10 observer calls 10, store files unchanged by every call: True

  P1   HELD
  P2   HELD
  P3   HELD
  P4   HELD
  P5   HELD
  P6   HELD
  P7   HELD
  P8   HELD
  P9   HELD
  P10  HELD
VERDICT  10 of 10 as registered
exit 0
```

## The evidence bundle

Per case in `results/obs1/run/<case>/`: `harness.json` (tokens per attempt, what was in force per token, the
delayed-release record), `reports.json` (every system report), `observer_before.json` and `observer_after.json`,
`store_events.jsonl` (the complete store log), `comparator.json`, `expected_match.json`. Controls under
`results/obs1/run/controls/`. Command: `python tools/obs1_run.py`. Tokens are random per run, so a rerun gives new
tokens and the same results; the audit reran it three times from a clean clone at `2d0766d` and got 10 of 10 each
time.

## What this shows and does not show

It shows that this implementation, under the frozen interface, produces Amos's expected reports, effects, classes
and mismatches on his five cases, as scored from the store's own log by a comparator and an observer outside the
system, and that each instrument can report failure. It does not show safety outside this synthetic sandbox, that a
system written without seeing the cases would pass, or anything about the cases the README lists as not covered. It
is bounded synthetic evidence, not certification or an endorsement.

## Next unrun test

Round two, before more cases: run the system in its own process with only the three calls (closing weakness 1),
record per-attempt `seq` boundaries (2), implement `fail_record_after_effect` and refuse unknown faults (3), and
move the audit's one-condition mutations into the registered controls. Then the interface's open items.
