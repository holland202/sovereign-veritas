# KL-1 (key lifecycle) and RE-1 (resource exhaustion) — registration

**Status:** REGISTERED, nothing built or run. Committed alone, before `tools/kl1_probe.py` and `tools/re1_probe.py` exist.
Baseline: `b7d072b`.

**Provenance.** Designed by Claude (Opus 5.5) at Chad Holland's direction; the same model builds, runs and judges:
**self-tested**. Container (Linux x86_64) only. **S25 NOT VALIDATED.**

## Why

`tools/verify_package.py` reports `authenticity=SIGNED:<identity>` when `ssh-keygen -Y verify -f ALLOWED_SIGNERS -I
<identity> -n sv-package` succeeds. It passes no revocation list (`-r`) and no verification time (`-Overify-time`), and
SSH signatures carry no signing time. The directive this work answers asks to keep AUTHENTIC, CURRENTLY TRUSTED, FRESH and
AUTHORIZED apart. KL-1 measures what SIGNED means as keys are rotated, expired, revoked, leaked or listed under a pattern.

The verifier and consumer read whole files and have no size cap; `MemoryError` is not among the exceptions the verifier
reports as COULD NOT LOOK (exit 2), and exit 1 means "a check failed". RE-1 measures what large inputs cost and how
exhaustion is reported.

## KL-1 predictions

Setup: identity `holland202`; keys `k_old`, `k_new`, `k_attacker` (ed25519); `P_old` a genuine package from
`tools/make_package.py` signed by `k_old`; `P_forged` a fully consistent rewrite (inputs and decision changed, every digest
recomputed) signed by whichever key the case names. Verdicts are read from `verify_package.py`'s VERDICT line and exit code.

| ID | Case | Prediction | Refuted if |
|---|---|---|---|
| KL-P1 | control: `P_old`, both keys listed for `holland202` | SIGNED, exit 0 | not SIGNED |
| KL-P2 | rotation by replacement: only `k_new` listed | signature check FAIL, exit 1: a genuine old package gets the verdict a forgery gets | SIGNED, or exit 0 or 2 |
| KL-P3 | rotation by validity window: `k_old` with `valid-before` in the past | FAIL through `verify_package.py` (it has no verification-time option); `ssh-keygen -Y verify -Overify-time=<inside the window>` on the same files succeeds | SIGNED through `verify_package.py`, or the direct `-Overify-time` check fails |
| KL-P4 | revocation: a KRL revoking `k_old` | still SIGNED through `verify_package.py` (it never reads a KRL); `ssh-keygen -Y verify -r KRL` fails | not SIGNED through `verify_package.py`, or the direct `-r` check succeeds |
| KL-P5 | pattern principal: an extra allowed-signers line `* namespaces="sv-package" <k_attacker>`; `P_forged` signed by `k_attacker`, verified with `--identity holland202` | CONSISTENT and `authenticity=SIGNED:holland202`: the verdict names an identity the signer was never listed under | anything else |
| KL-P6 | namespace binding: `P_old`'s bytes signed by `k_old` under `sv-effect-receipt`; allowed-signers line once restricted to `sv-package`, once unrestricted | FAIL both times | SIGNED either time |
| KL-P7 | signing time: the armored SSHSIG blob parsed field by field | no field carries a time | a time field exists |
| KL-P8 | leaked key: `P_forged` signed by `k_old` while `k_old` is listed | CONSISTENT, SIGNED (a limit: SIGNED means a listed key signed these bytes, not that the author did) | not SIGNED |

## RE-1 predictions

Each input runs `verify_package.py` in a child process; peak memory is the child's `ru_maxrss`; each timing is taken
3 times (median and spread reported, C-NOISE). Large inputs are a genuine package with one string field padded
(the closed schema then fails a check, but only after reading and parsing).

| ID | Case | Prediction | Refuted if |
|---|---|---|---|
| RE-P1 | padded packages of 1, 10, 50, 100 MB | no refusal before the whole file is read and parsed; wall time and peak memory each grow linearly (Pearson r ≥ 0.99 over the four sizes); peak memory at 100 MB ≥ 2× the file size | a size refusal, r < 0.99, or peak < 2× size |
| RE-P2 | 400 MB package under a 1 GiB address-space limit (`RLIMIT_AS`) | `MemoryError`, uncaught: exit 1, the code for "a check failed" | exit 2 (COULD NOT LOOK) or 0 |
| RE-P3 | `[` repeated 10 MB and 50 MB (depth > 64 from byte 65) | COULD NOT LOOK (exit 2) both times, and the 50 MB refusal takes ≥ 4× the 10 MB one: `json_depth` scans the whole text before refusing | an exit other than 2, or the ratio < 4 |
| RE-P4 | witness logs of 10⁵ and 10⁶ entries (package last) | both read and judged (LATEST_WITNESSED, exit 0); time grows linearly (10⁶ takes ≥ 5× the 10⁵ time) | not judged, or the ratio < 5 |
| RE-P5 | witness log of 10⁷ entries under a 512 MiB address-space limit | `MemoryError`, uncaught: exit 1 | exit 2 or 0 |
| RE-P6 | `sha256_chain` with `rounds` = 10,000,000 (the verifier's maximum) | completes; wall time reported (a bound, not a defect); < 30 s in this container | does not complete, or ≥ 30 s |

Anti-vacuity: KL-P1 must say SIGNED and KL-P2 must not (the instrument can say both); RE-P3 must reach exit 2 (the
instrument tells exit 1 from exit 2); a `--sabotage` flag in each probe flips one input so a registered prediction fails.

## What a held prediction leads to (decided now)

- RE-P2 or RE-P5 held: IMPLEMENT `MemoryError` → COULD NOT LOOK (exit 2) in `verify_package.py` and `consumer.py`.
  A default input-size cap: EXPERIMENT FIRST (genuine packages are kilobytes; a cap could still refuse a legitimate input).
- RE-P3 held: IMPLEMENT an early exit in `json_depth` (same verdicts, less work), with a test that the verdicts do not change.
- KL-P2/P3/P4 held: DOCUMENT in the threat model; an optional `--revocation-list` passed to `ssh-keygen -r` is
  EXPERIMENT FIRST; binding signatures to witness positions or a witness clock is EXPERIMENT FIRST.
- KL-P5 held: IMPLEMENT reporting of the principal pattern that matched (`ssh-keygen -Y find-principals`), so the verdict
  can no longer name an identity the signer was not listed under; refusing pattern entries is EXPERIMENT FIRST.

## Left unrun

The S25 (Android memory limits are lower and the OOM killer acts before `MemoryError`), consumers racing on a log that
takes longer to read than the 30 s lock timeout, certificate-authority entries (`cert-authority`) in allowed-signers,
hardware-backed keys (`sk-ssh-ed25519`).
