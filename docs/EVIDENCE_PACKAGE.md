# Evidence package (sv.package/0) — reconstruct and challenge one gated run

Status: **Architecture Self-Tested** (same author wrote producer, verifier and tests).
Device-verified on the S25 — see the end of this file. Not independently reproduced.

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

## Device measurement — S25 (SM-S938U, Android 16, Termux, aarch64, Python 3.14.6)

Line breaks restored from terminal wrap; values verbatim.

At `0e86c65` (package commit), `python tools/make_package.py` (runtime left undeclared):

```
decision REFUSE ['runtime_state_unavailable']
elapsed_ms 91.507  zones 68  freshness NOT_PROVEN
package /data/data/com.termux/files/home/sv_package_de9fee31b190.json  md5 de9fee31b190cfa5accaf24bd03ab6d8
rc=0
```

`python tools/verify_package.py ~/sv_package_de9fee31b190.json`:

```
PASS  schema                             sv.package/0
PASS  package_digest
PASS  artifact_digest
PASS  measurement_names_artifact
PASS  measurement_recomputed             recomputed from artifact bytes
PASS  provenance_chain
PASS  decision_record_is_artifact
PASS  decision_record_matches
PASS  measurement_in_chain
PASS  capability_named_in_record
PASS  gate_replay                        replayed REFUSE ['runtime_state_unavailable']
PASS  verifier_identity_not_overclaimed
PASS  verifier_provenance                sha256-chain-recompute-v0 VALIDATED
PASS  thermal                            zone statuses and per-domain summary recomputed
PASS  freshness_not_overclaimed          NOT_PROVEN
PASS  limitations_declared
VERDICT  CONSISTENT  freshness=NOT_PROVEN  authenticity=NOT_PROVEN
rc=0
```

At `ed042e7` (recovery commit): `python -m pytest -q` gave **157 passed in 9.31s**, rc=0, and
`python tools/package_recovery_sim.py ~/sv_package_de9fee31b190.json`:

```
package 17157 bytes, seed 7
TRUNCATION  0 of 17157 strict prefixes accepted
CORRUPTION  0 of 200 single-bit flips accepted []
VERDICT     nothing damaged was accepted
rc=0
```

This package was written by the pre-atomic writer (it predates `ed042e7`); it is complete, which is
what the verifier and the simulation confirm. The S25 package, the verifier's 16 checks, and the
recovery simulation all agree with the container runs above. Same author throughout.

## Red team round 1 — an NVIDIA-hosted model attacks the verifier (EXPLORATORY)

`tools/nvidia_challenge.py` (the run below used md5 c6a553f031564d3d73f4a9461613725d, kept outside the
repo; the committed version has the fixes listed after it). The model gets the S25 package and the
verifier's source, proposes edits; the tool applies them, recomputes every digest, and the verifier on
the phone judges. Accepted forgeries are also rebuilt with the real Gate. S25, 2026-09-25:

```
EXPLORATORY nvidia_challenge | model nvidia/nemotron-3.5-lightning-30b-a3b | 5 rounds | local verifier judges
log /data/data/com.termux/files/home/sv_challenge_1790389990.json  (written after every round)
round 1: UNUSABLE reply (JSONDecodeError: Extra data: line 1 column 30 (char 29))
round 2: UNUSABLE reply (JSONDecodeError: Expecting value: line 1 column 2 (char 1))
round 3: REJECTED by measurement_in_chain  (2 edits, 48.4s)
round 4: UNUSABLE reply (JSONDecodeError: Expecting value: line 1 column 2 (char 1))
round 5: ACCEPTED - within known limits K1-K3  paths [['measurement', 'kind'], ['measurement', 'output_sha256'], ['provenance', 'chain', -1, 'record', 'prediction', 'value', 'output_sha256']]
log /data/data/com.termux/files/home/sv_challenge_1790389990.json
VERDICT 0 forgery(ies) outside the known limits accepted
```

What this does and does not show:

- The pipeline works end to end against a real hosted model (the API key had to be replaced first:
  the NGC-console key returned 403 on every model).
- **Round 5 is not an independent discovery.** The prompt listed K1-K3 as known limits; the model
  used K3 (relabel the measurement kind so the verifier cannot recompute it, then forge the output).
- 3 of 5 rounds were unusable: this model writes its reasoning into the reply, brackets included, and
  the tool's parser took the first `[` to the last `]`. Two usable attempts is weak evidence of anything.

### Fixes that followed (container: 160 passed)

- **K3 closed, fail-closed.** A measurement kind the verifier cannot recompute now fails
  `measurement_recomputed` unless `--allow-recorded-only` is passed. Reverting this fails 2 tests.
- **Limitations must be exactly the four v0 statements.** Before, the verifier only checked that each
  required prefix appeared, so an appended line such as "authenticity: signed by device hardware" -
  contradicting the real one - verified. Found by the red-team tool's own mock test, not by the model.
  Reverting this fails 1 test. A test also pins producer and verifier to the same four statements.
- P2 now has 20 resealed rewrites (the two above added), all caught.
- `nvidia_challenge.py`: parses the last well-formed edit list in the reply, 4096-token replies,
  streamed with a per-chunk timeout and retries; K3 removed from the known list.

## Red team round 2 — 50 rounds overnight, then a deterministic sweep (EXPLORATORY)

S25, 2026-09-25/26, `nvidia/nemotron-3.5-lightning-30b-a3b`, stopped by hand at API call 240.
The script run was an edited copy of `nvidia_challenge.py` (it prints "API call N" and "attack k/50",
labels limits K1-K3, and uses the old first-`[`-to-last-`]` parser), not the committed version.
Counted from its log:

