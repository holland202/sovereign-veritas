# SV-ATTACK-001: can an ALLOW be reused to execute an action whose parameters changed after authorization?

**Status: REGISTERED, UNRUN.** This file was committed alone, before the probe (`tools/sv_attack_001_probe.py`)
existed. Nothing below has been executed. Registered 2026-10-09 by Claude (Opus 5.5) at Chad Holland's
direction. Chad has not reviewed it line by line. No gate, workflow or verifier code is changed by this
registration, and none may be changed by the run (see "Run rules").

Repository state: maintenance-only since v0.2.0. This is a security investigation, which the maintenance
notice permits. It adds no feature, and any fix would be a separate, owner-approved change.

## Origin and credit (kept at its stated strength)

- **John Rodriguez** raised in external review (2026-10) that an authorization gate can be manipulated, and
  that an authorization record can be clean while the premise behind it is wrong. That concern motivates this
  test. **He did not propose this attack design and has not reviewed it.** Naming him does not imply he
  endorses the design, the code or any result.
- The specific idea, substituting what is executed after an ALLOW, was suggested by **ChatGPT (OpenAI)** in
  the project's two-AI review channel. **Claude** turned it into the cases below after reading the code.

## Target (exact bytes)

Code at `main` = `438e6d5`. `git diff --stat ecd4de9 438e6d5 -- sovereign_veritas tools` is empty, so this is
also the code of release `v0.2.0` (`ecd4de9`).

| File | sha256 at 438e6d5 | Last change |
|---|---|---|
| `sovereign_veritas/workflow.py` | `dc845506e704ef9c305128b4272031dc67c60aafbc10b278f6b32d273e34a358` | `40fe508` |
| `sovereign_veritas/decision.py` | `84a4a59a4692973b9440e66fdcafdaa0e57d18e5f1e284ab04a9ccacd1893462` | `9308ce3` |
| `sovereign_veritas/interfaces/contracts.py` | `21183bd8cab0e39bb670c5e7248270a192b4f127cf0265e65c2ff3d10e8c03b3` | `59cda8b` |
| `sovereign_veritas/evidence.py` | `6eb33ba5d013f54658b6422042340563bef053c39d972543d232c3ccf0554ace` | `6e1f9b4` |
| `sovereign_veritas/idempotency.py` | `b8e92c6f5da51c2569dd9e8f7024ca166829d2fd17183037047946ebbdbbdd3a` | `f4022bc` |
| `sovereign_veritas/package.py` | `960922275727eff2862c5dce60852fdd2787dafcdd87f0ba84c3a45a73c2aada` | `4989379` |
| `tools/vehicle_action.py` | `408b3d5b1a58087805cda1b586b3452f06af7ed53dc3c6d59986c5ba3a00b657` | `2902a2c` |
| `tools/verify_package.py` | `fc952616158c3ab6d7749dd9e27ed9bf58b76f12a6eaa6a02aabdeac224d7746` | `bf6d76a` |

The probe must recompute these hashes before any case runs. A mismatch stops the run as **INCONCLUSIVE**.

## The code paths involved (a reading, not evidence)

**Kernel: `EvidenceWorkflow.run()` (`workflow.py`).**
1. L82–87: duplicate `record_id` refused before anything runs (XB-1 fix). An `idempotency_key` without a
   store is refused.
2. L89–181: sense, predict, verify.
3. **L183–189: the action is copied into the evidence**, as
   `{"capability", "requested", "parameters": dict(action.parameters)}`. `EvidenceRecord.__post_init__`
   (`evidence.py`) then deep-freezes it (`_freeze`: MappingProxy and tuples).
4. **L222–227: `Gate.evaluate()` decides on that frozen copy.** `decision.py` checks verification,
   capability, the parent capability, `action.capability` against the capability name, runtime state,
   required evidence, the quality threshold, steps, and `requested` against `policy["allow_only"]`.
   **It reads no other parameter.**
5. L248–251: if a key was given, it is reserved (RK-2). The reservation is keyed by the key only, not by
   the parameters.
6. **L253: `self.executor.execute(action)` receives the caller's original `ActionProposal`.**
   `ActionProposal` is a frozen dataclass, but its `parameters` field is an ordinary mutable `dict`
   (`contracts.py` L15–18).
7. L305: the record written to the ledger holds the copy made at step 3, not what was executed.

**Concrete executor: `tools/vehicle_action.py`.** `params` is one dict object shared by `req["params"]`,
the `Check` verifier (which holds `req`) and `ActionProposal(..., params)`. `Execute.execute` calls
`vehicle.run(action.requested, action.parameters)`. `FakeVehicle.run` appends the command with its actual
parameters to `commands`.

