# GEN 02 — the cure generation (separately identifiable; GEN 01 untouched)

This directory carries Generation 02 of the StegVerse covering suite for
Sovereign Veritas, beside — not over — the GEN 01 tree at
`stegverse-cover/`, which is preserved byte-for-byte as the baseline.

**Why GEN 02 exists.** GEN 01 was independently reproduced by the
repository's author (self-check 41/0; covering probe 7/7; boundary set
33/33; graded: bounded reproducibility). His examination returned three
findings against the suite itself, and GEN 02 cures exactly those three:

1. **The Windows lock was a no-op.** `transition_ledger.py` imported
   `msvcrt` but never called it; on Windows no lock was taken, under a
   docstring claiming one "for every caller." GEN 02 implements the
   lock on both platforms through a single helper and adds
   `test_lock_contention.py` (separate processes racing one record_id).
2. **The conformance gate could not fail on vacancy.** Three prose
   members shipped as unfilled template placeholders under a CONFORMANT
   proof. GEN 02 writes the members in full and adds a vacancy layer to
   the checker, proven by `test_non_vacuity.py` (the gate shown failing
   on deliberately vacated copies).
3. **The commercial shape was in the file before the message.** The
   terms now stand in both, in the same words — and the author's answer
   is recorded with them: continuation not elected; the collaboration
   continues public and non-commercial. GEN 02 is cure work on an
   UNFUNDED specimen and creates no charge.

**What did not change.** The covering design, the transition grammar,
the pair-verification rules, the seven registered cases, and the
repository's core — all GEN 01's, unmodified.

**Layout.** `suite/` is the GEN 02 suite exactly as shipped: 20 members
plus its manifest, with the conformance proof inside the suite it
proves. Start at `suite/README.md`; the finding-by-finding mapping is
`suite/CURE__RECORD__01.md`.

**Running it.**

    python3 suite/self_check.py
    python3 suite/test_non_vacuity.py
    PYTHONPATH=<sovereign-veritas-checkout>:<assembled-package-parent> python3 suite/run_cover_tests.py
    PYTHONPATH=<sovereign-veritas-checkout> python3 suite/test_lock_contention.py

**Status.** GEN 02 stands AUTHOR-CONFORMANT. The verification that
discharged GEN 01 — the author's independent reproduction — is the
standing next step for GEN 02 as well. The structural question (what
prevents execution from bypassing the covering layer entirely) is
documented at issue #79 with the author's three proposed test shapes.
