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
from .evidence import EvidenceRecord, EvidencePackage, Ledger, LedgerSink
from .file_ledger import FileLedger
from .governance import CapabilityGovernor
from .planner import BoundedMultiStepPlanner, BoundedPlan, PlanResult, PlanStep
from .runtime import RuntimeState
from .uncertainty import normalize_uncertainty

__all__ = [
    "AdversarialVerifier",
    "Adversary",
    "AdversarialPlan",
    "AdversarialPolicy",
    "CandidateState",
    "ResourcePolicy",
    "adversarial_evidence",
    "adversarial_pressure",
    "attack_mode",
    "plan_adversarial_search",
    "topology_descriptor",
    "Capability",
    "CapabilityRegistry",
    "CapabilityGovernor",
    "BoundedMultiStepPlanner",
    "BoundedPlan",
    "PlanStep",
    "PlanResult",
    "Decision",
    "EvidenceRecord",
    "EvidencePackage",
    "Gate",
    "Ledger",
    "LedgerSink",
    "FileLedger",
    "RuntimeState",
    "normalize_uncertainty",
]

# Version stays at 0.1.x until on-device integration evidence is recorded.
__version__ = "0.1.1"
