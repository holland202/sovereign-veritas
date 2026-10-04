# How a sovereign-veritas package maps to an action: notes for a relying-party replay section

Input for review, written at the request of Joe Krausz (`draft-krausz-verification-state-03`), not a proposal
for any particular rule. It describes one prototype, `holland202/sovereign-veritas` at `main` `16850f6`, and every
behaviour claimed below is backed by a vector run against that code (RP-1, [`RP1_RESULTS.md`](RP1_RESULTS.md)) or
by an earlier measurement cited by file. Linux container only; **not run on the phone I build on.** All RP-1
packages are unsigned, because my consumer still accepts unsigned packages (IM M5, an open gap).

Chad Holland. Drafted with Claude (Opus 5.5), which also wrote and ran the vectors; I reviewed it and take
responsibility for it. Self-tested: one author (with an AI) built the code, the vectors and this note.

## What is weak, first

1. **At-most-once is per package, not per action.** A package does not carry an action identifier. Two packages
   for the same action (same artifact, same gate inputs, same ALLOW) have different digests, and my consumer
   accepted both in turn with the same state (RP-1 P3).
2. **My consumer's retained state is not safe for concurrent consumers.** It reads its state file, checks, and
   rewrites the file with no lock, and the rewrite is not atomic. Forcing the interleaving, both checks accept
   (P6). With 8 real processes on one package, 4 of 100 trials accepted it twice (P7), and a reader that caught the
   file mid-rewrite stopped with exit 2. A torn state file stops the consumer for every package until a person
   repairs it (P8). It fails closed, but it does not stay live.
3. **"Latest" is author-wide.** The witness log is one sequence for all of an author's packages, so any newer
   package makes every older one STALE, whether or not anyone acted on it (P4).

The executor side is in better shape (point 4 below), but nothing ties it to the package yet.

## 1. Three operations, kept apart

Your split, mapped onto this code:

| Operation | Where it lives here | Retained state | Repeating it | Vector |
|---|---|---|---|---|
| Verify a package again | `tools/verify_package.py` | none | not an error: same output, exit 0, every time | P1 |
| Authorize an action again | `tools/consumer.py` (relying party); `EvidenceWorkflow` with a reserved idempotency key (executor) | consumed package digests + witness anchor; reservation per key | refused (same package); refused (same key) | P2, P3; RK-2, MP-1 |
| "Latest in the witness log" | `check_witness_entries` in the verifier, called by the consumer | the consumer's anchor (entries seen, hash of those lines) | an answer about order in one log, not about time | P4, P5 |

My consumer runs the first two in one call: `accept` verifies and then claims. So presenting a package to the
consumer again, only to check it, is refused as a replay. Re-verification has to go through `verify_package.py`,
which keeps no state.

## 2. How a package maps to an action

A package (`sv.package/0`) records **one Gate decision about one proposed action on one artifact**: the artifact
bytes and digest, the measurement, the provenance chain ending in the decision record, the verifier's validation,
every Gate input (capability, policy, runtime state) and the decision. Its identity is `package_sha256` over all
of that, including timing fields. The verifier recomputes the decision from the recorded inputs (`gate_replay`).

What it does not carry: an identifier for the action instance or the intent behind it. So the mapping is
**many packages to one action**. Gating the same intent again produces a new package with a new digest (P3: A and
B share artifact, gate inputs and decision, and differ in digest).

At-most-once therefore exists in two places that are not yet linked:

- **Relying party** (`consumer.py`): refuses a package digest it has already accepted. That stops a replayed
  receipt (P2), not a second authorization of the same action (P3).
- **Executor** (`EvidenceWorkflow`, `sovereign_veritas/idempotency.py`): reserves a caller-chosen key before the
  external effect and never runs it again without a person releasing it. The key is written into the execution
  record's metadata, not into the package.

If I were writing the relying-party rule for my own code, I would key at-most-once on an **intent identifier fixed
before the first attempt and bound into the signed record**, not on the receipt digest. RK-2 shows why the
"before the first attempt" part matters: with a fresh key per attempt, a retry after a lost reply ran the effect
twice (RK-2 case A3, `effects=2`).

## 3. The witness: trust and scope

**What it is.** An append-only text file in my repository, one line per package: `<seq> <package_sha256>`. The
copy on GitHub is the witness, and a challenger checks against their own pulled copy. `witness.py` appends only
packages that verify and refuses a digest already logged.

**What a relying party has to trust.** The author (me) decides what is logged and when. The log has no clock, so
it says nothing about wall-clock time, and it covers nothing the author never logged. Rewriting history needs a
force-push. `main` is currently protected against force-push and deletion, but the owner can change that setting,
so a relying party should not take the protection on trust. What detects a rewrite is the relying party's own
anchor (below), not the log.

**Scope.** One sequence for all of the author's packages. "LATEST_WITNESSED" means "the newest package this author
published", not "the newest for this action" or "for this claim". Consequences, both measured:

