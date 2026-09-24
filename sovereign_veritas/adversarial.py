from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


def _bounded(value: float, name: str) -> float:
    value = float(value)
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be in [0, 1]")
    return value


@dataclass(frozen=True)
class CandidateState:
    """Measured/descriptive state of a candidate before adversarial search.

    These values are epistemic/search signals, not truth values.
    """

    candidate_id: str
    uncertainty: float
    disagreement: float
    novelty: float
    verification_gap: float
    refutation_risk: float

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise ValueError("candidate_id must not be empty")

        for name in (
            "uncertainty",
            "disagreement",
            "novelty",
            "verification_gap",
            "refutation_risk",
        ):
            _bounded(getattr(self, name), name)


@dataclass(frozen=True)
class AdversarialPolicy:
    """Deterministic policy for allocating adversarial search effort."""

    uncertainty_weight: float = 0.20
    disagreement_weight: float = 0.20
    novelty_weight: float = 0.15
    verification_gap_weight: float = 0.25
    refutation_risk_weight: float = 0.20

    minimal_threshold: float = 0.25
    competing_threshold: float = 0.45
    counterexample_threshold: float = 0.65

    def __post_init__(self) -> None:
        weights = (
            self.uncertainty_weight,
            self.disagreement_weight,
            self.novelty_weight,
            self.verification_gap_weight,
            self.refutation_risk_weight,
        )

        if any(weight < 0.0 for weight in weights):
            raise ValueError("policy weights must be non-negative")

        if sum(weights) <= 0.0:
            raise ValueError("at least one policy weight must be positive")

        thresholds = (
            self.minimal_threshold,
            self.competing_threshold,
            self.counterexample_threshold,
        )

        if any(not 0.0 <= threshold <= 1.0 for threshold in thresholds):
            raise ValueError("policy thresholds must be in [0, 1]")

        if not (
            self.minimal_threshold
            <= self.competing_threshold
            <= self.counterexample_threshold
        ):
            raise ValueError("attack thresholds must be ordered")


@dataclass(frozen=True)
class ResourcePolicy:
    """Maps runtime resource state to search breadth.

    Resource state changes how much search is attempted.
    It never changes epistemic truth.
    """

    normal_branch_factor: int = 4
    constrained_branch_factor: int = 2

    def __post_init__(self) -> None:
        if self.normal_branch_factor < 1:
            raise ValueError("normal_branch_factor must be >= 1")
        if self.constrained_branch_factor < 1:
            raise ValueError("constrained_branch_factor must be >= 1")
        if self.constrained_branch_factor > self.normal_branch_factor:
            raise ValueError(
                "constrained_branch_factor cannot exceed normal_branch_factor"
            )

    def branch_factor(self, thermal_status: str, compute_budget: str) -> int:
        if thermal_status in {"critical", "unsafe", "unavailable"}:
            return 0

        if compute_budget in {"exhausted", "unavailable"}:
            return 0

        if thermal_status in {"high", "warning"}:
            return self.constrained_branch_factor

        if compute_budget in {"constrained", "low"}:
            return self.constrained_branch_factor

        return self.normal_branch_factor


@dataclass(frozen=True)
class AdversarialPlan:
    candidate_id: str
    pressure: float
    mode: str
    branch_factor: int
    resource_action: str

    # Explicitly prevents accidental interpretation as a truth decision.
    truth_status: str = "UNDETERMINED"

    # This is intentionally not called Gibbs free energy.
    thermodynamic_status: str = "SCAFFOLDING_ONLY"

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "pressure": self.pressure,
            "mode": self.mode,
            "branch_factor": self.branch_factor,
            "resource_action": self.resource_action,
            "truth_status": self.truth_status,
            "thermodynamic_status": self.thermodynamic_status,
        }


