# STD-2 — OASB: does the benchmark measure the product plugged into it? Registration

Status: **REGISTERED, nothing run.** This file is committed alone, before any adapter or harness exists and before
OASB has been installed or run here.

Drafted by Claude (Opus 5.5) at Chad Holland's direction. Chad has not reviewed it line by line.

## Question

The Open Agent Security Benchmark (OASB, `opena2a-org/oasb`, Apache-2.0) says: "Plug in your product, run the
suite, get a detection coverage scorecard". A product is plugged in by implementing `SecurityProductAdapter` and
setting `OASB_ADAPTER`. OASB asks for "an independent second implementation".

A benchmark can only score a product if its tests (a) actually call the product that was plugged in and
(b) can fail when that product detects nothing, or flags everything. This experiment checks both with three
adapters whose behaviour is known in advance. None of them is a security product.

## What was read before this registration (exploratory)

At `fddf2b1`: `README.md` (first 200 lines), `STATUS.md`, `package.json`, `src/harness/adapter.ts` (full
interface), `src/harness/create-adapter.ts`, `src/harness/capabilities-core.ts`, `src/harness/capabilities.ts`
(grep), `src/atomic/process/AT-PROC-001.spawn-child.test.ts` (first 90 lines). File counts by grep:

- 49 test files. **11** call `createAdapter()` (the one that honours `OASB_ADAPTER`). **37** construct
  `new ArpWrapper(...)` directly. 1 integration file does both. **2** (`src/benchmark/`) do neither: they are
  the scoring-engine unit tests.
- By directory, direct-ARP / createAdapter / total files: atomic 22 / 8 / 30; integration 8 / 1 / 8;
  baseline 1 / 2 / 3; e2e 6 / 0 / 6.
- `requireCapability()` in `capabilities-core.ts` has an empty body: it skips nothing. 5 test files use capability
  gating.
- `AT-PROC-001` says it injects the event it then waits for, "simulating what the monitor would emit on detection".

Nothing was installed or run.

## The three adapters (written after this registration, in `tools/std2_adapters/`)

All three declare every capability, so nothing is skipped as N/A.

- **silent**: detects nothing. `injectEvent` returns the event but records nothing; `waitForEvent` times out;
  every scanner returns `{detected: false, matches: []}`; no enforcements.
- **echo**: records exactly the events it is given, unchanged, and nothing else; `waitForEvent` searches those;
  scanners return `detected: false`. It has no detection logic at all.
- **flag-everything**: every scanner returns `detected: true`; every injected event is recorded as category
  `threat`, severity `critical`.

## Predictions

| ID | Prediction |
|---|---|
| P1 | Reproduction. `npm test` at `fddf2b1` with the default adapter (ARP) reports 245 tests: 244 passed, 1 skipped. |
| P2 | Plug-in reach. For every test in the 36 files that construct `ArpWrapper` and never call `createAdapter`, the pass/fail result under each of the three adapters is identical to the ARP run. Those tests measure ARP whatever product is named. (The harness prints the number of tests involved.) |
| P3 | Can fail on silence. Under **silent**, each of the 11 `createAdapter` files has at least one failing test. |
| P4 | Echo. Under **echo**, at least one `createAdapter` test passes. Such a test passes for a product with no detection logic. |
| P5 | Can fail on noise. Under **flag-everything**, at least one test in `src/baseline/` fails (the false-positive checks). |

P2 is about what the suite measures when a vendor plugs in a product. It is not a claim that ARP is weak, or that
any test is wrong about ARP.

## Controls and limits, stated now

- The adapters are deliberately not products. A result says what the tests can distinguish, not how good any
  product is.
- An adapter can fail to load or crash a test. The harness reports load errors separately from test failures.
  If **silent** cannot load, P2–P5 are COULD NOT RUN.
- E2E tests need OS-level monitoring. They may behave differently in a container than on a developer machine.
  Results are reported per directory.
- Container only (Linux x86_64). Not run on the S25.
- Self-tested.

## Next unrun test

Write a fourth adapter that detects by a simple keyword list, not a real product. See how far it gets on the
`createAdapter` tests. That bounds how much of the score a trivial detector earns.
