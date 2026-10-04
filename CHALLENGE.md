# Break the Gate

Anyone may try. A success is credited by name in STATUS.md. A careful reproduction is credited as well.

## What counts as a break

Get `tools/verify_package.py` to print `VERDICT  CONSISTENT` **with** `--signature` / `--allowed-signers` /
`--identity` and `--witness-log` (defender D2 in `docs/ATTACK_HARNESS.md`) for a package that:

- was not signed by the key in the allowed_signers file, or
- says ALLOW where the Gate's rules (`CONTRACT.md`) on its recorded inputs say DEFER or REFUSE, or
- is older than the newest package in a witness log you did not write.

A break of `tools/consumer.py` also counts: it accepting the same package twice, or accepting a log
that does not extend one it has already seen. Two ways of doing the first are already measured and do not
count (see the list below): concurrent processes, and a second package for the same action.

## Already known: these do not count (they are published limits)

- Without a signature, any fully consistent rewrite verifies (K1-K3 in `tools/nvidia_challenge.py`;
  A3-A5 in the harness).
- Replaying the latest package against the verifier alone (A7); `tools/consumer.py` is the fix.
- Rolling back the witness log against a consumer that has never seen the newer log (A10, round 3).
- Anything that needs the signing key. Key custody is out of scope.
- The companion route check trusts the companion's own labels (`docs/COMPANION_ACTION.md`).
- `tools/consumer.py` accepting one package twice when several processes race on its state file (4 of 100
  trials in `docs/RP1_RESULTS.md`, P6-P7), accepting a second, different package for the same action (P3), or
  stopping on a torn state file (P8). Published, not yet fixed. A **sequential** repeat of the same package
  against an intact state file still counts.