- 240 API calls: 212 unusable replies, 13 failed requests, **15 usable attacks**.
- 7 rejected (`measurement_recomputed` 3, `measurement_recomputed + measurement_in_chain` 1,
  `decision_record_matches + gate_replay` 2, `gate_replay` 1).
- 8 accepted, all editing a field no check recomputes: `measurement/elapsed_ms`, `artifact/name`,
  `resource_state/runtime/platform`, the decision record's `prediction/model_id`, a new
  `metadata/device` key on the decision record, and the genesis record's `decision` and
  `record_id` (twice). All are within the documented limit "authenticity: none".
- The replay history grows every round (package + verifier source + every reply), and the
  late rounds degraded to unusable replies and HTTP 400/404s. The loop is the wrong instrument.

### The cheaper instrument: `tools/field_sweep.py`

Mutates every leaf field one at a time, recomputes every digest, verifies. No model, no network,
under a second. On the test fixture package (container):

```
119 single-field rewrites (every digest recomputed): 44 verified, 36 distinct fields
  artifact/name
  gate_inputs/capability/description
  gate_inputs/capability/max_steps
  gate_inputs/capability_registry/root-off/authorized
  gate_inputs/capability_registry/root-off/description
  gate_inputs/capability_registry/root-off/max_steps
  gate_inputs/capability_registry/root-off/min_evidence_quality
  gate_inputs/capability_registry/root-off/name
  gate_inputs/capability_registry/root-off/parent
  gate_inputs/capability_registry/root-on/authorized
  gate_inputs/capability_registry/root-on/description
  gate_inputs/capability_registry/root-on/max_steps
  gate_inputs/capability_registry/root-on/min_evidence_quality
  gate_inputs/capability_registry/root-on/name
  gate_inputs/capability_registry/root-on/parent
  measurement/elapsed_ms
  provenance/chain/0/record/action
  provenance/chain/0/record/capability
  provenance/chain/0/record/decision
  provenance/chain/0/record/evidence_quality
  provenance/chain/0/record/input_digest
  provenance/chain/0/record/prediction
  provenance/chain/0/record/record_id
  provenance/chain/0/record/timestamp
  provenance/chain/0/record/uncertainty
  provenance/chain/0/record/verification
  provenance/chain/1/record/metadata/step_count
  provenance/chain/1/record/record_id
  provenance/chain/1/record/timestamp
  provenance/chain/1/record/uncertainty
  resource_state/runtime/platform
  resource_state/runtime/python_version
  resource_state/thermal/zones/*/raw
  resource_state/thermal/zones/*/type  (x5)
  resource_state/thermal/zones/*/zone  (x5)
  verifier/validation/total_probes
```

Every field the model found is in this class; the sweep finds all of them at once. Survivors are
either recorded-only (latency, names, timestamps, platform, earlier chain records, bcl readings)
or Gate inputs the recorded decision does not depend on (the capability registry when no parent
is declared, `max_steps` when no step limit is hit). None contradicts a stated limitation.
`tests/test_field_sweep.py` pins this set: binding a field must remove it on purpose, and losing a
check grows it and fails (demonstrated with gate replay disabled).

### Which checks carry weight against an attacker who recomputes digests

Each check disabled in turn; the number is how many fields become forgeable:

```
schema                             +1
package_digest                     +0
artifact_digest                    +0
measurement_names_artifact         +1
measurement_recomputed             +2
provenance_chain                   +0
decision_record_is_artifact        +1
decision_record_matches            +1
measurement_in_chain               +1
capability_named_in_record         +1
gate_replay                        +13
verifier_identity_not_overclaimed  +1
verifier_provenance                +8
thermal                            +21
freshness_not_overclaimed          +2
limitations_declared               +4
```

`package_digest`, `artifact_digest` and `provenance_chain` add **nothing** against this attacker:
anyone who can recompute sha256 reseals them. They catch accidental damage (R1/R2: 0 of 17157
truncations, 0 of 200 bit flips), not a deliberate rewrite. Unkeyed hashes are tamper-evidence
only against someone who does not recompute them — the "authenticity: none" limitation, measured.
Closing it needs a key: a signature over `package_sha256`.

## The sweep on the real S25 package, and the two derivable fields it exposed

S25 at `b0b82ad` (Python 3.14.6): `python -m pytest -q` gave **163 passed in 9.25s**, and
`python tools/field_sweep.py ~/sv_package_5bfc70dfcfa2.json` (the ALLOW package the model attacked
overnight, 68 zones) printed:

```
796 single-field rewrites (every digest recomputed): 549 verified, 371 distinct fields
```

The count was inflated by two gaps, not by the documented limits alone. 340 of the 371 lines were
`measurement/thermal_before/<n>/<field>`: the verifier never looked at the before-snapshot at all,
though its `domain` and `status` are derivable exactly like the after-snapshot's. And the decision
record's `metadata/execution_status` could be rewritten freely — including a REFUSE package claiming
the action ran. Every field the model found overnight is on the list.

### Registered before the fix (2026-09-26T10:06:40Z, md5 84a086880aa72986d28efd2094601000)

```
# Bind the derivable fields the S25 sweep exposed — registered before the fix ran
Source: field_sweep on the S25 package sv_package_5bfc70dfcfa2.json (ALLOW, 68 zones):
796 rewrites, 549 verified, 371 distinct fields (device, 2026-09-26).
Test object: the fixture package + measurement.thermal_before (5 zones) + decision-record
metadata.execution_status = "SUCCEEDED" (decision ALLOW), resealed.

D1 before the fix, the sweep on that object lists thermal_before/*/domain, */status, and
   metadata/execution_status as survivors.
D2 after the fix: thermal_before/*/domain, */status and execution_status are no longer survivors;
   thermal_before/*/raw, */type, */zone remain (recorded sensor readings: nothing to derive them from).
D3 a REFUSE package claiming execution_status SUCCEEDED fails (an action recorded as run without ALLOW).
D4 every pre-existing test passes unmodified; the pinned UNBOUND set for the plain fixture is unchanged.
```

