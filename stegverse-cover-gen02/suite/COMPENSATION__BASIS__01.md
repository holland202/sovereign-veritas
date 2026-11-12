# COMPENSATION BASIS — 01

StegVerse Build Lane, 2026-11-12. ProjectID LINKEDIN-SOVEREIGN-VERITAS-EVAL.
Required member under the suite template's GEN 02 specification (Spec
02, E7): the declaration of which of the subject's error modes this
product accounts for, metered in the subject's own units by the
subject's own probes.

## Declaration: accounts_for_errors = true

The covering layer compensates for error modes the subject's own
published findings document, at the execution boundary:

- **Duplicate execution under concurrency** (XB-1 X4, OPEN in the
  subject's record: a concurrent duplicate record_id produced two
  effects). The covering refuses the second INTENT atomically before
  execution. Metered in the subject's unit — effects at the executor:
  the unguarded construction yields 2; the covered construction yields
  1. Compensation per occurrence: 1 excess effect prevented.
- **Duplicate execution in the has_record-less sink configuration**
  (the subject's own regression test asserts the unguarded duplicate
  produces 2 effects). Covered: 1 effect, the duplicate refused before
  the executor is reached. Compensation per occurrence: 1 excess effect
  prevented.
- **Effect without a record** (XB-1 X5, OPEN: the effect lands, the
  record write fails, the chain knows nothing). The covering writes the
  COMPLETION before the evidence record is delegated; a failed record
  write leaves a named asymmetry the pair verifier reports, instead of
  silence. Metered in the subject's units — records and open
  transitions: silence (0 records for 1 effect) becomes 1 named open
  item per occurrence.
- **A record claiming no execution behind a real one** (EO-1's
  construction verifies CONSISTENT in the subject's package). The pair
  verifier fails it (V5). Compensation: a false CONSISTENT verdict
  becomes a named failure, per occurrence.

## Meter readings

GEN 01 (author runs, reproduced by the subject 2026-11-12): covering
probe 7/7 as registered — C1 and C2 each show the duplicate class
compensated at 1 effect; C3 shows the X5 asymmetry named; C4 shows the
EO-1 construction failing pair verification.

GEN 02 (author runs): the same probe, 7/7 on the corrected lock;
test_lock_contention.py shows the duplicate class compensated across
processes (8 attempts, 1 admission). Readings re-stated at each
generation, from the runs, never carried at a previous generation's
rate.

## What this basis is for

If the subject ever elects Governance Continuity, its stated basis is
this measured compensation load — the error surface the covering
carries on the subject's behalf — re-stated from the meter at each
generation. Paid remediation retires error classes at the source; each
retirement reduces the compensation load, and the basis declines with
it, toward the pure-verification limit. No party profits from anything
staying broken. This specimen is UNFUNDED and introductory; nothing here
prices it, and UNFUNDED specimens are never retro-priced.
