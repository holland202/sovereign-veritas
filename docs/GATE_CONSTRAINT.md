# Gate constraint — is the larger system boringly constrained?

Status: **Architecture Self-Tested** (same author wrote instrument and fixes; container only
until the device run below is recorded). NOT device-verified.

## The invariant

The set of inputs the Gate ALLOWs must equal the set a fail-closed spec allows.
Integration may shrink that set, never widen it. The trivial way to look constrained is a
gate that refuses everything, so the check is two-sided: a liveness case must ALLOW, and a
dead-gate mutant must be caught.

Instrument: `tools/gate_constraint.py` (stdlib only). Exit 0 looked/clean, 1 looked/found,
2 could not look (wrong API, or an installed copy shadows the target).

- **DOC** — decision classes and REFUSE ordering from the documented contract; DEFER reasons
  accumulate; REFUTED keeps a distinct reason.
- **RULE** — missing input means deny: a missing, unrecognized, mistyped or explicitly
  negative input must never reach ALLOW.
- **KNOWN** — RULE cases that leak by declared design (opt-in constraints), each with its
  reason in `KNOWN_OPT_IN`. A KNOWN case that stops leaking fails too, so the list cannot rot.
- **Lattice** — 4608 composed cases (11 axes); checks class, first REFUSE reason, complete
  DEFER reasons, monotonicity (adding a fault never loosens the decision), determinism.
- **Mutants** — `--mutants` runs the instrument's own killer: a copy-only null mutant must
  survive with an identical digest; every other mutant must be killed.

## Registered before the first run (2026-09-25T16:20:05Z, md5 11517262d411205364de8df22867ff45)

```
# gate_constraint v2 — registered before running against sovereign-veritas 8267c2b
Target: origin/feature/bounded-multi-step-planner @ 8267c2b (container clone).
Basis: read decision.py/runtime.py/workflow.py first; these confirm a reading.

PRE-FIX (tip as pushed)
Q1 baseline ALLOW; every single-fault DOC case matches (0 mismatches).
Q2 4608-point lattice: spec>0 and monotonicity>0, 0 nondeterministic; EVERY spec
   violation is (expected REFUSE, got DEFER) - INSUFFICIENT and unhealthy-runtime
   early returns masking a later REFUSE.
Q3 exactly 20 unexpected RULE failures: authorized 'false','0'; parent authorized
   'false'; thermal ['normal'] crashes; compute 'EXHAUSTED','depleted',None; power
   'UNSAFE','critical',None; evidence 'FAILED',{'ok':False},'false'; quality nan,inf,2.0;
   step_count -5,True; allow_only str; workflow registry configured + verifier_id omitted.
   thermal 'NORMAL' and None do NOT fail (DEFER).
Q4 all 7 KNOWN opt-ins leak; none stale.

POST-FIX (F1 monotone DEFER accumulation, F2 authorized is True, F3 runtime allowlists,
F4 required evidence is True, F5 quality finite in [0,1], F6 typed policy + step_count,
F7 configured registry cannot be bypassed by omitting verifier_id)
R1 baseline ALLOW; 0 DOC mismatches; lattice 0/0/0; 0 unexpected RULE; 7 KNOWN, 0 stale.
R2 all 139 pre-existing tests still pass unmodified.
R3 every mutant M01-M19 killed; null mutant M00 survives with identical digest.
```

## Pre-fix measurement — 8267c2b as pushed (container x86_64, Python 3.12.3)

```
gate_constraint v2 | python 3.12.3 x86_64
target /home/claude/svrepo/sovereign_veritas
  md5 5075544da4a47fa8883940eca5d7a0d3  decision.py
  md5 981b50457417989124717a2e00ddcb01  runtime.py
  md5 eb3b178d24bceacf81a46e9707f457b9  verification.py
  md5 3d43508c67a2efab95039716ca15e997  workflow.py
LIVENESS  baseline -> ALLOW  ok
DOC       42/42 documented cases match
RULE      20 unexpected of 29 fail-closed cases:
  ALLOW     single:authorized='false'
  ALLOW     single:authorized='0'
  ALLOW     single:parent authorized='false'
  RAISE:TypeError single:thermal=['normal']
  ALLOW     single:compute='EXHAUSTED'
  ALLOW     single:compute='depleted'
  ALLOW     single:compute=None
  ALLOW     single:power='UNSAFE'
  ALLOW     single:power='critical'
  ALLOW     single:power=None
  ALLOW     single:evidence='FAILED'
  ALLOW     single:evidence={'ok': False}
  ALLOW     single:evidence='false'
  ALLOW     single:quality=nan
  ALLOW     single:quality=inf
  ALLOW     single:quality=2.0
  ALLOW     single:step_count=-5
  ALLOW     single:step_count=True
  ALLOW     single:allow_only is a str
  EXECUTED  wf:wf_id_omitted
KNOWN     7/7 declared opt-ins still leak (listed in KNOWN_OPT_IN)
LATTICE   4608 points: 812 spec, 740 monotonicity, 0 nondeterministic
     24  want DEFER got DEFER
    788  want REFUSE got DEFER
DIGEST    9e313edf360106b721762a94f7ca67a9155c9c4e04e7681e9450ee4e184ea8d1
VERDICT   FOUND 22 failing checks
```