def adversarial_pressure(
    candidate: CandidateState,
    policy: AdversarialPolicy | None = None,
) -> float:
    """Return a dimensionless search-pressure score in [0, 1].

    This is a control/search score only. It is not Gibbs free energy,
    physical entropy, thermodynamic potential, confidence, or truth.
    """

    policy = policy or AdversarialPolicy()

    weighted = (
        candidate.uncertainty * policy.uncertainty_weight
        + candidate.disagreement * policy.disagreement_weight
        + candidate.novelty * policy.novelty_weight
        + candidate.verification_gap * policy.verification_gap_weight
        + candidate.refutation_risk * policy.refutation_risk_weight
    )

    total_weight = (
        policy.uncertainty_weight
        + policy.disagreement_weight
        + policy.novelty_weight
        + policy.verification_gap_weight
        + policy.refutation_risk_weight
    )

    return weighted / total_weight


def attack_mode(
    pressure: float,
    policy: AdversarialPolicy | None = None,
) -> str:
    """Select search intensity from pressure, never a truth outcome."""

    policy = policy or AdversarialPolicy()
    pressure = _bounded(pressure, "pressure")

    if pressure < policy.minimal_threshold:
        return "MINIMAL"

    if pressure < policy.competing_threshold:
        return "COMPETING"

    if pressure < policy.counterexample_threshold:
        return "COUNTEREXAMPLE"

    return "AGGRESSIVE"


def plan_adversarial_search(
    candidate: CandidateState,
    *,
    policy: AdversarialPolicy | None = None,
    resources: ResourcePolicy | None = None,
    thermal_status: str = "normal",
    compute_budget: str = "available",
) -> AdversarialPlan:
    """Create a deterministic adversarial search plan.

    The resource plane can reduce or stop search. It cannot alter
    the candidate's truth status.
    """

    policy = policy or AdversarialPolicy()
    resources = resources or ResourcePolicy()

    pressure = adversarial_pressure(candidate, policy)
    mode = attack_mode(pressure, policy)
    branch_factor = resources.branch_factor(thermal_status, compute_budget)

    if branch_factor == 0:
        resource_action = "STOP_SEARCH"
        mode = "STOPPED"
    elif branch_factor < resources.normal_branch_factor:
        resource_action = "REDUCE_SEARCH"
    else:
        resource_action = "SEARCH"

    return AdversarialPlan(
        candidate_id=candidate.candidate_id,
        pressure=pressure,
        mode=mode,
        branch_factor=branch_factor,
        resource_action=resource_action,
    )


def topology_descriptor(
    *,
    beta_0: int,
    beta_1: int,
    beta_2: int,
    topology_constraint: str = "not_applicable",
) -> dict[str, Any]:
    """Record topology descriptively; do not turn it into a truth criterion."""

    for name, value in (
        ("beta_0", beta_0),
        ("beta_1", beta_1),
        ("beta_2", beta_2),
    ):
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(f"{name} must be a non-negative integer")

    if not topology_constraint:
        raise ValueError("topology_constraint must not be empty")

    return {
        "betti": {
            "beta_0": beta_0,
            "beta_1": beta_1,
            "beta_2": beta_2,
        },
        "topology_constraint": topology_constraint,
    }


def adversarial_evidence(
    *,
    candidate_id: str,
    attack_id: str,
    attack_type: str,
    target: str,
    result: str,
    evidence_refs: tuple[str, ...] = (),
    verification: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Create an evidence-shaped adversarial observation.

    This object does not certify the candidate as true or false.
    It is intended to enter the existing EvidenceRecord/Ledger path.
    """

    if not candidate_id:
        raise ValueError("candidate_id must not be empty")
    if not attack_id:
        raise ValueError("attack_id must not be empty")
    if not attack_type:
        raise ValueError("attack_type must not be empty")
    if not target:
        raise ValueError("target must not be empty")
    if not result:
        raise ValueError("result must not be empty")

    return {
        "candidate_id": candidate_id,
        "attack_id": attack_id,
        "attack_type": attack_type,
        "target": target,
        "result": result,
        "evidence_refs": list(evidence_refs),
        "verification": dict(verification or {}),
        "epistemic_status": "OBSERVATION",
        "truth_status": "UNDETERMINED",
    }
