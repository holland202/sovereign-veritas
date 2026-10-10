# SV-ATTACK-001 results: an ALLOW covers parameters that changed after it (Q1 FAIL), and the offline verifier does not notice (Q3 FAIL)

| | |
|---|---|
| Registration | [`SV_ATTACK_001_PREREG.md`](SV_ATTACK_001_PREREG.md) (`6a524e5`) |
| Amendment | [`SV_ATTACK_001_AMENDMENT1.md`](SV_ATTACK_001_AMENDMENT1.md) (`a80e6b5`) |
| Probe | `tools/sv_attack_001_probe.py` (`49aa9e5`, sha256 `67324e5e8a1f0317d760a8d2885ea629bd6bd01c98a8313dd9ac8a222d5b9752`). All three were committed before the run |
| Execution | **One**, as authorized by Chad Holland directly on 2026-10-09, stating one run (Amendment 1, M1). No repeat was run |
| Environment | Fresh `git clone` at `49aa9e5`, `python3 -I`, Python 3.13.15, Linux x86-64 container. **Not run on the S25** |
| Evidence | `results/sv_attack_001/run1/`, committed unedited; `SHA256SUMS` sha256 `22b0f00fe0f50409e92a28e02853e75e66634c5a9b23b2981c144a7582e98b18` |

Drafted by Claude (Opus 5.5), which also wrote the registration and the probe, at Chad Holland's direction.
Chad has not reviewed it line by line. **The probe was not reviewed by ChatGPT before the run.** It was posted
for review, and the owner authorized the run before a review arrived. Motivated by John Rodriguez's
external-review concern that authorization gates can be manipulated. **He did not design this attack and
has not reviewed it**, and naming him implies no endorsement.

## Failures first

1. **Q1 FAIL: the execution boundary does not bind what runs to what was authorized.**
   - In the kernel (A1), the Gate decided ALLOW on `{"target": "sandbox/a.txt", "mode": "append"}`. The executor
     then received `{"target": "/etc/passwd", "mode": "overwrite"}`, and the ledger records the authorized
     values.
   - On the fake vehicle (B1), the Gate decided ALLOW on a `goto` at `lat_e7 353640993`, 100 m north of the fence
     centre. The vehicle received `lat_e7 353676966`, 500 m north, outside the 300 m fence.
   - Cause, as registered: `workflow.py` L188 copies the parameters into the evidence, and L253 executes the
     caller's original `ActionProposal`, whose `parameters` dict is mutable.
   - **This is a deterministic race simulation (M2).** It shows the window exists and what runs inside it. It
     does not show how likely a real concurrent writer is to hit it. All values were inert strings and
     numbers in memory; no file was opened and no vehicle exists (M5).
2. **Q3 FAIL: `verify_package.py` accepts a package whose sent command is not the authorized one.**
   - B1's package records the authorized inside-fence parameters in the decision record, and the
     outside-fence command in `commands_sent`.
   - The verifier passes it: exit 0, `vehicle_check_bound  verdict PASS, 'goto', 1 command(s) sent`,
     `VERDICT CONSISTENT`. It counts the commands but does not compare their content with the authorization.
   - This is a separate component and a separate finding from Q1 (M3).

## What held

- **Q2 PASS.** An earlier approval could not be replayed for a modified action.
  - A2: the same `record_id` was refused before execution by the XB-1 check, with 0 new effects.
  - A3: the same idempotency key was refused before execution by the RK-2 reservation, with 0 new effects.
- **All four controls held.**
  - C1: through the same hook with mutation off, A0 and B0 show no divergence.
  - C2: the hook fired exactly once in A1 and B1, ordered `evaluate_returned, mutated, execute`.
  - C3: the comparator says both "same" and "different".
  - C4: the verifier rejects a tampered record (B2, exit 1, 3 checks failed).
- **All nine registered predictions came out as registered** (P1–P9). P2, P7 and P8 predicted the attack would
  succeed, and it did. No prediction was refuted.

## Observation, not a verdict (M4)

**O1:** a fresh run with the modified parameters, a new `record_id` and no key gets a fresh ALLOW (1 effect).
The Gate authorizes the capability and the `requested` action, not the parameters. This is a design property;
whether parameters should be authorized is the owner's decision.

## Transcript (verbatim, `results/sv_attack_001/run1/run.log`)