### Result (container x86_64, Python 3.12.3)

- **D1 confirmed:** before the fix, all five `thermal_before` fields per zone and
  `metadata/execution_status` survived.
- **D2 confirmed:** after it, on the same object:

```
145 single-field rewrites (every digest recomputed): 58 verified, 39 distinct fields
  artifact/name
  gate_inputs/capability/description
  gate_inputs/capability/max_steps
  gate_inputs/capability_registry/root-off/authorized
  gate_inputs/capability_registry/root-off/description
  gate_inputs/capability_registry/root-off/max_steps
  gate_inputs/capability_registry/root-off/min_evidence_quality
  gate_inputs/capability_registry/root-off/name
  gate_inputs/capability_registry/root-off/parent
  gate_inputs/capability_registry/root-on/authorized
  gate_inputs/capability_registry/root-on/description
  gate_inputs/capability_registry/root-on/max_steps
  gate_inputs/capability_registry/root-on/min_evidence_quality
  gate_inputs/capability_registry/root-on/name
  gate_inputs/capability_registry/root-on/parent
  measurement/elapsed_ms
  measurement/thermal_before/*/raw  (x4)
  measurement/thermal_before/*/type  (x5)
  measurement/thermal_before/*/zone  (x5)
  provenance/chain/0/record/action
  provenance/chain/0/record/capability
  provenance/chain/0/record/decision
  provenance/chain/0/record/evidence_quality
  provenance/chain/0/record/input_digest
  provenance/chain/0/record/prediction
  provenance/chain/0/record/record_id
  provenance/chain/0/record/timestamp
  provenance/chain/0/record/uncertainty
  provenance/chain/0/record/verification
  provenance/chain/1/record/metadata/step_count
  provenance/chain/1/record/record_id
  provenance/chain/1/record/timestamp
  provenance/chain/1/record/uncertainty
  resource_state/runtime/platform
  resource_state/runtime/python_version
  resource_state/thermal/zones/*/raw
  resource_state/thermal/zones/*/type  (x5)
  resource_state/thermal/zones/*/zone  (x5)
  verifier/validation/total_probes
```

- **D3 confirmed:** a REFUSE package with `execution_status: SUCCEEDED` fails
  `execution_only_if_allowed`. A missing status still passes: not every package comes from
  `EvidenceWorkflow`.
- **D4 confirmed:** 165 passed (163 + 2 new); the pinned `UNBOUND` set is unchanged.
- Anti-vacuity: disabling either new check fails one test in `tests/test_package.py`.

What remains unbound is recorded sensor data (`raw`, `type`, `zone`) and fields no check can
recompute. Nothing derives a sensor reading; only a signature binds it.

## Signatures — closing "authenticity: none" (container)

`tools/sign_package.py` signs the package file's exact bytes with an ed25519 key through
`ssh-keygen -Y sign` (namespace `sv-package`). `tools/verify_package.py ... --signature SIG
--allowed-signers FILE --identity ID` checks it through `ssh-keygen -Y verify`; the verifier still
needs no Python packages. The private key stays on the device; `allowed_signers` holds only the
public key. A signature binds who signed these bytes. It says nothing about when: freshness stays
NOT_PROVEN, and a signed older package is still a valid older package.

### Registered before any signing code ran (2026-09-26T10:15:46Z, md5 cc59634fdf63908b6e5534c463e73bd1)

```
# Package signature (ssh-keygen -Y, ed25519) — registered before any signing code ran
Base: main f4989ac (tree 1792ebc), container. Signature is detached, over the package file's
exact bytes, namespace "sv-package", checked against an allowed_signers file by identity.
verify_package.py calls ssh-keygen; it stays free of Python dependencies.

S0 liveness: an untouched signed package verifies (exit 0) and reports authenticity=SIGNED:<id>.
S1 the fixture package's 119 single-field rewrites, each resealed: 44 verify without the signature
   check (the pinned UNBOUND set); 0 verify with it.
S2 each of these fails: a key not in allowed_signers; the right key under another identity;
   the right key, wrong namespace; a signature over a different package.
S3 signature requested but ssh-keygen absent: exit 2 (could not look), never a pass.
S4 a package verified without --signature behaves exactly as before (authenticity=NOT_PROVEN);
   every pre-existing test passes unmodified.
Expected by construction: S1's 0 follows from signing the bytes. What S1 measures is that the
check is wired in and live, not that ed25519 works.
```

### Result (container x86_64, Python 3.11.15, OpenSSH 9.6p1) — `tests/test_signature.py`

- **S0 confirmed:** untouched signed package verifies, `authenticity=SIGNED:chad`.
- **S1 confirmed**, the real tools end to end on the fixture package:

```
== unsigned sweep
119 single-field rewrites (every digest recomputed): 44 verified, 36 distinct fields
== signed sweep
119 single-field rewrites (every digest recomputed): 0 verified, 0 distinct fields
```

- **S2 confirmed:** an unlisted key, the right key under another identity, a wrong namespace, and a
  signature over another package's bytes each fail.
- **S3 confirmed:** with `ssh-keygen` off the PATH, a requested signature check exits 2
  (`COULD NOT LOOK`), never a pass.