**Offline verifier: `tools/verify_package.py`, `vehicle_command_check`** (L991–1011):
- It checks that the record's `action.parameters` equal the request's `params`, and that `commands_sent` is
  a list sent only under ALLOW with SUCCEEDED/FAILED.
- **It does not compare the content of `commands_sent` with the authorized parameters.**
- Packages are unsigned; `package.py` states "a fully consistent rewrite verifies". So forging a whole
  package is a known limit and is **out of scope here**.

**The window under test:** between the snapshot (L188) and `execute()` (L253), anything holding a reference
to the same `parameters` dict can change what runs. The gate's decision and the ledger record keep the old
values.

## Threat model

An in-process party, such as another thread, a plugin, or a component handed the same request object, holds a
reference to the action's `parameters` dict and changes it after the Gate has decided, before execution.
The executor is trusted and honest; it runs what it is given. Out of scope:
- a malicious executor;
- a compromised interpreter;
- forging whole packages offline;
- network or MAVLink attackers.

**Deterministic stand-in for the race.** The probe does not race real threads. A harness-only wrapper
around the Gate instance calls the real, unmodified `Gate.evaluate()`, returns its decision unchanged, and
then, in mutating cases only, changes the shared dict. This places the change exactly inside the window,
every time. The wrapper is installed by the probe on its own object, and no repository file is edited.

## Cases

All effects are in memory or on `FakeVehicle` (`fake:healthy_air`, a canned stand-in, not a vehicle).
No MAVLink, no SITL, no network, no S25 hardware. Every case is non-destructive.

**Layer A: kernel, with a recording executor that stores a deep copy of the parameters it receives.**

| ID | Case | Mutation |
|---|---|---|
| A0 | Legitimate action, `{"target": "sandbox/a.txt", "mode": "append"}`, capability authorized, policy allows `write` | none |
| A1 | Same as A0; after the Gate decides, the shared dict becomes `{"target": "/etc/passwd", "mode": "overwrite"}` | after decision |
| A2 | A0 runs, then a second run reuses A0's `record_id` with modified parameters | before the run |
| A3 | A0 runs with `idempotency_key="k1"`, then a second run with a new `record_id`, the same key and modified parameters | before the run |
| O1 | (observation) A new run with a new `record_id`, no key, and the modified parameters | before the run |

**Layer B: `tools/vehicle_action.py` on `fake:healthy_air`, fence radius 300 m, then `tools/verify_package.py`
on the package written.** `HOME` is a fresh temporary directory per case.

| ID | Case | Mutation |
|---|---|---|
| B0 | Legitimate `goto` 100 m north, alt 20 m (inside the fence) | none |
| B1 | Same as B0; after the Gate decides, the shared `params` becomes 500 m north (outside the fence) | after decision |
| B2 | (anti-vacuity of the verifier) B0's package with the record's `action.parameters` edited and no digest recomputed | offline edit |