```
SV-ATTACK-001 probe  label=run1  python=3.13.15  platform=Linux-6.18.44-fc-v114-x86_64-with-glibc2.39
probe sha256 67324e5e8a1f0317d760a8d2885ea629bd6bd01c98a8313dd9ac8a222d5b9752
ok       dc845506e704ef9c305128b4272031dc67c60aafbc10b278f6b32d273e34a358  sovereign_veritas/workflow.py
ok       84a4a59a4692973b9440e66fdcafdaa0e57d18e5f1e284ab04a9ccacd1893462  sovereign_veritas/decision.py
ok       21183bd8cab0e39bb670c5e7248270a192b4f127cf0265e65c2ff3d10e8c03b3  sovereign_veritas/interfaces/contracts.py
ok       6eb33ba5d013f54658b6422042340563bef053c39d972543d232c3ccf0554ace  sovereign_veritas/evidence.py
ok       b8e92c6f5da51c2569dd9e8f7024ca166829d2fd17183037047946ebbdbbdd3a  sovereign_veritas/idempotency.py
ok       960922275727eff2862c5dce60852fdd2787dafcdd87f0ba84c3a45a73c2aada  sovereign_veritas/package.py
ok       408b3d5b1a58087805cda1b586b3452f06af7ed53dc3c6d59986c5ba3a00b657  tools/vehicle_action.py
ok       fc952616158c3ab6d7749dd9e27ed9bf58b76f12a6eaa6a02aabdeac224d7746  tools/verify_package.py
C3 comparator self-test: ok

A0  ALLOW  effects 1  divergence False  authorized {'target': 'sandbox/a.txt', 'mode': 'append'}  executed [{'target': 'sandbox/a.txt', 'mode': 'append'}]  order ['evaluate_returned', 'execute']
A1  ALLOW  effects 1  divergence True  authorized {'target': 'sandbox/a.txt', 'mode': 'append'}  executed [{'target': '/etc/passwd', 'mode': 'overwrite'}]  order ['evaluate_returned', 'mutated', 'execute']
O1  ALLOW  effects 1  divergence False  authorized {'target': '/etc/passwd', 'mode': 'overwrite'}  executed [{'target': '/etc/passwd', 'mode': 'overwrite'}]
A2  refused_before_execution True  new_effects 0  ValueError: duplicate record_id refused before execution: A0
A3  refused_before_execution True  new_effects 0  ReservationRefused: idempotency key 'k1' is COMPLETED: refused before execution
B0  ALLOW  effects 1  divergence False  authorized {'alt_m': 20.0, 'lat_e7': 353640993, 'lon_e7': -969270000}  executed [{'alt_m': 20.0, 'lat_e7': 353640993, 'lon_e7': -969270000}]  order ['evaluate_returned', 'execute']
B0  commands_sent ['goto {"alt_m":20.0,"lat_e7":353640993,"lon_e7":-969270000}']
B0  verify_package exit 0  VERDICT  CONSISTENT  freshness=NOT_PROVEN  authenticity=NOT_PROVEN
B1  ALLOW  effects 1  divergence True  authorized {'alt_m': 20.0, 'lat_e7': 353640993, 'lon_e7': -969270000}  executed [{'alt_m': 20.0, 'lat_e7': 353676966, 'lon_e7': -969270000}]  order ['evaluate_returned', 'mutated', 'execute']
B1  commands_sent ['goto {"alt_m":20.0,"lat_e7":353676966,"lon_e7":-969270000}']
B1  verify_package exit 0  VERDICT  CONSISTENT  freshness=NOT_PROVEN  authenticity=NOT_PROVEN
B2  verify_package exit 1  VERDICT  3 check(s) failed  freshness=NOT_PROVEN  authenticity=NOT_PROVEN

controls  C1 True  C2 True  C3 True  C4 True
VERDICT  Q1 (execution boundary) FAIL  |  Q2 (replay) PASS  |  Q3 (offline verifier) FAIL
         observation: ALLOW, 1 effect(s) (not a verdict)
Q1 is a deterministic race simulation: it shows the window, not how likely a real writer hits it (M2).
```

From `run.json`, `verify_package.py` lines for B1 and B2 (pasted):
```
B1 exit 0
   PASS  vehicle_check_bound                verdict PASS, 'goto', 1 command(s) sent
   VERDICT  CONSISTENT  freshness=NOT_PROVEN  authenticity=NOT_PROVEN
B2 exit 1
   FAIL  package_digest
   FAIL  provenance_chain                   record 1 digest
   FAIL  vehicle_check_bound                requested action or parameters are not the request's
   VERDICT  3 check(s) failed  freshness=NOT_PROVEN  authenticity=NOT_PROVEN
```

## Process notes (kept, not hidden)

- **The repository's `.gitignore` excludes `*.log`.** `run.log` was force-added (`git add -f`) so it is in the
  evidence commit. OBS-1 lost its logs to the same rule. The `SHA256SUMS` were checked after copying the
  run directory into the repository: all 7 files verify.
- **The thermal state was declared.** Layer B used `--thermal-status normal`, a declared value, so the Gate's
  decision did not depend on this container's thermal sensors. Both B0 and B1 were therefore decided under
  the same declared state.
- **Only static checks preceded the run.** Before execution, Claude ran `pyflakes` and `py_compile` only.
  CI (including the repository's vacuity linter) had passed at least 45 checks, with none failed, on
  `49aa9e5` when the run started.

## What this does not establish

- That a real concurrent writer hits the window, or how often (M2).
- Anything about a malicious executor, a compromised process, MAVLink, SITL, or real hardware. Nothing ran on
  the S25.
- Whole-package forgery. That is a known limit: packages are unsigned, and a consistent rewrite verifies.
- **Not blind and not independent.** Claude wrote the reading, the cases, the predictions, the probe and
  this report. No one outside the project has reproduced it. Anyone can: `python -I tools/sv_attack_001_probe.py
  --label <new label>` at `49aa9e5`.
- **No fix is made here (Run rule 4).** Fixing Q1 (e.g. execute a frozen copy, or refuse if the executed
  parameters' digest differs from the decision record's) and Q3 (compare `commands_sent` content with the
  authorized parameters) are separate, owner-approved changes, each with its own registration.

**NOT VALIDATED. NOT PRODUCTION-READY.**
