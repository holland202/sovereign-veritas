# OBS-1 round one: registration

Status: **REGISTERED, nothing implemented.** Committed before any OBS-1 code exists, on top of the frozen interface
(`docs/OBS1_INTERFACE.md`, commit `04bca2d`, sha256 `dff9af54…8f4e`), the freeze record (`765aa7e`) and Amos
Tipton's case package v1.0, committed unedited at `05f630c` (`docs/external/amos-tipton_2026-10-04_obs1-cases_v1.0/`,
11 of 11 checksums verified by him and by this project).

Drafted by Claude (Opus 5.5) at Chad Holland's direction. Chad has not reviewed it line by line. Design lead and
case author: Amos Tipton, Founder & Chief Architect of HYBRID WAYSS (his cases were prepared with AI assistance
using OpenAI tools). Naming him does not imply he endorses or has reviewed the implementation or results.

## Not blind

The cases were public before the implementation was written, as the freeze procedure requires, and the
implementation is written by the same author (with Claude) who read them. A match therefore shows that this
implementation satisfies the cases as scored by an independent comparator and observer. It does not show that a
system written without seeing the cases would. The anti-vacuity controls below exist because of this.

## What will be built (design fixed here, before code)

- **Store** (`tools/obs1_store.py`): one record and an append-only log in a directory, the three calls of the
  interface under one exclusive lock, and the fault layer. The store checks no permissions.
- **System under test** (`tools/obs1_system.py`): sovereign-veritas's own `Gate` and RK-3 `FileReservations`.
  Per attempt it re-reads write permission at execution; if the intent's key shows an earlier unresolved attempt,
  it tries automated reconciliation (fence every earlier token, then read); then the Gate decides with
  `prior_outcome_resolved` as required evidence, so an unresolved prior attempt gives `DEFER` and a revoked
  permission gives `REFUSE` by the kernel's existing rules. It writes ahead which tokens it used per intent.
- **Observer** (`tools/obs1_observer.py`): a separate program, standard library only, importing nothing from this
  repository. It opens the store's files read-only and has no call into the store.
- **Comparator** (`tools/obs1_compare.py`): the store invariant, the outcome-class table, the status-mismatch
  rules and the reconciliation-claim checks of the interface, using only harness records and observer output; the
  system's report enters only the mismatch checks.
- **Harness and runner** (`tools/obs1_run.py`): fresh store per case, a fresh random token per attempt,
  permissions and conditions set before each attempt and recorded per token, every listed attempt issued,
  checkpoints A and B, a per-attempt wall-clock backstop (`HARNESS_TIMEOUT`), and an evidence bundle per case.

## How the interface is read where it leaves a choice (flagged, not amended)

1. `fail_before_effect` and `lose_ack_after_effect` apply to the **first** attempt's `set_value`, as
   `hold_write_until_fence` does by definition. Every case that uses them is consistent with this.
2. The store's exclusive lock is in-process (one process runs harness, store and system). The observer is a
   separate process. Several processes on one store are not round one.
3. How the system maps its state to `decision` is the system's, not the interface's; Amos's README marks those
   pairings (except `REFUSE` on revocation) as predictions.
4. `ALREADY_COMPLETED` is implemented but no case exercises it.

If the run meets something the interface cannot express, it is reported as an interface defect and v1.0 stays as
it is.

## Predictions

| ID | Prediction |
|---|---|
| P1–P5 | **Amos Tipton's cases, as written.** For AT-1, AT-2, AT-3, AT-4 and AT-4-DW, the comparator's result equals `expected/<case>.json` exactly (per-attempt `permission_at_execution`, `decision`, `system_status`; `effect_count`; the ordered `classes`; `status_mismatches`), and the README's evidence requirements for that case hold in the store log (for AT-4-DW: released at `fence`, `result: rejected`, released seq = fence seq + 1). |
| P6 | **The invariant check can fail.** On four deliberately broken logs (a `seq` gap; a version jump; a write by T after a fence of T; a fenced rejection with no fence) the check reports a violation for each, and passes the clean log. |
| P7 | **A broken store is caught.** With a store that lets a fenced write land, AT-4-DW is reported `STORE_DEFECT` with no outcome class. |
| P8 | **A careless system is caught.** With the system's reconciliation removed (a retry after `UNKNOWN` writes without fence or read), AT-4 and AT-4-DW do **not** match their expected results; AT-4 shows `DUPLICATE` and `UNKNOWN_UNRESOLVED_RETRY`, AT-4-DW shows `LATE_WRITE_UNFENCED`. |
| P9 | **A system that trusts approval-time permission is caught.** With the execution-time re-read removed, AT-2 does not match and shows `UNAUTHORIZED_EXECUTION`. |
| P10 | **The observer changes nothing.** The store's files are byte-identical before and after every observer call. |

The run is made once with these settings. A refuted prediction is kept and reported first. Any case Amos's
expected results do not match is reported as a mismatch as written; expectations are not edited.

## Evidence kept per case

Implementation commit, command, harness token and permission records, every system report, observer snapshots
before and after, the complete store log, the delayed-release record, and the comparator's output, under
`results/obs1/`.

## Limits

Synthetic sandbox; one record, one store, one process for system and store; Linux container. **Not run on the
S25.** A pass is bounded synthetic evidence, not certification, production safety, an endorsement, or general
exactly-once execution.

## Next unrun test

The interface's open items: revocation during execution, a late write released between a retry's read and its
write, and what a person's release must record.
