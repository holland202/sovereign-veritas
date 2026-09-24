"""Sovereign Veritas runtime and governance layer."""

from .adversarial import (
    AdversarialPlan,
    AdversarialPolicy,
    CandidateState,
    ResourcePolicy,
    adversarial_evidence,
    adversarial_pressure,
    attack_mode,
    plan_adversarial_search,
    topology_descriptor,
)
from .interfaces.contracts import AdversarialVerifier, Adversary
from .capability import Capability, CapabilityRegistry
from .decision import Decision, Gate
from .evidence import EvidenceRecord, Ledger, LedgerSink
from .file_ledger import FileLedger
from .runtime import RuntimeState

__all__ = [
    "AdversarialVerifier",
    "Adversary",
    "Capability",
    "CapabilityRegistry",
    "Decision",
    "EvidenceRecord",
    "Gate",
    "Ledger",
    "LedgerSink",
    "FileLedger",
    "RuntimeState",
    "AdversarialPlan",
    "AdversarialPolicy",
    "CandidateState",
    "ResourcePolicy",
    "adversarial_evidence",
    "adversarial_pressure",
    "attack_mode",
    "plan_adversarial_search",
    "topology_descriptor",
]

__version__ = "0.1.0"
