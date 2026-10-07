# Capability custody: does a revocation reach the decision? (R1–R3)

Found 2026-10-07 during an adversarial review requested by Chad Holland (Claude, Opus 5.5; **self-tested**, container
only, **S25 NOT VALIDATED**). Not registered in advance: these are probes of a documented design claim, run against
`48ab26a`. Raw output: the probe and its output are reproduced below.

## The claim tested

README, core idea 7: "Authorization changes are ledgered **before** the registry mutates", and "If custody fails, the
registry does not change." `CapabilityGovernor` implements that custody. The claim implies the registry is the authority.
The probe asked whether the registry's state is what decides.

## Observed before the fix (`48ab26a`)

```
registry now says authorized = False | ledger records: ['auth-1', 'revoke-1']
R1 workflow decision with held capability: ALLOW | effects: 1
R1b Gate.evaluate(held, registry=reg): ALLOW
R1c Gate.evaluate(reg.get('act')): REFUSE
R2 workflow, child of authorized root: REFUSE ['capability_parent_requires_registry'] | Gate with registry: ALLOW
R3 package: capability.authorized = True | capability_registry['act'].authorized = False
R3 verifier: VERDICT  CONSISTENT  freshness=NOT_PROVEN  authenticity=NOT_PROVEN (exit 0 )
```

- **R1, false ALLOW under the declared custody model.** A revocation that was ledgered and applied to the registry did
  not stop execution: `EvidenceWorkflow` (and the Gate) decide on the `Capability` object the caller passes, and a caller
  holding the pre-revocation object got ALLOW and an effect. The Gate uses a registry only for a capability's *parent*.
  Related to issue #4 B2 ("authorization is a mutable bit"), but distinct: here the authority *did* change and the
  decision did not see it.
- **R2, fail-closed availability defect.** `EvidenceWorkflow.run` called `gate.evaluate` without a registry, so every
  capability with a parent was REFUSED (`capability_parent_requires_registry`) on the execution path.
- **R3, false CONSISTENT from an honest producer.** `build_package` wrote a package whose registry snapshot revoked the very
  capability its `gate_inputs.capability` called authorized, with decision ALLOW, and `verify_package.py` said CONSISTENT.
  No attacker or resealing was involved; a signature would have made it `SIGNED` as well.

## Fix

- `EvidenceWorkflow(capability_registry=...)`: when configured, the registry's current entry for the capability's name
  decides (a name the registry does not hold gives `capability_missing`), and the registry is passed to the Gate, so
  parents are checked. The record's metadata says `capability_source: registry` and whether the caller's object differed.
  Without a registry nothing changes, and the record says `capability_source: caller`: authorization is then still a
  label the caller writes (B2), now stated in every record.
- `build_package` refuses a capability that differs from its own entry in the registry snapshot.
- `verify_package.py`: new check `capability_matches_registry` when the snapshot holds the capability's name.
- **Not changed:** the Gate and `CONTRACT.md` (`sv.gate/0`). The Gate remains a pure function of recorded inputs; sourcing
  current authority is the workflow's job. Conformance digest unchanged.

## Regression

`tests/test_capability_custody.py`: 7 tests, all failing on `48ab26a` (the new parameter did not exist; the behaviour
they guard is the output above), 7 passing after. Full suite: 491 passed, 1 skipped.

## What this does not fix

- Revocation **during** an execution (after the decision, before the effect) is a time-of-check/time-of-use gap; the
  registry is read once, at decision time.
- Nothing authenticates who may call `CapabilityGovernor.revoke/authorize`; the custody is a ledger record, not a
  principal (issue #4 B2's proposed "signed grant").
- Workflows built without a registry keep the old behaviour; production use should always configure one. The default is
  kept for compatibility and is labelled in every record.
