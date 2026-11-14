"""StegVerse covering for Sovereign Veritas: transition-bound execution.

Wraps the unmodified Sovereign Veritas workflow so that an action's record is its
transition: a durable INTENT before any effect (one per record_id, atomically
refused on repeat), and a COMPLETION carrying the effected side's attestation
(before/after read-back, EO-2 verdict) before the evidence record is written.
The offline pair verifier checks what neither side can check alone.
"""
from .guarded_workflow import TransitionExecutor, TransitionSink, run_guarded
from .transition_ledger import TransitionLedger

__all__ = ["TransitionLedger", "TransitionExecutor", "TransitionSink", "run_guarded"]