**Measured per case:** decision and reasons; the authorized parameters (from the ledger's decision record);
the executed parameters (executor copy, or `FakeVehicle.commands`); sha256 of each, over canonical JSON;
effect count; the ledger record digest. For layer B also the package sha256 and the verbatim
`verify_package.py` output and exit code.

**Divergence** = an effect executed under ALLOW whose executed-parameters sha256 differs from the
authorized-parameters sha256 in that run's decision record.

## Predictions (made from the code reading above, before any code exists)

| P | Case | Predicted outcome |
|---|---|---|
| P1 | A0 | ALLOW, 1 effect, no divergence |
| P2 | A1 | **ALLOW, 1 effect, divergence**: the executor receives `/etc/passwd`/`overwrite`, while the ledger records `sandbox/a.txt`/`append` |
| P3 | A2 | second run refused before execution (`duplicate record_id`), 0 new effects |
| P4 | A3 | second run raises `ReservationRefused` before execution, 0 new effects |
| P5 | O1 | ALLOW and 1 effect: a **fresh** authorization, not reuse. It shows the Gate authorizes capability and `requested`, not parameters. Recorded as an observation; no verdict |
| P6 | B0 | ALLOW, 1 command with the authorized parameters, `verify_package.py` exit 0 |
| P7 | B1 | **ALLOW, the fake vehicle receives the outside-fence `goto`**; the decision record holds the inside-fence parameters |
| P8 | B1 package | **`verify_package.py` exit 0 (all checks pass)** even though `commands_sent` shows parameters that were never authorized |
| P9 | B2 | `verify_package.py` exit non-zero (record digest or package digest check fails) |

P2, P7 and P8 predict that the attack **succeeds**. They are predictions about the code, not hopes: if any
of them is wrong, that is a refuted prediction, kept and explained.

## Anti-vacuity controls

- **C1 (hook is not the cause):** A0 and B0 run through the same wrapper with mutation switched off. They
  must show no divergence. If they diverge, the harness is broken and the run is INCONCLUSIVE.
- **C2 (the hook fired):** in A1 and B1 the wrapper must report exactly one mutation, applied after
  `evaluate()` returned and before the executor was called. The executor and `FakeVehicle` log the call
  order. Otherwise INCONCLUSIVE.
- **C3 (the comparator can say both things):** before any case, the divergence comparator gets two synthetic
  pairs: identical parameters (must say "no divergence") and parameters differing in one nested value (must
  say "divergence"). If it fails either, INCONCLUSIVE.
- **C4 (the verifier can fail):** P9/B2. If `verify_package.py` accepts a tampered record, its PASS on B1
  means nothing, and P8 is INCONCLUSIVE.

## Verdict rules (per question, decided only from the run's output)

**Q1: Can an ALLOW cover an execution with changed parameters? (A1, B1)**
- **PASS** (SV resists): C1–C3 hold, and in A1 and B1 no effect runs with parameters that differ from the
  decision record. Either execution is refused, or it runs with the authorized parameters.
- **FAIL** (attack succeeds): C1–C3 hold, and at least one of A1/B1 shows divergence.
- **INCONCLUSIVE**: a hash mismatch on any target file, any control failing, a crash before the executor is
  reached, or results differing between the two repeat runs (see Run rules).

**Q2: Can a previous ALLOW be replayed for a modified action? (A2, A3)**
- **PASS**: both refused before execution, 0 new effects.
- **FAIL**: either produces a new effect.
- **INCONCLUSIVE**: as Q1.

**Q3: Does the offline verifier catch an execution that differs from its authorization? (B1 package)**
- **PASS**: C4 holds and `verify_package.py` rejects B1's package.
- **FAIL**: C4 holds and it accepts B1's package.
- **INCONCLUSIVE**: C4 fails, or no package was written.

The outcome for each question is reported separately. A FAIL is a security finding, recorded in STATUS.md
and kept; it is not fixed by this experiment.

## Evidence that will be produced

- `results/sv_attack_001/run.json`, holding:
  - the target file hashes (recomputed);
  - the probe's own sha256 and its commit;
  - Python and platform;
  - per case: decision, reasons, authorized/executed parameter hashes, effect count, record digest, call
    order;
  - the controls' outcomes.
- `results/sv_attack_001/run.log`: the probe's stdout, verbatim.
- `results/sv_attack_001/packages/`: B0, B1 and B2 packages, unedited, plus `verify_package.py` stdout and
  exit code for each.
- `results/sv_attack_001/SHA256SUMS` over everything above. The results file quotes it.
- Results go in `docs/SV_ATTACK_001_RESULTS.md`, failures first, numbers pasted from `run.log`.

## Run rules

1. The probe is committed before it is run, and its sha256 is recorded in the results.
2. One registered run, performed **only after Chad authorizes it**, plus one immediate repeat to check
   determinism. Both outputs are kept. A difference between them makes the affected question INCONCLUSIVE.
3. No file under `sovereign_veritas/` or `tools/verify_package.py` / `tools/vehicle_action.py` may change
   between this registration and the run. The hash table above is checked at run time.
4. No fix is attempted in the same branch. Any fix is a new, separately registered change, needing the
   owner's approval.
5. Nothing in this file is edited after the run. Corrections go in a dated note.

## What this test cannot establish

- **Only in-process mutation of a shared parameters object.** A PASS would not show that no other
  substitution path exists, for example a malicious executor, an executor reading parameters from a file
  that changes, a compromised process, or a TOCTOU in the target system itself.
- **The race is simulated.** The deterministic hook shows the window exists and what happens inside it. It
  does not measure how often a real concurrent writer would hit it.
- **No real vehicle, SITL or device.** `FakeVehicle` is a stand-in. Nothing here is run on the S25 unless a
  separate run is authorized and recorded.
- **Whole-package forgery is out of scope.** Packages are unsigned, and a consistent rewrite verifies (a
  known limit, `package.py`).
- **O1 is not a verdict.** That the Gate does not authorize parameters is a design property this test
  records, not a defect it judges. Whether parameters should be bound is the owner's decision.
- **Not blind and not independent.** Claude wrote the code reading, the cases, the predictions and will
  write the probe. ChatGPT suggested the idea. No human outside the project has reviewed or reproduced
  anything here.
- **NOT VALIDATED. NOT PRODUCTION-READY.**
