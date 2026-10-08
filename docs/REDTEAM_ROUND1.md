# 🔴 Red Team Challenge — Round 1: Break the Gate Contract

**Target:** Sovereign Veritas `sv.gate/0`
**Frozen commit:** `709da9eb435cbfe06a1ca00427843b12c673ceb0`

Repository:

https://github.com/holland202/sovereign-veritas

Contract:

https://github.com/holland202/sovereign-veritas/blob/709da9eb435cbfe06a1ca00427843b12c673ceb0/CONTRACT.md

## Mission

Break the Gate **without modifying it**.

Find one concrete input where the public contract says the result must be `DEFER` or `REFUSE` but the frozen implementation returns `ALLOW`.

## Target

The Gate contract is `sv.gate/0`.

At the frozen target:

- 4,690 conformance vectors are defined;
- the kernel produces the expected conformance digest;
- baseline tests pass.

The challenge is to find something **outside the already-covered cases**.

## Attack surface

You may investigate:

- JSON representations;
- null and boolean handling;
- numeric edge cases;
- equality and type boundaries;
- Unicode;
- omitted versus present fields;
- conflicting fields;
- serialization/deserialization;
- parser behavior;
- rule ordering;
- interactions between independent contract rules;
- package-to-Gate interpretation;
- any other reachable input that should be governed by the frozen contract.

## Rules

1. Do not modify the target implementation.
2. Do not use signing keys or private credentials.
3. Do not alter the contract or vectors.
4. The attack must be reproducible.
5. “This could theoretically fail” is not enough.
6. Submit the smallest useful reproducer you can find.
7. A specification ambiguity is worth reporting even if it is not a confirmed implementation break.
8. Failed attacks and careful null results are useful evidence.

## Required submission

Provide:

```text
Target commit:
Input:
Expected decision:
Observed decision:
Exact command:
Raw output:
Violated contract rule:
Explanation:
```

A script or patch that reproduces the attack is strongly preferred.

## What does NOT count

Already-published limitations are not new Round 1 discoveries merely because they are reproduced.

The project already documents known issues involving, among other things:

- unsigned or fully self-consistent rewrites;
- known execution-boundary limitations;
- known consumer races;
- known provenance/evidence limitations.

Check `CHALLENGE.md` before claiming a break.

## Independent implementation bonus

Implement `sv.gate/0` independently from `CONTRACT.md` and run the complete 4,690-vector conformance check.

A disagreement is valuable.

Agreement is also valuable.

The goal is not to prove the project correct.

The goal is to discover where the specification and implementation fail to hold.

## Research status

Sovereign Veritas is an experimental research prototype.

**NOT VALIDATED.**

No result from this challenge should be interpreted as proof of production security, truth of recorded evidence, or correctness outside the tested model.
