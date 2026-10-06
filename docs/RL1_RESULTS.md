# RL-1 results: a `release()` record holds only what the caller wrote (3 of 3 as registered)

Registration: [`RL1_PREREG.md`](RL1_PREREG.md), committed alone at `2169410` and merged at `2603f3e` (PR #58) before the
probe ran. Probe: `python tools/rl1_release_probe.py`, committed exactly as run at `216fd03`; `RECORDED` pinned at
`00493d6`. Linux x86_64 container, Python 3.13.16. **NOT VALIDATED on the S25.**

Drafted by Claude (Opus 5.5), which also wrote the registration and the probe and judged the result, at Chad Holland's
direction on 2026-10-05. Review level: direction only. Chad has not read this document or the probe line by line.

## What could have gone wrong, first

- **This is self-testing.** The same model wrote the question, the predictions, the probe and this judgement. No one
  independent has run it.
- **The result was expected from reading the code.** L1 and L2 follow from `idempotency.py` lines 114-121 and 210-217,
  which were read before registering. The run confirms that reading against the real classes. It is not a discovery,
  and "3 of 3 as registered" is not "the system passed": the predictions were predictions of a gap.
- **L3 was seen before registering.** The three automatic `release(..., by="system")` calls in `tools/obs1_system.py`
  were found by a text search first, so L3 was registered as context and is not scored.
- **Interpretations of the registration, disclosed:**
  - R2's "automated loop" is a one-iteration loop that starts the releasing thread. It is a stand-in for an automated
    caller, as the registration's limits say.
  - The registration says the sabotage must exit 1 "because of L1". The probe exits 1 under `--sabotage` if and only if
    L1 is REFUTED. L2 is also REFUTED under sabotage, because no RELEASED entry exists to inspect. That follows from L1
    and does not decide the exit code.
  - L3's site list prints in string order (`:106`, `:139`, `:90`). Cosmetic. Not changed after the run.
- **No deviation in what was measured.** One comment in the probe's docstring was corrected before the first run
  ("merged" to "pushed", since the registration had been pushed but not yet merged when the file was written).

## Outcome

| ID | Prediction | Result |
|---|---|---|
| L1 | R1 and R2 accepted in both stores; `by` stored verbatim | **HELD** |
| L2 | RELEASED entry has exactly `at`, `to`, `by`, `why`; R1 and R2 entries equal without `at` | **HELD** |
| L3 | context: automatic `by="system"` releases in non-test code | 3 sites, all `tools/obs1_system.py` (not scored) |
| L4 | anti-vacuity: release of a non-UNKNOWN key is refused | **HELD** |
| sabotage | `release()` refuses `by != "operator"`: L1 REFUTED, exit 1 | **as registered** |
| no-op control | sabotage path with the unmodified method: L1 HELD, exit 0 | **as registered** |

Ten repeated registered runs gave one digest, `cfe519e4…6eff5`.

## Output, registered run (verbatim, `results/rl1/run_registered.txt`)

```
RL-1 | registered run | python 3.13.16
  MemoryReservations   R0 refused; R1 accepted; R2 accepted
  MemoryReservations   R1 entry {'to': 'RELEASED', 'by': 'human:chad', 'why': 'checked downstream'}  R2 entry {'to': 'RELEASED', 'by': 'human:chad', 'why': 'checked downstream'}
  FileReservations     R0 refused; R1 accepted; R2 accepted
  FileReservations     R1 entry {'by': 'human:chad', 'to': 'RELEASED', 'why': 'checked downstream'}  R2 entry {'by': 'human:chad', 'to': 'RELEASED', 'why': 'checked downstream'}
  L3 (context, not scored) release(..., by='system') call sites in sovereign_veritas/ and tools/: 3 ['tools/obs1_system.py:106', 'tools/obs1_system.py:139', 'tools/obs1_system.py:90']
  L1  HELD
  L2  HELD
  L4  HELD
VERDICT 3 of 3 as registered (L3 is context; sabotage and no-op control run separately)
DIGEST cfe519e4a21e684570e04dfe20113ebf5183a6f1487fcd9768642fc505b6eff5
exit 0
```

## Output, `--sabotage` (verbatim, `results/rl1/run_sabotage.txt`)

```
RL-1 | SABOTAGE: release() raises unless by == 'operator' | python 3.13.16
  MemoryReservations   R0 refused; R1 raised: sabotage: release by 'human:chad' refused; R2 raised: sabotage: release by 'human:chad' refused
  MemoryReservations   R1 entry None  R2 entry None
  FileReservations     R0 refused; R1 raised: sabotage: release by 'human:chad' refused; R2 raised: sabotage: release by 'human:chad' refused
  FileReservations     R1 entry None  R2 entry None
  L3 (context, not scored) release(..., by='system') call sites in sovereign_veritas/ and tools/: 3 ['tools/obs1_system.py:106', 'tools/obs1_system.py:139', 'tools/obs1_system.py:90']
  L1  REFUTED
  L2  REFUTED
  L4  HELD
VERDICT 1 of 3 as registered (L3 is context; sabotage and no-op control run separately)
DIGEST 315bf2a95d26931bc5fd4655040f2a09c84f120f6085a144a232d1b46abe061f
exit 1
```

`--sabotage-noop` (`results/rl1/run_sabotage_noop.txt`) printed the registered run's lines and digest, and exited 0.

## What this shows and does not show

- **Shows (implementation):** in both stores, a release record is the four fields the caller supplies or the library
  stamps (`at`, `to`, `by`, `why`). A release by a script that writes `by="human:chad"` is identical to any other with
  the same strings, apart from the time.
- **Shows (repository):** the module docstring says release is "meant for a human after investigating", and this
  repository's own OBS-1 system releases keys automatically, with `by="system"` and a reason. The documented purpose
  and the use differ. That is not a defect in OBS-1; its releases follow a stated reconciliation rule.
- **Does not show:** that anyone has misused this, or anything about who really called `release()`. No record a
  library writes from caller-supplied strings could show that.
- **Does not show:** that the library should authenticate people. That is a design decision (below).

## Candidate changes (proposals, Chad's decision: each changes a contract or a documented meaning)

1. Record `by` as unattested in the entry (for example `"by_attested": false`), so no reader takes it for a verified
   identity. Smallest change; it changes the history format.
2. Let the library set a caller kind from a verified credential (for example a signature by a key registered as a
   person's). This shows a key was used, not that a person was present. Who holds the key is outside the library.
3. Change the docstring so it no longer says "meant for a human", matching how OBS-1 uses it.

## Still open

- None of the candidate changes is made.
- The same question for any other record that names an actor (`EvidenceWorkflow` records, package signatures) is not
  asked here.
- Nothing here is run on the S25.
