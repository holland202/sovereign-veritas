# Evidence package (sv.package/0) — reconstruct and challenge one gated run

Status: **Architecture Self-Tested** (same author wrote producer, verifier and tests; container
only until the S25 run is recorded here).

One JSON document carries a gated run: artifact bytes, measurement, the provenance chain up to the
decision record, verifier validation, every Gate input, resource state (runtime + thermal zones),
freshness, the decision, and a package digest. `tools/verify_package.py` checks it with the
standard library only and imports nothing from `sovereign_veritas`: it recomputes every digest,
recomputes the measurement where the kind allows (`sha256_chain`), **replays the Gate** from the
recorded inputs, re-derives verifier-validation status and the per-domain thermal summary, and
rejects claims v0 cannot verify (freshness PROVEN, identity bound, missing limitations).
Exit 0 consistent, 1 a check failed, 2 unreadable.

`tools/make_package.py` produces one on the device through the real EvidenceWorkflow.

## What a CONSISTENT verdict means — and does not

It means the parts agree and the recorded decision is the one the documented Gate produces from the
recorded inputs. It does **not** mean authentic, fresh, or that the declared verifier object ran:
every package carries those four limitations, and the verifier fails a package that drops one.

## Registered before any package code ran (2026-09-25T21:24:14Z, md5 c0951a529357b1bb2a10197d159ec5e7)

```
# Evidence package v0 — registered before any package code was run
Base: feature/local-inference-measurement merged with main (tree 6dce015), container.
Package: artifact bytes, measurement, provenance chain, verifier validation, gate inputs,
resource state (runtime + thermal zones), freshness, decision, package digest.
Verifier: tools/verify_package.py, stdlib only, imports nothing from sovereign_veritas
(same author as the producer - N-version, not independent).

P0 anti-vacuity: an untouched package verifies (exit 0); the same package with only the
   decision flipped and EVERY digest recomputed fails.
P1 replay: the 4608-point gate_constraint lattice, each point run through the real Gate and
   packaged, replays to the identical decision AND reason strings in the verifier: 4608/4608.
P2 challenge: every inconsistent single-field rewrite is detected even when the attacker
   recomputes every digest it can (record digests, chain links, package digest). k/k.
P3 freshness: default packages report NOT_PROVEN; a package claiming PROVEN fails.
P4 boundary (predicted UNDETECTED, by design): a fully consistent rewrite - runtime changed
   to 'hot', decision rewritten to the gate's own DEFER, all digests recomputed - verifies.
   Self-consistency is not authenticity; that needs a signature or external witness.
```

## Results (container x86_64, Python 3.12.3) — `tests/test_package.py`

- **P0 confirmed.** Untouched package: every check passes. Decision flipped with every digest
  resealed: `gate_replay` fails.
- **P1 confirmed with a recorded deviation.** Registered 4608 lattice points; ran **2304/2304**
  exact replays (decision and full reason strings). The input-digest axis cannot be packaged:
  `build_package` refuses a decision record whose `input_digest` is not the artifact's sha256, so
  the 2 digest values collapse to 1.
- **P2 confirmed: 18/18** inconsistent rewrites caught after a full reseal (every record digest,
  chain link and the package digest recomputed by the attacker):

```
decision ALLOW->REFUSE                     -> gate_replay
reasons appended                           -> gate_replay
runtime thermal -> hot                     -> gate_replay
policy excludes action                     -> gate_replay
capability unauthorized                    -> gate_replay
capability demands more evidence           -> gate_replay
capability renamed                         -> capability_named_in_record, gate_replay
artifact swapped (digests updated)         -> measurement_recomputed
measurement output forged                  -> measurement_recomputed
validation VALIDATED with a failed probe   -> verifier_provenance
validation relabelled UNTESTED             -> verifier_provenance
verifier id swapped                        -> verifier_provenance
identity claimed bound                     -> verifier_identity_not_overclaimed
thermal zone raw edited                    -> thermal
offline zone relabelled ok                 -> thermal
thermal summary max edited                 -> thermal
freshness claimed PROVEN                   -> freshness_not_overclaimed
limitation deleted                         -> limitations_declared
elapsed_ms rewritten (unregistered)        -> UNDETECTED
genesis record rewritten (unregistered)    -> UNDETECTED
```

- **P3 confirmed.** Packages report `NOT_PROVEN`; a package claiming `PROVEN` fails.
- **P4 confirmed (undetected, as registered).** Runtime rewritten to `hot`, decision rewritten to
  the Gate's own `DEFER [runtime_not_healthy]`, all digests resealed: the package verifies.
- **Unregistered, same class as P4** (last two rows above): values that are recorded but not
  recomputable — latency, a raw thermal reading together with its summary, earlier chain records —
  can be rewritten consistently and verify. The package makes inconsistency detectable; it does
  not make a determined rewrite detectable. That needs a signature or an external witness.

Anti-vacuity: disabling each verifier check in turn (gate replay, thermal, verifier provenance,
measurement recompute, freshness, limitations) makes `tests/test_package.py` fail every time (6/6).
Suite: 152 passed (container).
