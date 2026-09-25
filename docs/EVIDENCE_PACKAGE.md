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

## Recovery simulation

Question: when a package is damaged, or its writer dies mid-write, does anything false get
accepted — and can the system produce a valid package again?

### Registered before the simulation code ran (2026-09-25T21:44:58Z, md5 17631b216306f4cd498ae3e5acf60be0)

```
# Package recovery simulation — registered before the simulation code ran
Question: when a package is damaged or its writer dies mid-write, does anything false get
accepted, and can the system produce a valid package again?

R1 truncation: every strict prefix of a valid package is rejected (exit != 0). 0 accepted.
R2 corruption: 500 seeded single-byte flips of a valid package: 0 accepted.
R3 current writer (plain open/write, as in make_package.py today): a process killed
   mid-write (os._exit) leaves a torn file at the FINAL path. The verifier rejects it,
   but the torn file sits under a name that claims an md5 its content does not have.
R4 atomic writer (temp file + fsync + os.replace): a process killed mid-write or just before
   the rename leaves NOTHING at the final path; a rerun writes a package that verifies.
R5 decision recovery: REFUSE (runtime unknown) then, with a declared valid runtime, ALLOW;
   both packages verify, and the REFUSE package still verifies afterwards (nothing overwritten).
```

### Results (container x86_64, Python 3.12.3) — `tests/test_package_recovery.py`

Process deaths are real (`os._exit(9)` in a child process), not raised exceptions.

- **R1 confirmed.** Every strict prefix of a package is rejected: 0 accepted.
- **R2 confirmed.** 500 seeded single-bit flips: 0 accepted.
- **R3 confirmed — a defect in the writer this commit replaces.** `make_package.py` wrote straight
  to its final path. Killed mid-write, it left a torn file under `sv_package_<md5>.json` whose
  content does not have that md5. The verifier rejected it (exit 2), so nothing false was
  accepted — but a file sat under a name that lies about it.
- **R4 confirmed.** `write_package()` writes a temp file, fsyncs, then renames. Killed mid-write
  or just before the rename, it leaves nothing at the final path (only a `.tmp-<pid>` file); a
  rerun writes a package that verifies. `make_package.py` now uses it.
- **R5 confirmed.** REFUSE with runtime unknown, then ALLOW with a declared runtime: both verify,
  and the REFUSE package still verifies after the second is written.

Anti-vacuity: making the writer non-atomic fails R4; disabling the verifier's package-digest check
fails R2 — some fields (artifact name, limitation wording, recorded latency) are guarded by the
package digest alone. Accidental corruption is caught there; deliberate rewrites are the P4 boundary.

`tools/package_recovery_sim.py PACKAGE.json` runs R1 and R2 against a real package. Container run on
a 4417-byte package: 0 of 4417 prefixes, 0 of 200 flips accepted, 9.5 s.
