# How a sovereign-veritas package maps to an action: notes for a relying-party replay section

Input for review, written at the request of Joe Krausz (`draft-krausz-verification-state-03`), not a proposal
for any particular rule. It describes one prototype, `holland202/sovereign-veritas` at `main` `16850f6`. Each claim
below is backed by a vector run against that code (RP-1, [`RP1_RESULTS.md`](RP1_RESULTS.md)), by an earlier
measurement cited by file, or is marked **read from the code, not run**. Linux container only; **not run on the
phone I build on.** All RP-1 packages are unsigned, because my consumer still accepts unsigned packages (IM M5, an
open gap).

Written by Claude (Opus 5.5) at Chad Holland's direction; Claude also wrote and ran the vectors. A second Claude
session that had not seen the drafting checked it against the code and outputs, and its corrections are applied.
Chad Holland read the whole note and is responsible for it; he did not rerun the vectors himself. Self-tested throughout: one author
(with an AI) built the code, the vectors and this note.

## What is weak, first

1. **My consumer's at-most-once is keyed on the package digest, not the action.** Two packages for the same action
   (same artifact, same gate inputs, same action description, same ALLOW) differ only in timing fields and so in
   digest. My consumer accepted both in turn with the same state (RP-1 P3). The package *can* carry a better key
   (section 2), but the consumer does not read one.
2. **My consumer's retained state is not safe for concurrent consumers or power loss.** It reads its state file,
   checks, and rewrites the file with no lock, and the rewrite (`open(path, "w")`) is neither atomic nor fsynced.
   Forcing the interleaving, both checks accept (P6). With 8 real processes on one package, the registered run had
   4 of 100 trials accept it twice; two later runs had 2 and 1 of 100 (P7). The runner still judged P7 **REFUTED**,
   because one process in the registered run ended with neither accept nor refuse, and the runner's judge counts
   that as an error. An unregistered rerun captured what such a process prints: it read the state file while
   another process had it truncated, and stopped with exit 2. A torn state file stops the consumer for every
   package until someone repairs it (P8): fail closed, but not live.
3. **"Latest" is author-wide.** The witness log is one sequence for all of an author's packages, so any newer
   package makes every older one STALE, whether or not anyone acted on it (P4).

The executor side is in better shape (section 4).

## 1. Three operations, kept apart

Your split, mapped onto this code:

| Operation | Where it lives here | Retained state | Repeating it | Vector |
|---|---|---|---|---|
| Verify a package again | `tools/verify_package.py` | none | not an error: same output, exit 0, every time | P1 |
| Authorize an action again | relying party: `tools/consumer.py`; executor: `EvidenceWorkflow` with a reserved idempotency key | consumed package digests + witness anchor; one reservation per key | refused (same package digest); refused (same key) | P2, P3; RK-2, MP-1 |
| "Latest in the witness log" | `check_witness_entries` in the verifier, also called by the consumer | the consumer's anchor (entries seen, sha256 of those lines) | an answer about order in one log, not about time | P4, P5 |

My consumer runs the first two in one call: `accept` verifies and then claims. So presenting a package to the
consumer again, only to check it, is refused as a replay. Re-verification has to go through `verify_package.py`,
which keeps no state.

## 2. How a package maps to an action

