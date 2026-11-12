"""Guarded workflow for the Sovereign Veritas covering (StegVerse Build Lane).

Wraps an unmodified EvidenceWorkflow for one run at a time:

- The executor is proxied. Sovereign Veritas calls execute() only on an ALLOW
  decision, with the frozen decided action (SV-FIX-001 F1) - so the proxy writes
  the transition INTENT, durably, before the inner executor can produce any
  effect, and refuses a repeated record_id there (XB-1 X1-X4, for every caller,
  with no idempotency key and regardless of the sink). After the effect it reads
  back the target's state through a probe that does not go through the executor,
  and computes the EO-2 observed-effect verdict at completion time.
- The sink is proxied. The COMPLETION (intent hash + observation + expected state
  + verdict) is appended to the transition ledger BEFORE the evidence record is
  delegated to the real sink - so if the record write fails (XB-1 X5), the
  completion stands and the pair-check can name the asymmetry instead of the
  chain holding silence.
- If the executor raises, the intent is marked UNKNOWN (the RK vocabulary): the
  effect may or may not have happened, the record_id stays refused, and the
  transition stays open for a person - never silently reusable, never a success.

Nothing in sovereign_veritas is modified; the wrap is two attribute swaps for
the duration of run(), restored afterwards.
"""
from __future__ import annotations

from typing import Any, Callable

from sovereign_veritas.effect_observation import (
    action_digest,
    check_observed_effect,
    make_observation,
)
from sovereign_veritas.interfaces.contracts import ActionProposal

from .transition_ledger import TransitionLedger

Probe = Callable[[], dict[str, Any]]
ExpectedOf = Callable[[dict[str, Any]], dict[str, Any] | None]


def _action_dict(action: ActionProposal) -> dict[str, Any]:
    return {"capability": action.capability, "requested": action.requested,
            "parameters": dict(action.parameters)}


class TransitionExecutor:
    """ActionExecutor proxy: intent-before-effect, attested completion."""

    def __init__(self, inner: Any, ledger: TransitionLedger, record_id: str,
                 probe: Probe, expected_of: ExpectedOf | None = None) -> None:
        self.inner = inner
        self.ledger = ledger
        self.record_id = record_id
        self.probe = probe
        self.expected_of = expected_of
        self.pending: tuple[dict[str, Any], dict[str, Any] | None, str] | None = None

    def execute(self, action: ActionProposal) -> Any:
        action_dict = _action_dict(action)
        before = self.probe()
        # The claim is the transition's admission: durable, before any effect.
        self.ledger.begin(self.record_id, action_digest(action_dict))
        try:
            result = self.inner.execute(action)
        except Exception as exc:
            self.ledger.mark_unknown(self.record_id, str(exc))
            raise
        after = self.probe()
        observation = make_observation(self.record_id, action_dict, before, after)
        expected = self.expected_of(action_dict) if self.expected_of else None
        pseudo_record = {"record_id": self.record_id, "action": action_dict,
                         "decision": "ALLOW",
                         "metadata": {"execution_status": "SUCCEEDED"}}
        verdict = check_observed_effect(pseudo_record, observation, expected)
        self.pending = (observation, expected, verdict)
        return result


class TransitionSink:
    """EvidenceSink proxy: the completion precedes the evidence record."""

    def __init__(self, inner: Any, ledger: TransitionLedger,
                 executor: TransitionExecutor) -> None:
        self.inner = inner
        self.ledger = ledger
        self.executor = executor

    def record(self, record: Any) -> Any:
        pending = self.executor.pending
        if pending is not None and getattr(record, "record_id", None) == self.executor.record_id:
            observation, expected, verdict = pending
            self.ledger.complete(self.executor.record_id, observation, expected, verdict)
            self.executor.pending = None
        return self.inner.record(record)

    def has_record(self, record_id: str) -> bool:
        # Sovereign Veritas' own pre-check stays available through the proxy.
        has = getattr(self.inner, "has_record", None)
        return bool(has(record_id)) if has is not None else False


def run_guarded(workflow: Any, ledger: TransitionLedger, probe: Probe,
                expected_of: ExpectedOf | None = None, **run_kwargs: Any) -> Any:
    """Run workflow.run(**run_kwargs) with the transition wrap in place."""
    record_id = run_kwargs["record_id"]
    inner_executor, inner_sink = workflow.executor, workflow.evidence_sink
    proxy = TransitionExecutor(inner_executor, ledger, record_id, probe, expected_of)
    workflow.executor = proxy
    workflow.evidence_sink = TransitionSink(inner_sink, ledger, proxy)
    try:
        return workflow.run(**run_kwargs)
    finally:
        workflow.executor = inner_executor
        workflow.evidence_sink = inner_sink