- An older package is STALE to every consumer once a newer one is logged, including one that never acted on it
  (P4). With one log per author, at most one package is actionable at a time. That is a liveness cost, and it would
  be wrong for an author issuing decisions for several independent actions.
- A consumer that has seen the log refuses a log missing its newest lines (rollback). A consumer seeing the log for
  the first time cannot tell, and accepts the same rolled-back log (P5). First use is unprotected.

A per-action or per-claim scope would remove the first consequence. It is not built.

## 4. Retained-state assumptions

What the replay protection above needs, and whether this code meets it:

| Assumption | Met here? | Evidence |
|---|---|---|
| The consumed set and anchor survive restarts | yes: a JSON file | P2, P5 |
| One writer at a time, or an atomic check-and-claim | **no** for the consumer | P6 (both accept), P7 (4 of 100 doubled), P7c (20 of 20 when the window is widened) |
| State writes are atomic (no torn file) | **no** for the consumer: `open(path, "w")` truncates first | P8; the P7 diagnostic saw a reader hit an empty file |
| A crash before the state write means no authorization | yes, for a caller that acts only on exit 0: the state is written before the consumer exits 0 | read from the code, not run |
| A crash after authorization but before the action | the package is consumed, the action never runs, and a retry is refused: at most once, possibly zero | read from the code, not run |
| The executor's claim is atomic across processes | **yes** for the reservation store (`O_CREAT|O_EXCL`, one file per key) | MP-1: 0 of 200 / 100 / 30 trials doubled at N = 2 / 8 / 32; a deliberately non-atomic store doubled 100 of 100 |
| A crashed holder does not make the key runnable again | yes: an expired lease becomes UNKNOWN and is refused until a person releases it | RK-2 R7; MP-1 P3/P4 (killed before the effect: 0 effects; after: 1 effect; 8 retries refused either way) |
| A lost reply after the effect is not repeated | yes, if the key was fixed at intent | RK-2 R1/R2 (1 effect, retry refused); A3 shows the failure with a fresh key |

The executor numbers are on one local Linux filesystem. Not tested: Android storage, network filesystems, separate
machines, and a late `complete()` racing a lease expiry (listed as unrun in MP-1).

The fix for the consumer is to reuse what the executor already does: claim each package digest with an exclusive
create, instead of rewriting one shared file. That is my next change. It is not done.

## 5. Vector pairs

Each pair differs in one thing. Inputs and a `vector.json` for each are in
[`results/rp1/vectors/`](../results/rp1/vectors/). Commands run from the repository root, and consumer state files
start absent. A and B are two packages for the same action; `log_A` holds A only, `log_AB` holds A then B.

| Pair | Accepting | Refusing | What the pair isolates |
|---|---|---|---|
| P1 | verify A (twice: identical, exit 0) | verify A with its decision changed (exit 1) | verifying again is not an error; tampering is |
| P2 | A, fresh state (exit 0) | A again, same state (exit 1, `replay`; state unchanged) | single use of a receipt |
| P3 | B after A, same state, `log_AB` (exit 0) | A again, same state, `log_AB` (exit 1) | at-most-once keyed on the receipt, not the action (gap) |
| P4 | A with `log_A`, fresh state (exit 0) | A with `log_AB`, a different fresh state (exit 1, `STALE`) | "latest" is relative order in the author's log |
| P5 | A with `log_A` (cut), fresh state (exit 0) | A with `log_A` (cut), state anchored on `log_AB` (exit 1, `rollback`) | rollback is visible only to retained state |
| P8 | B with the intact state (exit 0) | B with the state file torn in half (exit 2, `COULD NOT LOOK`) | a crash mid-write fails closed and stops progress |

P6 and P7 are not file pairs. P6 is an in-process interleaving of the real `consumer_check`. P7 is a race measured
over 100 trials (`tools/rp1_vectors.py`).

## 6. For a relying-party section, offered as input only

From this one prototype, the points I would want a replay section to make explicit:

1. Re-verification, re-authorization and witness order are three operations with different state, as you put it.
2. The at-most-once key is an action or intent identifier fixed before the first attempt and bound into the signed
   record. A receipt digest is not enough, because one action can produce many receipts.
3. Claiming that key must be atomic and durable before the action, against concurrent relying parties and against a
   crash between the claim and the action. Say which way the crash fails: here, "possibly zero", never "twice".
4. "Latest in a witness log" needs a stated scope (per issuer, per action, per claim), and relying parties without
   retained state cannot detect rollback.

## What this does not show

- Anything about another implementation, or about the draft beyond what is quoted in
  [`IETF_MAP_RESULTS.md`](IETF_MAP_RESULTS.md).
- Signed packages. Behaviour on the S25 phone, Android storage, or across machines.
- That the vectors are complete. They cover the cases above and nothing else.

## Next unrun test

Make the consumer claim each digest atomically, add an action key fixed at intent to the package, and rerun P3 and
P6–P8 with the predictions flipped.
