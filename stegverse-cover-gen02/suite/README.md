# SOVEREIGN VERITAS COVERING SUITE — 02

- Generation: 02
- ProjectID: LINKEDIN-SOVEREIGN-VERITAS-EVAL
- Funding: UNFUNDED. Full statement: FUNDING__STATEMENT__01.md.
- Source: Built by the StegVerse Build Lane (coordinator session, Muse) 2026-11-12: GEN 02 cure generation of the covering for holland202/sovereign-veritas, around its unmodified core; GEN 01 preserved separately as the baseline

## What this generation is

GEN 01 of this suite was reproduced by the subject's author, who returned
three findings against the suite itself: the transition ledger's Windows
lock was a no-op under a docstring that claimed otherwise; three prose
members shipped as unfilled template placeholders under a conformance
proof that could not fail on vacancy; and the suite's commercial shape
arrived in the file before it was stated in the message. GEN 02 is the
cure generation for those three findings and nothing else: the covering
design, the case registry, and the subject's unmodified core are GEN 01's,
unchanged. CURE__RECORD__01.md maps each finding to its cure and its
evidence. GEN 01 is preserved unmodified — in its own suite directory and
in the fork at StegVerse-org/sovereign-veritas (stegverse-cover/) — as the
baseline this generation is diffed against.

## Verification

Run `self_check.py`: it verifies every member against
PACKAGE__MANIFEST__01.json (size + SHA-256), runs the conformance
checklist carried from the suite template (funding block, ProjectID,
derivation), and — new in GEN 02 — a vacancy layer that fails the gate
when a prose member is a template placeholder or a stub. The vacancy
layer is itself tested by `test_non_vacuity.py` (the gate is shown to
fail on deliberately vacated copies). The covering is exercised by
`run_cover_tests.py` (7 registered cases) and the ledger's lock by
`test_lock_contention.py` (separate processes racing one record_id).
Derived from SUITE__TEMPLATE — the derivation is recorded in the manifest.
