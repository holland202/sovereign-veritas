# STD-3 results: on OASB main, the plugged-in adapter now reaches the scenario tests

Registration: [`STD3_PREREG.md`](STD3_PREREG.md), commit `b4f5a34`, pushed before OASB was installed here.
Harness `019aae1`, pushed before any run. Target: `opena2a-org/oasb` at `7bf7deb` (main, 2026-11-25). Linux x86_64
container, Node v22.23.5, `npm ci`. Not run on the S25.

Drafted by Claude (Opus 5.5), which also wrote the harness and ran it, at Chad Holland's direction. Chad has not
reviewed it line by line. Self-tested. Nothing has been filed upstream from this document yet.

## What went wrong, first

- **P5 is REFUTED.** I predicted the echo adapter (no detection, records exactly what it is given) would pass all
  3 BL-001 tests. It passed 1 of 3. The two failures are on event counts, not on detection — see below.
- **P3 held, but test 1 fails under flag before it reaches its false-positive check.** Under flag-everything,
  BL-001 test 1 fails at the event count (`expected 50 to be 52`, line 73), the same line echo fails at. Only test 3
  (`without escalation`) fails because the adapter flagged things.
- **M1 is 0 under all three adapters**, against my expectation in the registration that the atomic monitor tests
  would crash on the missing `observe*` methods. Not investigated which path those tests took.
- **E2E-002 timed out again** (`should detect a suspicious binary (curl)`), under ARP and every adapter. Still not
  diagnosed; it is why one test does not move.

## Outcome

Raw output, verbatim (`python tools/std3_run.py ../oasb`, also in `results/std3/run.txt`):

```
OASB     7bf7deb
ARP      total 445 passed 441 failed 1 skipped 3  load errors 0 []
SILENT   total 445 passed 249 failed 186 skipped 10  load errors 0 []  M1 not-a-function 0
ECHO     total 445 passed 266 failed 169 skipped 10  load errors 0 []  M1 not-a-function 0
FLAG     total 445 passed 240 failed 195 skipped 10  load errors 0 []  M1 not-a-function 0
HELD     P1  ARP failures outside e2e: 0; e2e failures: 1
HELD     P2  scenario tests not moving: 8 of 220 (3.6%)
HELD     P3  BL-001 under flag   ['failed', 'failed', 'failed']
HELD     P4  BL-001 under silent ['failed', 'failed', 'failed']
REFUTED  P5  BL-001 under echo   ['failed', 'passed', 'failed']
         (for comparison) BL-001 under ARP ['passed', 'passed', 'passed']
HELD     P6  tests carrying a [requires: <undeclared>] tag under the adapters: 8; in gated files, skipped under all three: 8 of 12; of those also skipped under ARP: 0
```

(The per-test lines under P1, P2 and P6 are in `results/std3/run.txt`.)

| ID | Result |
|---|---|
| P1 | **HELD.** The one ARP failure is E2E-002 |
| P2 | **HELD.** 212 of 220 scenario tests move with the adapter (STD-2 at `fddf2b1`: 153 tests could not move at all) |
| P3 | **HELD**, with the caveat above |
| P4 | **HELD** |
| P5 | **REFUTED** |
| P6 | **HELD.** The 8 tests gated on the 3 capabilities added since `fddf2b1` report N/A under these adapters, as they should |

Anti-vacuity: `--sabotage` refutes P2 (220 of 220 not moving) and P3 (BL-001 passes under flag); harness exit 0
(`results/std3/sabotage.txt`).

## The 8 tests that do not move

Each one was read. Seven are checks these three adapters cannot fail; none of them is a reach defect.

| Test | Why it does not move |
|---|---|
| AT-ENF-001 `should include a reason string in the result` | All three adapters return a reason string |
| AT-INT-001 `should not trigger kill for threat events below critical severity` | None of the three adapters ever kills. A kill-everything adapter would fail it |
| E2E-001 `should allow normal file creation without triggering violations` | None of the three raises a violation from live file activity |
| E2E-002 `should detect a suspicious binary (curl) as a violation` | Times out under every adapter, ARP included, in this container |
| E2E-004/005/006 `should restore ... after stop` | Check that no events arrive after `stop()`; none of the three records anything after stop |
| INT-007 `should create a budget controller with tiny budget` | Setup check |

## The new finding: BL-001 tests 1 and 2 expect ARP's correlation events

BL-001 injects 50 normal events and then asserts `allEvents.length === 52` and `threats.length === 2` (test 1),
and 6 network events where 5 were injected (test 2). By the test's own comment, the extra events are the
low-severity threats ARP's cross-monitor correlation raises. The block is gated only on `process-monitoring`,
`network-monitoring` and `filesystem-monitoring`, not on `event-correlation`.

Exploratory control, not registered: the echo adapter with `event-correlation` removed from its declared
capabilities (`tools/std3_echo_nocorr.cjs`) still runs BL-001 and fails tests 1 and 2 on the same counts
(`results/std3/echo_nocorr_bl001.txt`):

```
   × ... should produce zero violations or threats from normal agent activity 8ms
     → expected 50 to be 52 // Object.is equality
   × ... should correctly attribute events to all 3 monitor sources 3ms
     → expected [ { id: 'std2-56', …(7) }, …(4) ] to have a length of 6 but got 5
   ✓ ... should handle mixed info and low severity without escalation 1ms
```

So a product that monitors all three sources, raises no false positives and does not claim correlation fails the
"Zero False Positives" baseline twice, on counts. And an adapter that flags everything fails test 1 on the same
count line, before the violations and severity assertions run. Test 3 is the one BL-001 test that separates
"flags nothing" from "flags everything" on false positives alone.

This is about what BL-001 asserts, not about ARP. Whether to gate those assertions on `event-correlation`, or
assert on the injected events only, is the maintainer's call.

## Files

`tools/std3_run.py`, `tools/std3_echo_nocorr.cjs`, `results/std3/{arp,silent,echo,flag}.json` (vitest reports),
`results/std3/*.adapter.json` (written by OASB), `results/std3/run.txt`, `results/std3/sabotage.txt`,
`results/std3/not_moving.tsv`, `results/std3/echo_nocorr_bl001.txt`.

## Next unrun test

Why M1 is 0: which path the atomic process, network and filesystem tests take when the adapter declares those
capabilities but has no `observe*` methods. Read the 15 atomic monitor tests' results under silent before
claiming anything about them.
