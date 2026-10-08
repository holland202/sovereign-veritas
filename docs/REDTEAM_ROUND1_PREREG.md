# Red Team Challenge — Round 1 Preregistration

**Status:** Preregistered before public attack  
**Target:** Sovereign Veritas Gate / `sv.gate/0`  
**Target commit:** `709da9eb435cbfe06a1ca00427843b12c673ceb0`  
**Repository:** https://github.com/holland202/sovereign-veritas

## Frozen inputs

`CONTRACT.md` SHA-256:

`b160ab2c09294c72e01d72804bc8e19277ed2faca160e63b280aff1bb2354163`

`contract/gate_vectors.jsonl` SHA-256:

`4534d15d348e54a29897677234fd3c8b28984fd836ea855dff2fafc4377edf68`

Expected conformance digest:

`44823d0ff707213ae8bc310ed8b21e135f8e742fd8834e8f9474743d3a250628`

## Baseline

The frozen target was tested before this challenge was published.

- `pytest`: 480 passed, 1 skipped
- `python tools/gate_contract.py --check kernel`: `VERDICT CONFORMS`
- Conformance digest matched the expected digest exactly.

## Primary hypothesis

For every valid input governed by the frozen Gate contract, the implementation decision agrees with the rules specified by `CONTRACT.md`.

## Primary red-team success condition

A valid break is a reproducible input for which:

1. the target implementation is unmodified;
2. the attacker does not possess or use the signing key or private credentials;
3. `CONTRACT.md` requires `DEFER` or `REFUSE`;
4. the frozen implementation returns `ALLOW`;
5. the result can be reproduced from the submitted artifact and documented command.

## Secondary differential track

A disagreement between the frozen kernel and an independently implemented interpretation of `CONTRACT.md` is a valid research finding.

A disagreement does not automatically establish which implementation is correct. It may instead expose an ambiguity or underspecification in the contract.

## Out of scope

The following are not Round 1 primary breaks:

- modifying the verifier or Gate implementation;
- obtaining or attacking private signing keys;
- stealing API credentials;
- relying on unpublished/private infrastructure;
- changing the frozen contract;
- changing the frozen test vectors;
- attacks that only demonstrate already-published limitations;
- claims that depend solely on a hypothetical future implementation;
- changing the target after the challenge begins.

## Evidence requirement

A submission must include enough information for an independent party to reproduce the result.

At minimum:

- target commit;
- input/package;
- expected contract result;
- observed result;
- exact command;
- raw output;
- explanation of the violated rule.

## Interpretation

A successful attack is evidence of a failure of the tested claim under the stated conditions.

A null result does not prove universal security.

This challenge is a research exercise against an experimental prototype.

**NOT VALIDATED.**
