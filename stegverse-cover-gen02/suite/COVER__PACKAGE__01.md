# THE sv_transition_cover PACKAGE

The covering code is a Python package of four files; three are carried in
this suite as flat members (transition_ledger.py, guarded_workflow.py,
verify_transition.py). To run it, place those files in a directory named
sv_transition_cover/ together with an __init__.py containing:

    from .guarded_workflow import TransitionExecutor, TransitionSink, run_guarded
    from .transition_ledger import TransitionLedger

and put a Sovereign Veritas checkout and the package's parent directory
on PYTHONPATH. run_cover_tests.py (carried in this suite) exercises the
whole covering against the repository's own constructions. Nothing in
sovereign_veritas is modified by the covering.

GEN 02 additions, also flat members of this suite:

- test_lock_contention.py — assembles the package from this suite's own
  flat members (as above) and races separate processes on one record_id
  against one ledger file, exercising the GEN 02 lock contract. Needs
  the same PYTHONPATH as run_cover_tests.py.
- test_non_vacuity.py — stdlib only, no checkout needed: runs this
  suite's self_check.py against pristine and deliberately vacated
  copies of the suite and shows the GEN 02 vacancy layer failing the
  vacated ones.