- **S4 confirmed:** unsigned verification unchanged (`authenticity=NOT_PROVEN`); 165 pre-existing
  tests pass unmodified; 172 with the new ones.
- Anti-vacuity: a signature check that always accepts fails 2 of the 7 new tests.

Not yet measured: `ssh-keygen -Y` on the S25 (Termux OpenSSH), and anyone verifying a signature
with only the published public key.

### Device measurement — the S25 package signed on the S25 (OpenSSH 10.5p1, Python 3.14.6)

At `2c39272`: `python -m pytest -q` gave **172 passed in 11.23s** — the signature tests ran, not
skipped. Then the author's key was generated on the phone and the ALLOW package attacked overnight
(`sv_package_5bfc70dfcfa2.json`, 68 zones) was signed and swept. Line breaks restored from
terminal wrap; values verbatim:

```
holland202 namespaces="sv-package" ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIBe8+ScGb9CfAye5A97mGPGpDMTsR+v1kMfYOrSpVyNV
signature /data/data/com.termux/files/home/sv_package_5bfc70dfcfa2.json.sig
PASS  signature                          valid sv-package signature by holland202
VERDICT  CONSISTENT  freshness=NOT_PROVEN  authenticity=SIGNED:holland202
796 single-field rewrites (every digest recomputed): 0 verified, 0 distinct fields
```

Unsigned, the same sweep of the same package verified 405 of 796. S1 is now confirmed on the device
against real data. The public key is committed as `keys/allowed_signers`; the private key stays on
the phone. Still open: freshness (a signed older package still verifies), and verification by
anyone other than the author.

## Freshness witness v0 (container)

`tools/witness.py append PACKAGE.json` adds `<seq> <package_sha256>` to `witness/packages.log`
(append-only, only for packages that verify, never twice). The author commits and pushes it; GitHub's
copy is the witness. `verify_package.py --witness-log FILE` checks a package against a log the
challenger pulled themselves: `LATEST_WITNESSED` passes, `STALE` and `NOT_WITNESSED` fail, and a
malformed log is `COULD NOT LOOK`. The package's own `freshness` field still says `NOT_PROVEN` - a
package cannot know about later packages; the verdict reports what the log shows.

### Registered before any witness code ran (2026-09-26T10:34:38Z, md5 c84733cda9bfa7ad0c85d27303dc54d9)

```
# Freshness witness v0 — registered before any witness code ran
Base: main 41e8b39 (tree 7421493), container.
Design: witness/packages.log in the repo, append-only, one line per package: "<seq> <package_sha256>".
The author appends a package's digest and pushes; GitHub's copy of the log is the witness.
verify_package.py --witness-log FILE (a log the CHALLENGER pulled themselves) reports:
  LATEST_WITNESSED  - the package is the last entry           -> check passes
  STALE             - later entries exist (reports how many)  -> check fails
  NOT_WITNESSED     - the package is absent                   -> check fails
A malformed log is could-not-look (exit 2), never a pass or a plain fail.

W0 a package appended as the last entry: LATEST_WITNESSED, exit 0.
W1 after a second package is appended, the first reports STALE (1 later entry), exit 1.
W2 a package absent from the log: NOT_WITNESSED, exit 1.
W3 a log with non-increasing seq, a duplicate digest, or a non-hex digest: exit 2.
W4 without --witness-log, verification is unchanged (freshness=NOT_PROVEN); all prior tests pass.
W5 witness append refuses a package that does not verify, and refuses a digest already logged.
W6 the rollback case (restore an older valid, signed package after a newer one was witnessed):
   STALE, exit 1 — signature still valid, freshness not.
Stated limits, not tested away: order, not time; latest WITNESSED, not latest MADE (an unlogged
newer package is invisible); only as strong as the challenger's own copy of the log and the
remote's history (a force-push to main can rewrite it — branch protection closes that).
```

### Result (container x86_64, Python 3.11.15) — `tests/test_witness.py`

All of W0-W6 confirmed; 183 passed. The real tools on two packages, witnessed in order (exit codes
read without a pipe: old 1, new 0):

```
== old package
FAIL  freshness_witness                  STALE: entry 1 of 2: 1 newer package(s) witnessed
VERDICT  1 check(s) failed  freshness=STALE  authenticity=NOT_PROVEN
== new package
PASS  freshness_witness                  LATEST_WITNESSED(2): entry 2 of 2, the last
VERDICT  CONSISTENT  freshness=LATEST_WITNESSED(2)  authenticity=NOT_PROVEN
```

W6 is the rollback the anchored-ledger tests found on 2026-09-25: an older package with a valid
signature restored after a newer one was witnessed reports `PASS signature` and
`FAIL freshness_witness ... STALE`. Anti-vacuity: forcing "no newer entries" fails 2 tests; skipping
the sequence validation fails 2 tests.

Not yet measured: a witness log pushed from the S25 and checked by someone else from their own pull.
The trust boundary is GitHub's history of `main`; it is broken by a force push unless the branch
is protected.

## First real witness entry — and the defect that kept it off GitHub

S25, 2026-09-26: the signed ALLOW package was copied to `evidence/` with its signature, appended to
the witness log (`witnessed 1 6888cbf2f5f450af32aeeac93f7f6ceafd990677ac912ef184f5308164b2a1f6`), and
verified on the phone with all three layers: `CONSISTENT  freshness=LATEST_WITNESSED(1)
authenticity=SIGNED:holland202`, then committed and pushed as `6589904`.

