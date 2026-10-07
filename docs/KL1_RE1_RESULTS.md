# KL-1 and RE-1 results: SIGNED means "a key in today's allowed-signers file signed these bytes" (8 of 8 as registered); the verifier had no size limit and misreported memory exhaustion (6 of 6 as registered); three fixes

Registration: `docs/KL1_RE1_PREREG.md`, commit `9e52fa2`, **pushed** before `tools/kl1_probe.py` and `tools/re1_probe.py`
existed. Baseline `b7d072b`. Linux container (x86_64, Python 3.13.16, OpenSSH 9.6p1). **S25 NOT VALIDATED**: Android's
memory killer acts before Python's `MemoryError`, and Termux's OpenSSH may differ. Claude-assisted (Claude Opus 5.5): the
same model registered, built, ran and judged this, so it is **self-tested**. Chad Holland directed the work. He has not
reviewed this text or the code line by line.

## Failures, limits and corrections (first)

1. **KL-P5, a defect, fixed.** The allowed-signers file had an extra line `* namespaces="sv-package" <attacker key>`. An
   attacker's fully consistent package then verified as `VERDICT  CONSISTENT  freshness=NOT_PROVEN
   authenticity=SIGNED:holland202`. The verdict named an identity the signer was never listed under. The verdict now
   reads `authenticity=SIGNED:holland202[pattern:*]`. The signature still passes, because refusing pattern entries is
   EXPERIMENT FIRST, as registered.
   **My first fix was wrong, and my own test caught it before commit.** It used `ssh-keygen -Y find-principals`, which
   ignores namespaces. When the key was listed by name only for another namespace, it reported `holland202`, so the verdict
   would have read `SIGNED:holland202[pattern:holland202]`. The fix now verifies each allowed-signers line alone with
   ssh-keygen, under that line's own options.
2. **RE-P2 and RE-P5, a defect, fixed.** Memory exhaustion exited 1, which is the code for "a check failed":
   - a 400 MB package under a 1 GiB address-space limit;
   - a 10⁷-entry witness log under 512 MiB.

   In `tools/consumer.py`, exit 1 means REFUSED. Both now print `COULD NOT LOOK: MemoryError` and exit 2.
3. **RE-P1, a limit, not fixed.** There is no input size limit:
   - a 100 MB package verified `CONSISTENT`, with a peak of 401 MB;
   - with no memory limit, a 400 MB package verified CONSISTENT in 27.9 s (the sabotage run).

   The padding sat in `artifact.name`, which no check binds (the field sweep already lists it). A default size cap is
   EXPERIMENT FIRST, as registered.
4. **RE-P4, a limit.** A witness log costs about 8× its size in memory: 10⁶ entries is a 72 MB file with a 587 MB peak. Not
   fixed; it was not registered as a fix.
5. **KL-P2, P3, P4, P7 and P8: limits, now measured.**
   - Rotation by replacement: a genuine old package fails exactly as a forgery does (`1 check(s) failed ...
     authenticity=NOT_PROVEN`, exit 1).
   - An expired validity window does the same. The verifier has no option to verify at signing time, and SSH signatures
     carry no signing time (KL-P7). That time would have to come from elsewhere, and the witness log has no clock.
   - A KRL is never read: a revoked key still verifies `SIGNED:holland202`, while `ssh-keygen -r` refuses the same
     signature.
   - A leaked key signs consistent packages that verify `SIGNED:holland202`.
6. **RE-P3, a defect, fixed.** `json_depth` scanned the whole text before refusing. 50 MB of `[` took 3.66 s against 0.83 s
   for 10 MB (ratio 4.41), although the limit was exceeded at byte 65.
7. **Instrument corrections.**
   - The KL-1 probe first compared authenticity as a substring, which the fixed verdict would also match. It now compares
     the whole token. The registered run is unaffected: every token in it was exactly `authenticity=SIGNED:holland202`.
   - The RE-1 sabotage run overlapped my edit of `verify_package.py`. Its outputs show pre-fix behaviour (RE-P3 ratio 4.46,
     RE-P5 `MemoryError` exit 1). A rerun in a clean worktree at `9e52fa2` gave the same result:
     `re1_sabotage_prefix_worktree.txt`, `5 of 6`, RE-P2 refuted under sabotage.

## Outcome

### KL-1 (8 of 8 as registered; `results/kl1/kl1_registered.txt`)

| ID | Case | Result |
|---|---|---|
| KL-P1 | control: both keys listed | HELD: exit 0, `authenticity=SIGNED:holland202` |
| KL-P2 | rotation by replacement | HELD: exit 1, `authenticity=NOT_PROVEN` for the genuine old package |
| KL-P3 | expired validity window | HELD: exit 1 through the verifier; `ssh-keygen -Overify-time=20251231` rc 0 |
| KL-P4 | KRL revoking the key | HELD: exit 0, `SIGNED:holland202` through the verifier; `ssh-keygen -r` rc 255 |
| KL-P5 | `*` principal line, attacker's package | HELD: exit 0, `CONSISTENT`, `authenticity=SIGNED:holland202` |
| KL-P6 | package bytes signed under `sv-effect-receipt` | HELD: exit 1 with the line restricted and unrestricted |
| KL-P7 | SSHSIG fields | HELD: `['magic', 'version', 'publickey', 'namespace', 'reserved', 'hash_algorithm', 'signature']`, 0 trailing bytes |
| KL-P8 | leaked key | HELD: exit 0, `CONSISTENT`, `SIGNED:holland202` |

Sabotage (KL-P2 keeps `k_old` listed): `7 of 8`, exit 1. After the fix: `--expect-fix` gives `8 of 8`. In registered mode,
KL-P5 is now REFUTED by design (`authenticity=SIGNED:holland202[pattern:*]`).

### RE-1 (6 of 6 as registered; `results/re1/re1_registered.txt`)

| ID | Case | Result |
|---|---|---|
| RE-P1 | 1, 10, 50, 100 MB | HELD: all exit 0 and `CONSISTENT`; 0.17, 0.69, 3.17, 6.22 s; peak 23.3, 57.6, 210.1, 401.0 MB; r(time) 1.0000, r(peak) 1.0000 |
| RE-P2 | 400 MB, `RLIMIT_AS` 1 GiB | HELD: exit 1, last line `MemoryError` (22.9 s) |
| RE-P3 | 10 and 50 MB of `[` | HELD: exit 2 both; 0.83 and 3.66 s; ratio 4.41 |
| RE-P4 | witness log 10⁵ and 10⁶ entries | HELD: exit 0 both, LATEST_WITNESSED; 0.43 and 3.52 s; peak 78.2 and 587.0 MB; ratio 8.17 |
| RE-P5 | 10⁷ entries (729 MB), `RLIMIT_AS` 512 MiB | HELD: exit 1, `MemoryError` (0.1 s) |
| RE-P6 | rounds = 10,000,000 | HELD: exit 0, 3.60 s |

Baseline: the genuine 4709-byte package takes 0.099 s and peaks at 19.4 MB. After the fixes, `--expect-fix` gives `6 of 6`:
- RE-P2 and RE-P5 print `COULD NOT LOOK: MemoryError` and exit 2;
- RE-P3 takes 0.11 s at 10 MB and 0.17 s at 50 MB, a ratio of 1.55;
- in registered mode RE-P2, RE-P3 and RE-P5 are REFUTED, by design (`3 of 6`).

## Fixes, as decided in the registration

| Held | Registered decision | Done | Test (fails at `9e52fa2`) |
|---|---|---|---|
| KL-P5 | IMPLEMENT: report the principal pattern that matched | `signature_listing()`: each line verified alone; VERDICT `SIGNED:<id>[pattern:<p>]` | `test_the_signature_listing_says_how_the_identity_matched` (8 cases), `test_the_verdict_names_the_pattern` |
| RE-P2, RE-P5 | IMPLEMENT: MemoryError is COULD NOT LOOK in the verifier and the consumer | added to both exception lists | `test_verifier_reports_memory_exhaustion_as_could_not_look`, `test_consumer_reports_memory_exhaustion_...` |
| RE-P3 | IMPLEMENT: early exit in `json_depth` | `json_depth(text, stop_above)` | `test_json_depth_stops_as_soon_as_the_limit_is_exceeded` |
| KL-P2, P3, P4 | DOCUMENT; `--revocation-list` and binding signatures to witness positions or a witness clock are EXPERIMENT FIRST | this document | — |
| RE-P1 | a default size cap is EXPERIMENT FIRST | not done | — |

Against the code at `9e52fa2`, `tests/test_kl1_re1.py` gave `12 failed, 2 passed`. The two passes are the deliberate
behaviour-preservation checks: the depth refusal message and the literal-listing verdict are unchanged.

## What SIGNED means, measured (AUTHENTIC ≠ CURRENTLY TRUSTED ≠ FRESH ≠ AUTHORIZED)

- **SIGNED** means that a key in the allowed-signers file **as it is when you verify** signed these exact bytes under
  `sv-package`. That key is listed for the identity by name, or now visibly by pattern. It is judged at verification time
  (KL-P3), ignoring revocation lists (KL-P4), and it says nothing about when the bytes were signed (KL-P7). It is
  "currently trusted", not "trusted when signed".
- **FRESH** (`LATEST_WITNESSED`) is position in a witness log you pulled yourself. It has no clock and no signature, and it
  is independent of keys.
- **AUTHORIZED** is the Gate's recorded decision, independent of keys.
- The missing link is "this key was trusted when this package was made". It needs a time that someone other than the
  signer vouches for. The candidate (EXPERIMENT FIRST) is witness checkpoints signed by a separate witness key that carry
  the witness's own clock. A package witnessed at entry *n* would then be checkable against the signer's validity at the
  time of checkpoint *n*.

## Left unrun

- The S25: Android's memory killer, and Termux's OpenSSH.
- Consumers racing on a log that takes longer to read than the 30 s lock timeout.
- `cert-authority` and `sk-ssh-ed25519` keys.
- A default size cap and its false-refusal rate.
- A quoted principals field (reported as a pattern by design; not exercised).

## Reproduce

```
python tools/kl1_probe.py [--sabotage | --expect-fix]
python tools/re1_probe.py [--sabotage | --expect-fix]     # writes ~1 GB of temporary files, about 2 minutes
python -m pytest -q tests/test_kl1_re1.py
```
