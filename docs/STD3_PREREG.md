# STD-3 — OASB on main: do the STD-2 adapters now move every scenario test? Registration

Status: **REGISTERED, nothing run.** This file is committed before OASB is installed or run here for STD-3.

Drafted by Claude (Opus 5.5) at Chad Holland's direction, 2026-11-25. Chad has not reviewed it line by line.

## Question

STD-2 ([`STD2_RESULTS.md`](STD2_RESULTS.md), OASB at `fddf2b1`) found that 36 scenario files constructed
`ArpWrapper` directly, so 153 tests measured ARP whatever `OASB_ADAPTER` named, and that `BL-001`
("Zero False Positives") passed 3 of 3 under an adapter that flags everything. That was filed as
`opena2a-org/oasb#40`. The maintainer replied on 2026-11-25 that both are fixed on `main` (`82ffe63`, #85;
`9ccc5b9`, #324) and asked: rerun the silent, echo and flag adapters on `main` and post the ID of any test that
still does not move with the adapter.

STD-3 is that rerun. Target: `opena2a-org/oasb` at `7bf7deb` (main on 2026-11-25).

## What was read before this registration (exploratory)

At `7bf7deb`, by grep and by reading: all 47 files under `src/{atomic,baseline,integration,e2e}` call
`createAdapter()` and `describeWithCapability`; the only test file still constructing `ArpWrapper` is
`src/harness/arp-observations.test.ts`. `requireCapability()` in `src/harness/capabilities-core.ts` now marks its
enclosing `describe` block skipped, or throws when there is none. `src/harness/adapter.ts`: the interface has
grown since `fddf2b1` — new capabilities `connection-burst-detection`, `http-response-scanning`,
`baseline-persistence`, and new optional methods `observeConnections`, `observeProcesses`, `observeFileChange`,
`createConnectionBurstDetector`, `createHttpProxy`. `src/baseline/BL-001.normal-agent-profile.test.ts`: its
three tests inject events and assert on counts, categories and severities of what the adapter returns.

Nothing was installed or run.

## Instrument

The STD-2 adapters **unchanged**: `tools/std2_adapters/{silent,echo,flag}.cjs` and `make.cjs` exactly as at
`7949d4d`. This is the rerun the maintainer asked for, so the adapters are frozen. Consequences, stated now:

- They declare the 16 capabilities that existed at `fddf2b1`, not the three added since, so tests gated on
  those three should report N/A under all three adapters.
- They do not implement the `observe*` methods. The atomic process, network and filesystem tests that call
  them can fail with a missing-method error, not a wrong verdict. Such a failure still "moves" relative to ARP,
  but it is a crash. The harness counts failures whose message contains `is not a function` (M1) and reports
  them apart.

Harness: `tools/std3_run.py`, written after this registration.

## Definitions

- **Scenario tests**: tests in files under `src/atomic/`, `src/baseline/`, `src/integration/`, `src/e2e/`.
- **Moves**: a test moves if its status under at least one of silent, echo, flag differs from its status under
  ARP. A test **does not move** if its status is identical to ARP's under all three. Tests skipped under ARP are
  excluded from the denominator.

## Predictions

| ID | Prediction |
|---|---|
| P1 | Reproduction. Under ARP, no test outside `src/e2e/` fails. (STD-2 saw E2E-002 time out in a container; E2E results are recorded, not predicted.) |
| P2 | Reach. Of scenario tests not skipped under ARP, at most 5% do not move. |
| P3 | Fails on noise. Under **flag**, at least 1 of BL-001's 3 tests fails. (Under STD-2 it passed 3 of 3.) |
| P4 | Fails on silence. Under **silent**, at least 1 of BL-001's 3 tests fails. |
| P5 | Transport, not detection (the open point of `oasb#88`). Under **echo** — an adapter with no detection logic that records exactly what it is given — all 3 of BL-001's tests pass. |
| P6 | Gating. Every scenario test in a block gated on a capability the STD-2 adapters do not declare is skipped under all three adapters and not skipped under ARP. |

M1 (measured, not predicted): the number of failures under each adapter whose message contains `is not a function`.

## Anti-vacuity control

`python tools/std3_run.py <oasb> --sabotage` replaces each adapter's results with ARP's. P2 and P3 must then be
refuted (every test fails to move; BL-001 cannot fail under flag). If the harness does not refute them, it exits 1
and the run is void.

## Limits

- Linux container only (x86_64), not the S25. Self-tested: one author wrote the adapters, harness and judgment.
- The list of tests that do not move is the deliverable for `oasb#40`. A test that does not move is not
  automatically a defect: a test can be correctly insensitive to these three adapters. Each one will be read
  before anything is posted.
- P5 holding would show BL-001 can be passed without detection; it would not show BL-001 is wrong about ARP.