**Defect:** the commit carried 2 files, not 3. `.gitignore` line 57 is `*.log`, so
`witness/packages.log` was silently ignored: `git add witness` added nothing and printed nothing. The
phone's `LATEST_WITNESSED(1)` was checked against a log that existed only on the phone - not a
witness. The name was chosen without checking the ignore rules. Fixed here: `.gitignore` now
un-ignores `witness/packages.log`; `witness.py` refuses to append to any log git would ignore; a test
fails if the committed log path is ignored (it fails against the old `.gitignore`).

### Verified from a fresh public clone of `6589904` (container x86_64, Python 3.11.15, OpenSSH 9.6p1)

Only files from the repository - the package, its signature, `keys/allowed_signers` - on a machine
the package never touched. Exit code 0 (read without a pipe):

```
PASS  schema                             sv.package/0
PASS  package_digest                     
PASS  artifact_digest                    
PASS  measurement_names_artifact         
PASS  measurement_recomputed             recomputed from artifact bytes
PASS  provenance_chain                   
PASS  decision_record_is_artifact        
PASS  decision_record_matches            
PASS  measurement_in_chain               
PASS  capability_named_in_record         
PASS  gate_replay                        replayed ALLOW []
PASS  verifier_identity_not_overclaimed  
PASS  verifier_provenance                sha256-chain-recompute-v0 VALIDATED
PASS  thermal                            zone statuses and per-domain summary recomputed
PASS  thermal_before                     68 zones: domain and status recomputed
PASS  execution_only_if_allowed          SUCCEEDED under ALLOW
PASS  freshness_not_overclaimed          NOT_PROVEN
PASS  limitations_declared               exactly the four v0 statements
PASS  signature                          valid sv-package signature by holland202
VERDICT  CONSISTENT  freshness=NOT_PROVEN  authenticity=SIGNED:holland202
```

Freshness reads `NOT_PROVEN` here because the witness log is not public yet. This is still the author's
own verifier; a reproduction by someone else remains open.

## All three layers from GitHub alone

Fresh clone of `5b64d8e` (container x86_64, Python 3.11.15, OpenSSH 9.6p1): the published package,
its signature, `keys/allowed_signers` and `witness/packages.log`, nothing from the phone. Exit code 0,
read without a pipe; 20 PASS, 0 FAIL:

```
PASS  schema                             sv.package/0
PASS  package_digest                     
PASS  artifact_digest                    
PASS  measurement_names_artifact         
PASS  measurement_recomputed             recomputed from artifact bytes
PASS  provenance_chain                   
PASS  decision_record_is_artifact        
PASS  decision_record_matches            
PASS  measurement_in_chain               
PASS  capability_named_in_record         
PASS  gate_replay                        replayed ALLOW []
PASS  verifier_identity_not_overclaimed  
PASS  verifier_provenance                sha256-chain-recompute-v0 VALIDATED
PASS  thermal                            zone statuses and per-domain summary recomputed
PASS  thermal_before                     68 zones: domain and status recomputed
PASS  execution_only_if_allowed          SUCCEEDED under ALLOW
PASS  freshness_not_overclaimed          NOT_PROVEN
PASS  limitations_declared               exactly the four v0 statements
PASS  signature                          valid sv-package signature by holland202
PASS  freshness_witness                  LATEST_WITNESSED(1): entry 1 of 1, the last
VERDICT  CONSISTENT  freshness=LATEST_WITNESSED(1)  authenticity=SIGNED:holland202
```

