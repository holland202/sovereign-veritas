from __future__ import annotations

import pytest

from sovereign_veritas.adversarial import (
    AdversarialPolicy,
    CandidateState,
    ResourcePolicy,
    adversarial_evidence,
    adversarial_pressure,
    attack_mode,
    plan_adversarial_search,
    topology_descriptor,
)


def candidate(**overrides):
    values = {
        "candidate_id": "c-001",
        "uncertainty": 0.5,
        "disagreement": 0.5,
        "novelty": 0.5,
        "verification_gap": 0.5,
        "refutation_risk": 0.5,
    }
    values.update(overrides)
    return CandidateState(**values)


def test_pressure_is_deterministic_and_bounded():
    c = candidate(
        uncertainty=1.0,
        disagreement=0.0,
        novelty=0.5,
        verification_gap=0.5,
        refutation_risk=1.0,
    )

    first = adversarial_pressure(c)
    second = adversarial_pressure(c)

    assert first == second
    assert 0.0 <= first <= 1.0


def test_attack_modes_are_search_intensity_only():
    assert attack_mode(0.10) == "MINIMAL"
    assert attack_mode(0.30) == "COMPETING"
    assert attack_mode(0.55) == "COUNTEREXAMPLE"
    assert attack_mode(0.90) == "AGGRESSIVE"


def test_plan_never_claims_truth():
    plan = plan_adversarial_search(candidate())

    assert plan.truth_status == "UNDETERMINED"
    assert plan.thermodynamic_status == "SCAFFOLDING_ONLY"
    assert plan.mode != "ALLOW"
    assert plan.mode != "REFUSE"


def test_resource_constraints_reduce_search_not_truth():
    c = candidate()

    normal = plan_adversarial_search(
        c,
        thermal_status="normal",
        compute_budget="available",
    )

    constrained = plan_adversarial_search(
        c,
        thermal_status="high",
        compute_budget="constrained",
    )

    assert constrained.branch_factor < normal.branch_factor
    assert constrained.truth_status == normal.truth_status
    assert constrained.thermodynamic_status == normal.thermodynamic_status


def test_critical_resources_stop_search():
    plan = plan_adversarial_search(
        candidate(),
        thermal_status="critical",
        compute_budget="available",
    )

    assert plan.branch_factor == 0
    assert plan.resource_action == "STOP_SEARCH"
    assert plan.mode == "STOPPED"
    assert plan.truth_status == "UNDETERMINED"


def test_exhausted_compute_stops_search():
    plan = plan_adversarial_search(
        candidate(),
        thermal_status="normal",
        compute_budget="exhausted",
    )

    assert plan.branch_factor == 0
    assert plan.resource_action == "STOP_SEARCH"
    assert plan.truth_status == "UNDETERMINED"


def test_topology_is_descriptive():
    topology = topology_descriptor(
        beta_0=1,
        beta_1=3,
        beta_2=0,
        topology_constraint="not_applicable",
    )

    assert topology["betti"]["beta_0"] == 1
    assert topology["betti"]["beta_1"] == 3
    assert topology["betti"]["beta_2"] == 0
    assert topology["topology_constraint"] == "not_applicable"


def test_topology_does_not_encode_universal_beta_constraints():
    topology = topology_descriptor(
        beta_0=1,
        beta_1=7,
        beta_2=2,
        topology_constraint="task_specific",
    )

    assert topology["betti"] == {
        "beta_0": 1,
        "beta_1": 7,
        "beta_2": 2,
    }


def test_custom_policy_is_deterministic():
    policy = AdversarialPolicy(
        uncertainty_weight=1.0,
        disagreement_weight=0.0,
        novelty_weight=0.0,
        verification_gap_weight=0.0,
        refutation_risk_weight=0.0,
    )

    assert adversarial_pressure(candidate(uncertainty=0.8), policy) == 0.8
    assert adversarial_pressure(candidate(uncertainty=0.2), policy) == 0.2


@pytest.mark.parametrize(
    "field",
    [
        "uncertainty",
        "disagreement",
        "novelty",
        "verification_gap",
        "refutation_risk",
    ],
)
def test_candidate_metrics_are_bounded(field):
    values = {
        "uncertainty": 0.5,
        "disagreement": 0.5,
        "novelty": 0.5,
        "verification_gap": 0.5,
        "refutation_risk": 0.5,
    }

    values[field] = 1.1

    with pytest.raises(ValueError):
        CandidateState(candidate_id="bad", **values)


def test_adversarial_evidence_is_observation_not_truth():
    evidence = adversarial_evidence(
        candidate_id="c-001",
        attack_id="a-001",
        attack_type="counterexample",
        target="hypothesis",
        result="candidate_survived",
        evidence_refs=("ev-001",),
        verification={"status": "PENDING"},
    )

    assert evidence["epistemic_status"] == "OBSERVATION"
    assert evidence["truth_status"] == "UNDETERMINED"
    assert evidence["evidence_refs"] == ["ev-001"]


def test_adversarial_evidence_does_not_self_certify():
    evidence = adversarial_evidence(
        candidate_id="c-001",
        attack_id="a-002",
        attack_type="mutation",
        target="hypothesis",
        result="counterexample_found",
        verification={"status": "PASS"},
    )

    assert evidence["truth_status"] == "UNDETERMINED"
    assert evidence["epistemic_status"] == "OBSERVATION"
