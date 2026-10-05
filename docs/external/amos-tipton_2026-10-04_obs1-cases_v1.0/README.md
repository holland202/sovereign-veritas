# OBS-1 outside-authored cases — Amos Tipton — v1.0

Prepared 2026-10-04 by Amos Tipton, Founder & Chief Architect of HYBRID WAYSS,
with AI assistance using OpenAI tools. Submission candidate for preregistration;
not yet published, run, or evidence of a passing implementation.

## Baseline and scope

Target: [docs/OBS1_INTERFACE.md](https://github.com/holland202/sovereign-veritas/blob/04bca2dfbb014d66566a38f9068a07a2e9c86947/docs/OBS1_INTERFACE.md)
in holland202/sovereign-veritas.

- Frozen commit: `04bca2dfbb014d66566a38f9068a07a2e9c86947`
- Interface SHA-256: `dff9af54ed649546f8251072fc630a73da09563e627c6c9120741210009a8f4e`
- Retrieved interface bytes matched this checksum during preparation.

Four core scenarios plus one delayed-write variant of scenario 4: five complete
inputs, each with one expected-result file. This submission replaces the earlier
exploratory seven-input draft; the extra recovery variants are outside this package.
Case authorship used the frozen interface and supplied correspondence, without
reviewing an OBS-1 implementation. It includes no runner or implementation code.

## Files and interpretation

`cases/<case_id>.json` is a complete input; `expected/<case_id>.json` uses the
expected-result shape in the frozen interface. Neither needs template substitution.
`SHA256SUMS` covers this README and all ten JSON files; it excludes itself and the ZIP.

The expected JSON compares the listed fields exactly, including attempt order and
the complete ordered class list. Reports must still include all fields required by
the interface. Omitted `reason` and `reconciliation` fields in expected JSON do not
waive those requirements: validate them under the interface and evidence checks below.
Random tokens and read sequence numbers are obtained from the run, not hard-coded.

Predictions use `ALLOW` for authorized execution, `REFUSE` for revocation, and
`DEFER` for an unresolved held retry. The interface expressly mandates `REFUSE`
on revocation; the other pairings are author predictions, not newly imposed interface
rules. Report a differing pairing as a prediction mismatch, separately from a
safety finding. Preserve it; do not rewrite expectations after inspecting results.

## Cases and predictions

Each case gets a fresh store: `r1`, value `off`, version 0; the intent requests `on`.
Retries retain the same intent and idempotency key. The harness generates a fresh
random token per attempt and issues every listed attempt. Write permission is
fixed at the execution value during every attempt; fence permission is granted
in all five inputs. Only AT-4 attempt 2 has observation unavailable.

| Case | Condition | Predicted reports (decision/status) | Effects | Classes in order |
|---|---|---|---:|---|
| AT-1 | Granted; no fault | ALLOW/COMPLETED | 1 | AUTHORIZED_COMPLETION |
| AT-2 | Approved, then revoked before execution | REFUSE/REFUSED | 0 | CONFIRMED_FAILURE |
| AT-3 | Granted; fail_before_effect | ALLOW/FAILED | 0 | CONFIRMED_FAILURE |
| AT-4 | lose_ack_after_effect; retry observation unavailable | ALLOW/UNKNOWN; DEFER/HELD | 1 | AUTHORIZED_COMPLETION, UNKNOWN_HELD |
| AT-4-DW | hold_write_until_fence; retry can fence and read | ALLOW/UNKNOWN; ALLOW/COMPLETED | 1 | AUTHORIZED_COMPLETION, UNKNOWN_RECONCILED_RETRY |

All five predict zero status mismatches. Reported execution permission is REVOKED
only in AT-2, otherwise GRANTED on every attempt. Final value/version is off/0
for AT-2 and AT-3, otherwise on/1. Count write events, including repeated writes
of the same value; final value alone cannot establish the effect count.

## Required evidence

- **AT-1:** Exactly one write attributed to attempt 1. COMPLETED has a null reason;
  no earlier uncertainty exists to reconcile.
- **AT-2:** Re-read execution permission and refuse. No business-write call;
  no write event. REFUSED has a machine-readable reason for revocation.
  CONFIRMED_FAILURE is the interface's zero-effect classification; correct refusal
  passes this case.
- **AT-3:** The attempted write is logged as rejected with reason `fault`, with
  no write event. FAILED has a machine-readable reason for confirmed rejection.
- **AT-4:** One write belongs to attempt 1; its acknowledgement is lost and its
  report is UNKNOWN. Attempt 2 writes nothing and reports HELD with a reason for
  unresolved prior execution. If it reads, the result is unavailable. An authorized
  fence is allowed, but cannot prove whether a prior write occurred. No successful
  reconciliation read may be claimed. The observer is unaffected by system-read
  unavailability and sees the first write. AUTHORIZED_COMPLETION describes the
  effect; UNKNOWN_HELD describes the absence of a later write after UNKNOWN.
- **AT-4-DW:** Attempt 1 times out before reaching the store and reports UNKNOWN.
  Attempt 2 fences its token. Checkpoint A releases the held write inside that same
  locked step: its rejected/fenced event must have seq equal to fence seq + 1.
  Attempt 2 then performs a successful read and only then writes, with granted
  write permission. The read shows no earlier write and includes the rejection.
  Exactly one write belongs to attempt 2. Its reconciliation report identifies
  attempt 1's token, the actual successful read seq, zero observed writes by that
  token, and `by: system`. Check the claim against the log. The harness records
  `released_at: fence`, `result: rejected`, and the rejection's actual seq.

Other permitted read/control events need not match a fabricated exact trace.
They must obey permissions, attribution and store invariants. Before scoring any
case, check the frozen store invariants and demonstrate the invariant check can
fail on a deliberately broken store, as the interface requires. Keep the observer
separate and read-only; do not use its findings to suppress listed retries.

## Failure reporting and coverage boundaries

A post-fence write is STORE_DEFECT, with no outcome class. If AT-4-DW finishes
without fencing the held token, checkpoint B releases the write and reports
LATE_WRITE_UNFENCED: failure even if only one write occurs. A retry write without
the required recovery evidence is UNKNOWN_UNRESOLVED_RETRY, even with one effect.
An attempt that never returns produces HARNESS_TIMEOUT, not a skipped case.
Release the held write exactly once, then observe the final state. Time limits
are backstops, not a substitute for checkpoint ordering.

Keep all applicable classes, status mismatches, defects, timeouts and deviations
from predictions. Full matching requires the expected JSON plus the evidence
requirements above, not just the desired final value or zero status mismatches.
Unattributable effects cannot be silently assigned to a claimed attempt.

This package exercises successful checkpoint A recovery; it does not guarantee
checkpoint B will be taken by a conforming implementation. Its missing-fence
failure branch must nevertheless be implemented as frozen. This package does not
add a forced checkpoint B input or a new test-machinery suite.

Not covered: fail_record_after_effect, ALREADY_COMPLETED recovery, denied fence
permission, mid-execution revocation, multiple records/stores, other late-write
release positions, or human release of a hold. Those require separate cases or
later rounds. A passing run is bounded synthetic evidence, not certification,
production safety, an endorsement, or general exactly-once execution.

## Publication and run sequence

Commit these submitted files unedited under docs/external/ with their checksums
before implementation is written or shared, as agreed. Return the commit link
so published bytes can be checked against this package. This package's existence
alone does not establish that preregistration or that sequence has occurred.
Preserve attribution and the stated limits. This package contains no private messages.

Run all five inputs and retain the implementation commit, command, harness token
and permission records, every system report, before/after observer snapshots,
complete store events, delayed-release record, and comparator output. Report
each case as written. An input the interface cannot express is an interface defect,
not an omitted case. Any later amendment gets a new version and hashes; keep v1.0.

Verify all submitted files from the extracted package directory with
`sha256sum -c SHA256SUMS` (or an equivalent SHA-256 checker). ZIP integrity and JSON
structure were checked during preparation; no OBS-1 execution was performed.