This closes the milestone as scoped on 2026-09-25: an end-to-end package whose artifact, measurement,
provenance, verifier, freshness, resource state and Gate decision can be reconstructed and challenged
from public files. What it still is not: independently reproduced (every check so far ran on the
author's verifier, by the author or his AI tools), time-stamped (the witness gives order, not time),
or protected against a rewrite of `main`'s history unless the branch is protected.

## Branch protection on `main` — registered and tested (2026-09-26)

The witness log is only as strong as GitHub's history of `main`. Prediction, registered before the
test: with the ruleset active, a non-fast-forward push to `main` is refused by GitHub and `main` does
not move. The test can fail: had the push been accepted, `main` would have moved back one commit
(recoverable by a fast-forward push of the old head).

Ruleset as read back from the GitHub API (not from the settings page):

```
active {'ref_name': {'exclude': [], 'include': ['~ALL']}} ['deletion', 'non_fast_forward'] [] 2026-09-26T06:06:47.735-05:00
```

`rules/branches/main` lists `deletion` and `non_fast_forward` from ruleset 24038678; bypass list empty.

The test, from the container, `main` at e6d2c3a, pushing its parent 197b0b0 with `--force`:

```
remote: error: GH013: Repository rule violations found for refs/heads/main.
remote: - Cannot force-push to this branch
 ! [remote rejected] HEAD~1 -> main (push declined due to repository rule violations)
exit=1
```

`origin/main` after the attempt: `e6d2c3a3aaebe39055bb1832ff6ac37da082d3b2` (unchanged). Confirmed.

What this does not cover: the repository owner can disable or delete the ruleset, and GitHub itself
is trusted. A challenger who keeps their own clone of the log detects a rewrite regardless; the
ruleset only stops it happening silently through a push. Deletion blocking was not tested (a
successful test would delete a branch).


## Measured thermal status — registered before any code (2026-09-26)

Until now `thermal_status` is typed in by the caller (`--thermal-status normal`), and every
package says so: "resource state: runtime fields are declared by the caller, not derived from
thermal zones". This step derives `thermal_status` from the zones the package already records
(`measurement.thermal_before`, read before the run) and makes the verifier recompute it.

Policy `s25-uncalibrated-v0`, per-domain limits in millidegrees as the kernel reports them. A domain
is hot when its hottest `ok` zone is at or above its limit:

| domain | limit | why this number |
|---|---|---|
| cpu_core, cpu_subsystem, gpu, npu | 95000 | S25 probe run: cores 39.9-46.3 °C idle, up to 104.2 °C after 30 s all-core load; 95 sits between |
| battery | 45000 | chosen; battery peaked at 33.3 °C in that run |
| board | 50000 | chosen; board thermistors peaked at 39.709 °C in that run |

These limits are chosen from one probe run on one device. They are not calibrated and not a
safety claim. Every other domain (ddr, modem, camera, video, always_on, pmic, rf, bcl, unknown)
is recorded but does not decide.

Derivation, in order: for each limited domain, any zone `unreadable` or `out_of_range` -> `unknown`;
no `ok` zone -> `unknown`. Otherwise any domain at or above its limit -> `hot`; else `normal`.
`offline` zones (powered down, -273000) are skipped. The existing Gate contract is unchanged:
`normal` -> healthy; `hot` -> degraded -> DEFER `runtime_not_healthy`; `unknown` -> unavailable ->
REFUSE `runtime_state_unavailable`.

Registered predictions:

- **T0** Declared packages are unchanged: the published S25 package still passes 20 of 20 with
  signature and witness; the fixture sweep is still 119 rewrites, 44 verified unsigned, 0 signed.
- **T1** Derivation on synthetic zones: all limited domains below limit -> `normal`; one domain at
  exactly its limit -> `hot`; a limited domain with no `ok` zone, or with one `unreadable` or
  `out_of_range` zone -> `unknown`; offline zones and unlimited domains never change the result.
- **T2** Gate consequence through a real package: `normal` -> ALLOW []; `hot` -> DEFER
  [runtime_not_healthy] with no execution recorded; `unknown` -> REFUSE [runtime_state_unavailable].
  All three packages verify CONSISTENT.
- **T3** Binding against a resealing attacker (every digest recomputed): rewriting
  `thermal_status` hot -> normal together with a matching ALLOW decision fails
  `thermal_status_derived`; so does raising a limit, renaming the policy, deleting
  `thermal_before`, or relabelling a measured package as declared.
- **T4** No thermal zones (the container, CI): `make_package.py --thermal-status measured` gives
  REFUSE [runtime_state_unavailable] and the package verifies CONSISTENT, exit 0.
- **T5** S25 at rest: `measured` gives `normal`, ALLOW [], CONSISTENT, one more PASS line than a
  declared package (`thermal_status_derived`).
- **T6** S25 under load (`--preload-seconds 30`: all-core busy loops, `thermal_before` read while
  they still run): cpu_core at or above 95 °C -> `hot` -> DEFER [runtime_not_healthy], no execution,
  CONSISTENT. This is the anti-vacuity control on real hardware: the derived status can come back
  something other than `normal`.
- **T7** Anti-vacuity of the check: a verifier that trusts the package's recorded status instead of
  recomputing it fails the T3 tests.

Stated limits, not tested away: the snapshot is one instant before the run, not during it; the
limits are uncalibrated and fit only the S25 domain map (another device reads `unknown` and
REFUSEs); raw readings are recorded data, so an unsigned rewrite that lowers them consistently
still verifies (the signature closes that for anyone but the key holder); the key holder can
still sign false readings. `compute_budget` and `power_status` stay declared.

### Result (container x86_64, Python 3.11.15) — `tests/test_thermal_policy.py`

28 passed; full suite 213 passed. T0-T4 confirmed; T7 confirmed, with a gap found on the way.

- **T0** The published S25 package, with signature and witness: 20 `PASS`, exit 0, no
  `thermal_status_derived` line. `tests/test_field_sweep.py` and `tests/test_signature.py`
  (fixture: 119 rewrites, 44 verified unsigned, 0 signed): 10 passed, unchanged.
- **T1** 14 derivation cases on fake zone trees; the kernel and the verifier's re-implementation
  agree on every one, including exactly-at-limit -> `hot`.
- **T2** `make_package.py --thermal-status measured --thermal-root <fake tree>`: cool -> ALLOW [],
  execution recorded; one CPU zone at 99600 -> DEFER [runtime_not_healthy], no execution;
  battery unreadable -> REFUSE [runtime_state_unavailable]. All three verify, exit 0.
- **T3** After a full reseal, hot -> normal with a matching ALLOW fails exactly
  `thermal_status_derived`. Raising a limit, renaming the policy, deleting `thermal_before`, and
  relabelling the source as declared each fail. Two rewrites verify, as stated in advance and
  pinned as tests: removing every trace of "measured" (a fully consistent rewrite), and lowering
  the recorded raw readings. Only the signature binds those.
- **T4** This container has no `/sys/class/thermal`:

```
thermal unknown (battery: no readable zone)  policy s25-uncalibrated-v0  zones 0
decision REFUSE ['runtime_state_unavailable']
PASS  gate_replay                        replayed REFUSE ['runtime_state_unavailable']
PASS  thermal_status_derived             s25-uncalibrated-v0: recomputed unknown, recorded unknown
PASS  limitations_declared               the four statements, resource state measured
VERDICT  CONSISTENT  freshness=NOT_PROVEN  authenticity=NOT_PROVEN
exit=0
```

  Field sweep on that package: `78 single-field rewrites (every digest recomputed): 33 verified,
  33 distinct fields` (unsigned).
- **T7** A verifier that uses the recorded status instead of recomputing it fails
  `test_t3_status_rewritten_to_normal_with_matching_allow_fails` (1 of the 7 T3 tests; the other
  checks still catch the limit, policy, snapshot and relabel rewrites). Using `>` for `>=` in both
  derivations fails 3 T1 cases.
- **Found by sabotage:** deleting the unreadable/out-of-range rule from the verifier failed
  NO test at first: every case had one zone per domain, so "no ok zone" caught it anyway. Two
  cases added (a bad zone beside a good one); deleting the rule from either copy now fails both.

Also corrected: the README said a fresh package gives 16 `PASS` lines. It gives 18, and did before
this change (checked on the previous commit).

### Result (S25, Termux) — T5 and T6

`git pull` to 2033088, then `213 passed in 16.01s`, `sleep 30`, then two runs. Verbatim:

```
thermal normal (all limited domains below limit)  policy s25-uncalibrated-v0  zones 68
decision ALLOW []
elapsed_ms 76.071  zones 68  freshness NOT_PROVEN
package /data/data/com.termux/files/home/sv_package_118a02b75646.json  md5 118a02b756462c4c7b1e17067e1e8d7b
PASS  gate_replay                        replayed ALLOW []
PASS  thermal_before                     68 zones: domain and status recomputed
PASS  thermal_status_derived             s25-uncalibrated-v0: recomputed normal, recorded normal
PASS  execution_only_if_allowed          SUCCEEDED under ALLOW
PASS  limitations_declared               the four statements, resource state measured
VERDICT  CONSISTENT  freshness=NOT_PROVEN  authenticity=NOT_PROVEN
rest exit=0
thermal hot (cpu_core 103800>=95000; cpu_subsystem 95300>=95000)  policy s25-uncalibrated-v0  zones 68
decision DEFER ['runtime_not_healthy']
elapsed_ms 88.852  zones 68  freshness NOT_PROVEN
package /data/data/com.termux/files/home/sv_package_45c6ad182584.json  md5 45c6ad1825848d003931561c398a6281
PASS  gate_replay                        replayed DEFER ['runtime_not_healthy']
PASS  thermal_before                     68 zones: domain and status recomputed
PASS  thermal_status_derived             s25-uncalibrated-v0: recomputed hot, recorded hot
PASS  execution_only_if_allowed          no execution recorded
PASS  limitations_declared               the four statements, resource state measured
VERDICT  CONSISTENT  freshness=NOT_PROVEN  authenticity=NOT_PROVEN
load exit=0
```

Each run printed 19 `PASS` lines (the other 14 are the unchanged checks, all PASS); a declared
package prints 18.

- **T5 confirmed.** At rest: `normal`, ALLOW [], executed, CONSISTENT, 19 `PASS` = 18 + 1.
- **T6 confirmed.** After 30 s of all-core load: `hot` from cpu_core 103.8 °C, DEFER
  [runtime_not_healthy], nothing executed, CONSISTENT. The Gate's decision on this device now
  changes with a sensor reading, and the verifier recomputed the reason.
- Worth noting, not a finding: cpu_subsystem reached 95.3 °C, 0.3 °C over its limit. The CPU core
  zones alone decided it (103.8). One run; the limits are still uncalibrated.

Both packages stay on the device and are not signed or witnessed. The resource-state limitation
is now narrower on the S25: `thermal_status` is measured; `compute_budget` and `power_status`
are still declared.

## Publishing the measured pair — registered before the phone step (2026-09-26)

Plan: sign the two S25 packages from T5 and T6 (`sv_package_118a02b75646`, ALLOW at rest;
`sv_package_45c6ad182584`, DEFER under load) with the committed key and publish them in
`evidence/` beside the first package.

**Not witnessed yet, on purpose.** Someone outside the project is reproducing the published
package (`sv_package_5bfc70dfcfa2`) against `witness/packages.log`. Appending entries now would turn
that package's result from `LATEST_WITNESSED(1)` into `STALE` while it is being checked. The pair is
witnessed after the reproduction comes back; until then its freshness is `NOT_PROVEN`, and the
verifier says so.

**Defect found while preparing.** Container, test key, two packages witnessed in order, the older
one verified with its valid signature:

```
PASS  signature                          valid sv-package signature by chad
FAIL  freshness_witness                  STALE: entry 1 of 2: 1 newer package(s) witnessed
VERDICT  1 check(s) failed  freshness=STALE  authenticity=NOT_PROVEN
exit=1
```

The verdict reports authenticity `NOT_PROVEN` for a signature the same output reports valid:
`authenticity` was `SIGNED` only when every check passed. W6 asserted the PASS and FAIL lines, not
the verdict, so no test caught it. It would be the public output for the first package as soon as a
newer one is witnessed.

Registered predictions:

- **R1** Verdict fix: authenticity comes from the signature check alone. The case above prints
  `authenticity=SIGNED:chad` with `1 check(s) failed`, exit 1; an invalid signature still prints
  `NOT_PROVEN`. Reverting the fix fails the new test.
- **R2** Published-evidence invariants, as a test on every push: every package in `evidence/` has a
  signature that verifies as `holland202` against `keys/allowed_signers` and passes every
  consistency check; every witness entry names a package published in `evidence/` (the log claims
  "made public", so that must be true); the last entry verifies `LATEST_WITNESSED`, earlier ones
  `STALE` with the right count, unlogged packages `NOT_WITNESSED`. On copies, each of these
  sabotages fails the test: one flipped byte, swapped signature files, a log entry with no
  published package.
- **R3** After the phone push, from a fresh clone of GitHub: each new package verifies with its
  signature, exit 0, 20 `PASS` (19 + signature), `authenticity=SIGNED:holland202`,
  `freshness=NOT_PROVEN`; the DEFER package replays DEFER [runtime_not_healthy] with no execution.
- **R4** Same clone, with `--witness-log`: both new packages fail `freshness_witness` as
  `NOT_WITNESSED`, exit 1, still `authenticity=SIGNED:holland202`; the first package is still
  `LATEST_WITNESSED(1)`, exit 0. Publishing is not witnessing, and the check tells them apart.
- **R5** Field sweep on the published DEFER package: with its signature, 0 rewrites verify. Without
  it some survive (recorded data); that number is measured, not predicted.
- **R6** All 9 CI jobs pass on the commit that adds the pair.

### Result (container x86_64, Python 3.11.15) — R1 and R2

- **R1 confirmed.** The same case after the fix:

```
PASS  signature                          valid sv-package signature by chad
FAIL  freshness_witness                  STALE: entry 1 of 2: 1 newer package(s) witnessed
VERDICT  1 check(s) failed  freshness=STALE  authenticity=SIGNED:chad
exit=1
```

  `test_w7_verdict_keeps_a_valid_signature_when_freshness_fails` fails when the old line is put
  back; `test_w7_invalid_signature_is_still_not_proven` holds the other side.
- **R2 confirmed in the container** for the one package published so far:
  `tests/test_published_evidence.py`, 8 passed; full suite 223 passed. The checker is proven on a
  synthetic tree first: intact passes; one changed byte, swapped signature files, a missing
  signature file and a witness entry with no published package each fail it.
- **Found by sabotage, again:** replacing the checker's witness comparison with "accept anything"
  failed no test at first, because the checker and `check_witness` read the same log and agreed.
  Added a case where `check_witness` is replaced by one that lies; it now fails. The comparison is
  a cross-check of the verifier's freshness logic, not a second source of truth.
- `test_t0_published_package_still_verifies` no longer passes `--witness-log`: T0 was confirmed
  with 20 of 20 at 2033088, but that package is `LATEST_WITNESSED(1)` only until a newer one is
  witnessed. It now checks consistency and signature (19 `PASS`); witness status moved to R2.

### Result — R3 to R6 (fresh clone of GitHub at 211b703, container x86_64, Python 3.11.15)

The pair was signed on the S25 and pushed from Termux (`223 passed` there before the commit).
From a fresh clone, with `--signature evidence/<pkg>.sig --allowed-signers keys/allowed_signers
--identity holland202`:

```
== R3 118a02b75646 (signature)
PASS  gate_replay                        replayed ALLOW []
PASS  thermal_status_derived             s25-uncalibrated-v0: recomputed normal, recorded normal
PASS  execution_only_if_allowed          SUCCEEDED under ALLOW
PASS  signature                          valid sv-package signature by holland202
VERDICT  CONSISTENT  freshness=NOT_PROVEN  authenticity=SIGNED:holland202
exit=0 PASS=20 FAIL=0
== R3 45c6ad182584 (signature)
PASS  gate_replay                        replayed DEFER ['runtime_not_healthy']
PASS  thermal_status_derived             s25-uncalibrated-v0: recomputed hot, recorded hot
PASS  execution_only_if_allowed          no execution recorded
PASS  signature                          valid sv-package signature by holland202
VERDICT  CONSISTENT  freshness=NOT_PROVEN  authenticity=SIGNED:holland202
exit=0 PASS=20 FAIL=0
== R4 118a02b75646 (signature + witness)
FAIL  freshness_witness                  NOT_WITNESSED: not among 1 witnessed packages
VERDICT  1 check(s) failed  freshness=NOT_WITNESSED  authenticity=SIGNED:holland202
exit=1
== R4 45c6ad182584 (signature + witness)
FAIL  freshness_witness                  NOT_WITNESSED: not among 1 witnessed packages
VERDICT  1 check(s) failed  freshness=NOT_WITNESSED  authenticity=SIGNED:holland202
exit=1
== R4 5bfc70dfcfa2 (signature + witness)
PASS  freshness_witness                  LATEST_WITNESSED(1): entry 1 of 1, the last
VERDICT  CONSISTENT  freshness=LATEST_WITNESSED(1)  authenticity=SIGNED:holland202
exit=0
```

- **R3 confirmed.** Both 20 of 20, `SIGNED:holland202`; the DEFER package replays DEFER with no
  execution.
- **R4 confirmed.** Both new packages `NOT_WITNESSED`, exit 1, signature still reported; the first
  package still `LATEST_WITNESSED(1)`. Without R1's fix these two lines would have read
  `authenticity=NOT_PROVEN`.
- **R5 confirmed.** `tools/field_sweep.py` on the published DEFER package: unsigned,
  `807 single-field rewrites (every digest recomputed): 408 verified, 33 distinct fields`; with its
  signature, `807 single-field rewrites (every digest recomputed): 0 verified, 0 distinct fields`.
  The unsigned survivors include `measurement/thermal_before/*/raw (x61)` and
  `measurement/preload_seconds`. The sweep adds 1 to a reading, which never crosses a limit; the 7
  readings it cannot change are the offline zones (+1 turns the -273000 sentinel into
  `out_of_range`). So without the signature the readings are recorded data, as stated before the
  code, and `preload_seconds` could be edited to hide that the heat was induced. Signed, neither can.
- **R6 confirmed.** Run 36240440331 on 211b703: 9 of 9 jobs pass. Logs read for three: ubuntu 3.12
  and macOS 3.12 `223 passed`; windows 3.14 `215 passed, 8 skipped` (the 8 POSIX-lock tests), so
  the signature half of the published-evidence check ran on Windows too. The measured-thermal CI
  step read `zones 0` on all three, `thermal unknown`, REFUSE, `CONSISTENT`.

Still open: witnessing the pair, after the outside reproduction of `sv_package_5bfc70dfcfa2` is back.