Outcome against registration: Q1 confirmed. Q3 confirmed (exactly the 20 listed). Q4
confirmed. **Q2 partially REFUTED (kept):** spec>0, monotonicity>0 and 0 nondeterministic
held, but "every spec violation is REFUSE->DEFER" is false — 788 of 812 are REFUSE masked as
DEFER; the other 24 are DEFERs that dropped reasons, which the registration did not
anticipate. Same cause (early DEFER returns), second symptom.

## Fixes (this commit)

| | Defect measured above | Fix |
|---|---|---|
| F1 | INSUFFICIENT_EVIDENCE and unhealthy runtime returned DEFER early, masking later REFUSEs and dropping reasons | both accumulate into one DEFER |
| F2 | `authorized="false"` / `"0"` authorized (capability and parent) | `authorized is True` |
| F3 | compute/power used denylists: `None`, `"EXHAUSTED"`, `"UNSAFE"`, `"critical"` allowed; a list crashed | recognized vocabulary only; anything else is unavailable -> REFUSE |
| F4 | required evidence `"FAILED"`, `{"ok": False}`, `"false"` counted as present | attestation must be `True` |
| F5 | evidence quality NaN, inf, 2.0 passed the threshold | must be finite in [0, 1], else DEFER |
| F6 | `allow_only` as a str did substring matching; step_count -5 / True accepted | collection required (else REFUSE); step_count int >= 1 |
| F7 | a configured verifier registry was skipped when `verifier_id` was omitted | omitted id with a registry -> INSUFFICIENT_EVIDENCE |

Values the repo already uses keep their meaning: thermal warning/high/hot/critical defer,
compute constrained/low stay healthy.

## Post-fix measurement (container x86_64, Python 3.12.3)

```
gate_constraint v2 | python 3.12.3 x86_64
target /home/claude/svrepo/sovereign_veritas
  md5 0c753732af5c209260e7a1d6627789d8  decision.py
  md5 8caf76d162b5aa4a5612232255938a85  runtime.py
  md5 eb3b178d24bceacf81a46e9707f457b9  verification.py
  md5 8cc16fb926e426ec185ec992b250f0d6  workflow.py
LIVENESS  baseline -> ALLOW  ok
DOC       42/42 documented cases match
RULE      0 unexpected of 29 fail-closed cases:
KNOWN     7/7 declared opt-ins still leak (listed in KNOWN_OPT_IN)
LATTICE   4608 points: 0 spec, 0 monotonicity, 0 nondeterministic
DIGEST    ab816905b1faf69aeaf24119b207cf7b80fcebd2ffcddac80d3edfa5e4da2d65
VERDICT   CLEAN
MUTANTS   differential: KILLED = new failing checks vs the unmutated target
  M00 SURVIVED digest identical  null mutant (copy only) - must SURVIVE
  M01 KILLED   +60  control: always ALLOW
  M02 KILLED   +25  control: always REFUSE (dead gate)
  M03 KILLED   +3   drop input-digest check
  M04 KILLED   +1   REFUTED no longer refuses
  M05 KILLED   +2   authorization by truthiness
  M06 KILLED   +2   drop action/capability binding
  M07 KILLED   +5   drop runtime availability check
  M08 KILLED   +2   INSUFFICIENT short-circuits (masks REFUSE)
  M09 KILLED   +2   unhealthy runtime short-circuits
  M10 KILLED   +4   INSUFFICIENT_EVIDENCE allows
  M11 KILLED   +2   drop policy check
  M12 KILLED   +14  runtime vocabulary accepts any string
  M13 KILLED   +3   required evidence by truthiness
  M14 KILLED   +3   drop quality validity check
  M15 KILLED   +1   drop policy type check
  M16 KILLED   +1   omitted verifier_id bypasses registry
  M17 KILLED   +2   max_steps overrun only defers
  M18 KILLED   +1   parent authorization by truthiness
  M19 KILLED   +1   REFUTED loses its distinct reason
MUTANT VERDICT  instrument can fail both ways (exit 0; gate findings above are reported, not gated, here)
```

Outcome against registration: R1 confirmed. R2 confirmed — all 139 pre-existing tests pass
unmodified; with the 2 new tests the suite is 141 passed (container). R3 confirmed — 19/19
mutants killed, null mutant survives with an identical digest.

Measured after, not registered: the 139 pre-existing tests kill 9 of these 19 mutants. They
stay green with the digest check removed (M03), with the early-DEFER masking restored (M08,
M09), or with the policy check removed (M11) — which is how the masking shipped.

## Still open

- KNOWN opt-ins stay listed, not fixed. `wf_identity_unbound` is the one worth deciding:
  `VerifierRegistry.register(id, verifier)` already stores the object, but the workflow never
  checks `self.verifier is registry.get(verifier_id)`; `test_validated_registry_allows_actual_verifier`
  registers `object()` and relies on that.
- Device run on the S25 (aarch64, Python 3.14) — record its DIGEST here. A matching digest
  means identical gate decisions across substrates for this lattice.