- A repeated `record_id`, a concurrent race, or a record write that fails after `execute()` producing
  more external effects than ledger records in `EvidenceWorkflow.run()` (XB-1,
  `docs/EXECUTION_BOUNDARY_RESULTS.md`; credited to Davorin Popović). Exception: the sequential case is
  fixed (PR #8), so getting a second external effect from a **sequential** repeat of a `record_id` through a
  sink that implements `has_record` **does** count as a break.

## One action, two effects (RK-2 / MP-1 / RK-3, a separate track, also credited)

**Claim.** Through `EvidenceWorkflow.run()` with an `idempotency_key` and a `FileReservations` store, one key
produces at most one external effect, including when separate processes race, when a holder is killed, and when
the response is lost after the effect. The retry is refused before it executes. This holds while nobody releases
the key; see "release while the holder still runs" below for what a release can do.

**What is measured** (`docs/RK2_RESULTS.md`, `docs/MP1_PREREG.md` Amendment 1; run both probes yourself):

    python tools/rk2_probe.py          # R1-R10; --sabotage must exit 1
    python tools/mp1_probe.py          # 0 of 200 / 100 / 30 trials doubled at N = 2 / 8 / 32 processes
    python tools/rk3_probe.py          # a late complete() is no longer lost (0 of 300; 123 of 300 before RK-3)

A deliberately non-atomic store doubled 100 of 100 trials in the same harness, so the harness can see a double.

**A break.** A program (any language) that gets **two or more external effects for one idempotency key** through
`EvidenceWorkflow.run()` with `FileReservations` on one local filesystem, counted at the executor, outside the
reservation store and the ledger as the two probes do. Send the program and the output.

**These do not count.** They are published limits:

- A **fresh key per attempt** (RK-2 case A3, `effects=2`). The key must be chosen when the intent is created,
  before the first attempt. A caller that breaks that rule gets what it asked for.
- **Release while the holder still runs.** A holder outlives its lease (set with `run(lease_s=...)`, default
  30 s), a person releases the key after truthfully seeing no effect yet, the retry runs, and then the late
  holder's action lands: two effects (`docs/RK3_RESULTS.md`, Q2). Seeing no effect does not show that the earlier
  attempt can no longer produce one. The store records the late holder (`late_events()`) but cannot stop it; that
  needs a fence at the action's target, which is OBS-1's subject.
- A key left `UNKNOWN` or `IN_FLIGHT` stays blocked until `release()` is called, and an empty reservation file
  (a crash between the create and the write) blocks its key for good. Liveness costs, not doubles. `release()`
  does not check who calls it.
- Keys are compared byte for byte, so the NFC and NFD forms of the same text are two keys (RK-2 limit 7).
- `MemoryReservations` across processes (it is in-process by design).
- Anything that needs write access to the reservation directory.

**Not tested, and welcome.** Each is a registered "left unrun" item, so a reproduction is credited and a null
result is a useful result too:

- Two `release()` calls racing each other, or a `release()` racing a late `complete()` that carries no token
  (both read-check-write sequences without a lock; read from the code, not tested). The earlier suspected race,
  a late `complete()` lost to `reserve()`'s expiry write, was demonstrated and fixed in RK-3.
- Android storage (Termux's own folder and FUSE shared storage), network filesystems, and separate machines.
  These are outside the claim above (one local filesystem); a double there is credited as a limit of the claim.

## Reimplement the Gate (also credited)

The Gate's contract is language-neutral: `contract/` holds the vectors, and `CONTRACT.md` holds the
rules. Any program that reads one JSON case per line on stdin and writes one decision per line can be
checked:

    python tools/gate_contract.py --check-command ./your-gate

It must print the same conformance digest (`44823d0f...0628`) as the kernel. `ports/go` already
does, but it was written inside this project, so it is not independent evidence. An implementation
written from `CONTRACT.md` alone, by someone else, is the missing check. Agreement is credited by name.
A disagreement is credited too: it means the contract or this implementation is underspecified, and
that is the more useful result.

## Corroboration corridor (V14, a separate track, also credited)

`docs/V14_CORRIDOR_PREREG.md` registers a bound, and `docs/V14_CORRIDOR_RESULTS.md` records that it held
against the reference attackers and a 1,000-attacker search. Break it.

**Claim:** in `tools/corridor_challenge.py`, configuration C2, with an independent root and adversarial
noise, no attacker drives the simulated vehicle more than **B = 31.1 m** outside its 300 m fence. In C2:

- the Gate checks the request;
- the V13 latch then re-runs the cross-check on every reading;
- a latch FAIL lands the vehicle without horizontal position hold.

**What the attacker controls:**

- the GNSS offset, moving it at most 1 m per tick;
- the independent position's error, anywhere within 5 m;
- it also sees everything: the true position, the readings, the setpoint and the latch counters.

**A break:** a program in any language, speaking the JSON-lines protocol in the harness docstring, for
which this prints `VERDICT  BREAK`:

    python tools/corridor_challenge.py --attacker "<your program>"

The harness, model, check, latch and Gate must be unchanged. `tools/corridor_attacker_example.py` is a
working starting point; it reaches 30.95 m. The best attack known to the author reaches 31.00 m.

**Also a break:** getting the harness to accept an attacker that violates either limit (a GNSS move of
more than 1 m in one tick, or an error of more than 5 m).

**These do not count.** They are published results:

- C1 (today's request-time-only path; 117.5 m);
- the corridor (28.5 m, inside the bound);
- a common-root independent source;
- C2g (LAND on GNSS);
- anything the harness reports as OUT OF MODEL.

Criticism of the model's realism (lag, overshoot, wind) is welcome, as a registered experiment, and is
credited. It is not a break of this claim.

## Start here

    git clone https://github.com/holland202/sovereign-veritas && cd sovereign-veritas
    python -m pip install -e ".[test]"
    python -m pytest -q
    python tools/attack_harness.py --round2 --round3        # every registered prediction prints HELD
    python tools/gate_contract.py --check kernel             # digest 44823d0f...0628

Open an issue with the package, the commands and the output. A reproduction of the numbers (on any
platform) is also worth an issue: say what you ran and what it printed.
