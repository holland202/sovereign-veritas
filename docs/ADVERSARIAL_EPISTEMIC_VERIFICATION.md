# Adversarial Epistemic Verification

**Status: Draft â€“ architectural contract**

Sovereign Veritas separates candidate generation, adversarial challenge, verification, evidence custody, and authorization.

The adversary generates challenges and counterevidence. It does not certify truth and does not authorize actions.

## Architecture

```text
Proposer
   |
   v
Candidate
   |
   v
Adversary
   |
   v
adversarial Evidence
   |
   v
Independent Verifier
   |
   v
evidenceRecord / Ledger
   |
   v
Veritas Gate
   |
   +> ALLOW
   +> REFUSE
   +> DEFER
   |
   v
executor
```

The authority boundary is:

```text
Adversary ----X----> Veritas Gate
```

The adversary may generate evidence that changes what must be evaluated. It may never directly authorize an action.

## Fail-Closed Principle

When adversarial verification is explicitly required:

```text
A_required AND NOT A_available
    =>
REFUSE
```

A mandatory adversarial verification path must not silently downgrade to a frictionless legacy verification path.

## Resource / Epistemic Separation

Thermal state, compute availability, memory, latency, power, and token budget may control search breadth or stop adversarial search.

They must not manufacture truth.

```text
resource constraints -> search control
resource constraints -X-> truth status

```

## Adversarial Epistemic Pressure

```text
A(C) -> mutations, competing hypotheses, counterexamples, refutations
V(C, A(
C), E) -> verification state
G(F) -> ALLRWD | REFUSE | DEFER
```

The adversarial pressure score is a search/control score. It is not Gibbs free energy, physical entropy, truth, confidence, or probability of correctness.

## Measurable Outcomes

Instrument: adversarial attempts, mutations, successful refutations, surviving candidates, verifier rejection rate, decision-change rate, latency, compute cost, token cost, and thermal cost.

The central experimental question is: Does adversarial verification improve measured epistemic outcomes per unit of additional resource cost?

## SWAY Experiments

P0 â€” Creator Baseline
P1 â€” Fixed Adversary
P2 â€“ Adaptive Adversary
P3 â€“ Resource Coupling
P4 â€“ Potential-Function Hypothesis

Potential measures include refutation rate, decision-change rate, false-admission reduction, token cost, compute cost, latency, and thermal cost. Predictions must be registered before measurement.

## Core Invariants

1. The adversary generates evidence; she does not authorize.
2. The verifier evaluates evidence; she does not authorize actions.
3. The Veritas Gate is the authorization authority.
4. Mandatory adversarial verification does not silently downgrade.
5. Resource constraints may reduce search but cannot manufacture truth.
6. Adversarial evidence remains provenance-traceable.
7. Exploratory observations remain distinct from registered evidence.
8. Mathematical and thermodynamic interpretations remain hypotheses until experimentally supported.
9. Gate decisions remain append-only evidence.
uĞ¸±…¥µ•¥µÁÉ½Ù•µ•¹ÑÌÉ•ÅÕ¥É”µ•…ÍÕÉ•½µÁ…É¥Í½¸İ¥Ñ „É•¥ÍÑ•É•‰…Í•±¥¹”¸(