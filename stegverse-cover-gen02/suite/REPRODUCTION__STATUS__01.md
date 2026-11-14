# REPRODUCTION STATUS — 01

StegVerse Build Lane, 2026-11-12. ProjectID LINKEDIN-SOVEREIGN-VERITAS-EVAL.
Who has run what, graded as the runners graded it. Author-side runs are
never recorded here as verification.

## GEN 01 — reproduced by the subject (non-author)

Chad Holland, 2026-11-12, isolated container, fresh clone of
holland202/sovereign-veritas at 13c663b3a3b058b7170fd3628325c1361112d07d,
Python 3.13.18: self-check 41/0; covering probe 7/7 as registered;
boundary-relevant test files 33/33; covering code clean on static read
with the lock exception recorded as Finding 1 in CURE__RECORD__01.md.
His grading: bounded reproducibility. Not independent security
validation of Sovereign Veritas; not proof of real-world execution
safety. This suite's record adopts his grading exactly. GEN 01 also
carries his correction of the assessor's run-form attribution for his
repository's full-suite failures (isolated by him to a Python 3.12
incompatibility in his repository); the withdrawn attribution stands
withdrawn.

## GEN 02 — AUTHOR-CONFORMANT, reproduction pending

Author-side runs at build time (coordinator session, Linux, Python
3.12.3, subject checkout at the pinned commit): covering probe 7/7 as
registered on the corrected lock; lock contention test L1–L2 pass;
non-vacuity tests T0–T3 pass; self-check passes including the vacancy
layer. These are the builder's runs. GEN 02's verification is the same
act that discharged GEN 01: a non-author reproduction, the subject's in
the first instance, against the draft pull request that carries this
generation. Until then this suite claims AUTHOR-CONFORMANT and nothing
more.