A package (`sv.package/0`) is written **after the producer's run**. It carries the artifact bytes and digest, the
measurement, the provenance chain, the verifier's validation, every Gate input (capability, policy, runtime state)
and the decision. The last record in the chain is the run's record: `record_id`, the action description
(`{"capability": "measure", "requested": "record_result", "parameters": {}}` in RP-1), the decision, and an
`execution_status` (`SUCCEEDED` in RP-1, where the producer's executor is a no-op). The verifier recomputes the
decision from the recorded inputs. The package's identity is `package_sha256` over all of it, including timing
fields.

So a relying party that "accepts" a package is acting downstream of a run that already happened, on a record of
it. What identifies the action inside that record:

- **The action description** names the kind of action, not an instance. A and B carry identical ones.
- **`record_id`** is chosen by the caller. `make_package.py` always uses `run-1`, so A and B share it, and keying on
  it would also refuse every later, different action from that tool.
- **`idempotency_key`**: when the caller reserves one, the workflow writes it into this record's metadata, so it is
  inside the package and covered by `package_sha256`. **Read from the code** (`workflow.py`, success path), not
  part of RP-1. RP-1's packages have no key, because `make_package.py` passes none.

The mapping today is therefore **many packages to one action**, and nothing in my consumer or verifier reads the
key that would tie them together. If I were writing the relying-party rule for my own code, I would key
at-most-once on that **intent key, fixed before the first attempt and inside the signed record**, not on the
package digest. RK-2 shows why "before the first attempt" matters: with a fresh key per attempt, a retry after a
lost reply ran the effect twice (RK-2 case A3, `effects=2`).

## 3. The witness: trust and scope

**What it is.** An append-only text file in my repository, one line per package: `<seq> <package_sha256>`. The
copy on GitHub is the witness, and a challenger checks against their own pulled copy. `witness.py` appends only
packages that verify, and refuses a digest already logged.

**What a relying party has to trust** (not measured; this is how it is built). The author (me) decides what is
logged and when. The log has no clock, so it says nothing about wall-clock time, and it covers nothing the author
never logged. Rewriting history needs a force-push. A GitHub ruleset on the repository currently blocks force-push
and deletion, but the owner can change it, so a relying party should not take that on trust. What detects a rewrite
is the relying party's own anchor, not the log.

**Scope.** One sequence for all of the author's packages. "LATEST_WITNESSED" means "the newest package this author
published", not "the newest for this action" or "for this claim". Measured consequences:

- An older package is STALE to every consumer once a newer one is logged, including a consumer that never acted on
  it (P4). With one log per author, at most one package is actionable at a time. That is a liveness cost, and it
  would be wrong for an author issuing decisions for several independent actions.
- A consumer that has seen the log refuses a log missing its newest lines (rollback). A consumer seeing the log for
  the first time cannot tell, and accepts the same rolled-back log (P5). First use is unprotected.

A per-action or per-claim scope would remove the first consequence. It is not built.

## 4. Retained-state assumptions

What the replay protection above needs, and whether this code meets it:

| Assumption | Met here? | Evidence |
|---|---|---|
| The consumed set and anchor survive a process restart | yes: a JSON file | P2, P5 |
| ... and survive power loss | **not shown**: the consumer's write is not fsynced, so a consumed digest could be lost and the package accepted again | read from the code, not run |
| One writer at a time, or an atomic check-and-claim | **no** for the consumer | P6 (both accept); P7 (4, 2 and 1 of 100 doubled across three runs); P7c (20 of 20 when the window is widened) |
| State writes are atomic (no torn file) | **no** for the consumer: `open(path, "w")` truncates first | P8; the unregistered P7 rerun saw a reader hit an empty file |
| A crash before the consumer's state write means no authorization | yes, for a caller that acts only on exit 0: the state is written before the consumer exits 0 | read from the code, not run |
| A crash after the consumer accepts but before the caller acts | the package is consumed and a retry is refused: at most once, possibly zero | read from the code, not run |
| The executor's claim is atomic across processes | **yes** for the reservation store (`O_CREAT \| O_EXCL`, one file per key) | MP-1: 0 of 200 / 100 / 30 trials doubled at N = 2 / 8 / 32; a deliberately non-atomic store doubled 100 of 100 |
| A crashed holder does not make the key runnable again | yes: an in-flight key is refused, and an expired lease becomes UNKNOWN and is still refused, until `release()` is called (intended for a person after investigating; not enforced) | MP-1 P3/P4 (holder killed before the effect: 0 effects; after: 1 effect; 8 retries refused in both, within the lease); RK-2 R7 (expired lease: 0 effects, refused, UNKNOWN) |
| A lost reply after the effect is not repeated | yes, if the key was fixed at intent | RK-2 R1/R2 (1 effect, retry refused); A3 shows the failure with a fresh key |

The executor numbers are from one local Linux filesystem. Not tested: Android storage, network filesystems, separate
machines, and a late `complete()` racing a lease expiry (listed as unrun in MP-1).

The fix for the consumer is to reuse what the executor already does: claim each key with an exclusive create
instead of rewriting one shared file, and key on the intent key in the record rather than the package digest. That
is my next change. It is not done.

## 5. Vector pairs

Inputs and a `vector.json` for each are in [`results/rp1/vectors/`](../results/rp1/vectors/). Commands run from the
repository root, and consumer state files start absent, except P8's torn file (below). A and B are two packages for
the same action; `log_A` holds A only, `log_AB` holds A then B.

| Pair | Accepting | Refusing | What the pair isolates |
|---|---|---|---|
| P1 | verify A (twice: identical output, exit 0) | verify A with its decision changed (exit 1) | verifying again is not an error; tampering is |
| P2 | A, fresh state (exit 0) | A again, same state (exit 1, `replay`; state file unchanged) | single use of one package |
| P3 | B after A, same state, `log_AB` (exit 0) | A again, same state, `log_AB` (exit 1) | the accepting half is the gap: a second package for the same action gets through. The refusing half fails two checks (`STALE` and `replay`), so it isolates nothing; P2 is the clean replay pair |
| P4 | A with `log_A`, fresh state (exit 0) | A with `log_AB`, a different fresh state (exit 1, `STALE`) | "latest" is relative order in the author's log |
| P5 | A with `log_A` (B's line cut off), fresh state (exit 0) | the same, with a state anchored on `log_AB` (exit 1, `rollback`) | rollback is visible only to retained state |
| P8 | B with the intact state (exit 0) | B with the state file torn in half (exit 2, `COULD NOT LOOK`) | a crash mid-write fails closed and stops progress |

To replay P8's refusing half, rebuild `T.state.json` as the first half of `S.state.json`'s bytes after P8's first
step (the runner did this; the file is not committed as an input). P6 and P7 are not file pairs. P6 is an in-process
interleaving of the real `consumer_check`. P7 is a race measured over 100 trials (`tools/rp1_vectors.py`).

## 6. For a relying-party section, offered as input only

From this one prototype, the points I would want a replay section to make explicit:

1. Re-verification, re-authorization and witness order are three operations with different state, as you put it.
2. The at-most-once key is an action or intent identifier fixed before the first attempt and bound into the signed
   record. A receipt digest is not enough, because one action can produce many receipts.
3. Claiming that key must be atomic and durable before the action, against concurrent relying parties and against a
   crash between the claim and the action. A section could say which way a crash may fail. "Possibly zero, never
   twice" is what I would want. My executor meets it in the cases measured. My consumer does not (P6, P7).
4. "Latest in a witness log" needs a stated scope (per issuer, per action, per claim). Relying parties without
   retained state cannot detect a rollback.

## What this does not show

- Anything about another implementation, or about the draft beyond what is quoted in
  [`IETF_MAP_RESULTS.md`](IETF_MAP_RESULTS.md).
- Signed packages. Behaviour on the S25 phone, Android storage, or across machines.
- That the vectors are complete. They cover the cases above and nothing else.

## Next unrun test

Make the consumer claim an intent key atomically (exclusive create, fsynced), give `make_package.py` a key fixed at
intent, and rerun P3 and P6–P8 with the predictions flipped.
