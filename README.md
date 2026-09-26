# Sovereign Veritas

A fail-closed permission gate for AI actions. Before an action runs, the Gate decides
ALLOW, DEFER or REFUSE, and the decision can be written into an evidence package that a
separate verifier, sharing no code with this package, rebuilds and checks from the file alone.

Developed and run on a Galaxy S25 in Termux. Standard library only. The kernel makes no network
calls and has no telemetry; one optional red-team tool (below) calls NVIDIA's API when you run it.

## Try it — about 5 minutes, Python 3.10+

```bash
git clone https://github.com/holland202/sovereign-veritas
cd sovereign-veritas
python -m pip install -e ".[test]"
python -m pytest -q
python tools/make_package.py --thermal-status normal
# Copy the package path printed above, then run:
python tools/verify_package.py /path/to/the/package.json
```

Use `python3` if that is your interpreter. What you should see:

- **pytest:** all tests pass. On Windows the 8 anchored-ledger tests skip — that ledger needs
  POSIX file locking and refuses to write without it (tested on every platform).
- **make_package:** `decision ALLOW []` and a package path in your home directory.
- **verify_package:** 18 `PASS` lines and `VERDICT  CONSISTENT`.

Anything else is a finding. Please open an issue with your OS, Python version and the raw output.
Without `--thermal-status`, nothing vouches for the runtime state and the Gate REFUSEs: that is
the fail-closed default, not an error. `--thermal-status measured` derives the status from the
device's thermal zones instead of taking your word for it (below). Linux, macOS and Windows are tested in CI on every push
(GitHub-hosted runners); the author's own device is an Android phone.

Want to break it? Edit a package so the verifier still says CONSISTENT while it claims something
false. One way is already known and documented (a fully consistent rewrite, below). Anything
else is a real bug and will be credited.

## Sign a package (optional — needs `ssh-keygen`; Termux: `pkg install openssh`)

```bash
python tools/sign_package.py keygen YOUR_NAME   # once; prints your allowed_signers line
# Save that line in a file, e.g. allowed_signers, and share it: it holds only the public key.
python tools/sign_package.py sign /path/to/the/package.json
python tools/verify_package.py /path/to/the/package.json --signature /path/to/the/package.json.sig \
    --allowed-signers allowed_signers --identity YOUR_NAME
```

Packages signed by this repository's author verify against the committed public key:
`--allowed-signers keys/allowed_signers --identity holland202`.

With a valid signature the verdict reads `authenticity=SIGNED:YOUR_NAME`. The private key stays in
`~/.ssh/sv_package_ed25519` and never goes in the repo. A signature proves who signed the exact
bytes, not when: freshness is still not proven.

## Prove a package is the newest (optional)

```bash
python tools/witness.py append /path/to/the/package.json   # adds its digest to witness/packages.log
git add witness/packages.log && git commit -m "witness package" && git push
```

GitHub's copy of that append-only log is the witness. A challenger pulls it themselves and runs
`python tools/verify_package.py /path/to/the/package.json --witness-log witness/packages.log`:
`LATEST_WITNESSED` passes; `STALE` (a newer package was witnessed) and `NOT_WITNESSED` fail. This
proves order, not time, and only among packages the author logged. It holds as long as nobody
rewrites `main`'s history. This repository's `main` is protected by the ruleset `protect-main`
(force pushes and deletions blocked on every branch, no bypass); a test force push was rejected by
GitHub on 2026-09-26 (`docs/EVIDENCE_PACKAGE.md`). Forks need their own protection.

## What a CONSISTENT package does not prove

Every package states these, and the verifier fails a package that drops one:

- **authenticity** — the package carries no signature; a fully consistent rewrite verifies.
  A detached signature checked with `--signature` closes this (see above); the statement inside
  the package still describes the package on its own
- **freshness** — an older valid package is indistinguishable from the newest. A witness log
  checked with `--witness-log` shows whether it is the newest the author made public (see above)
- **verifier identity** — declared by the caller, not bound to the verifier object that ran
- **resource state** — runtime fields are declared, not derived from the device's sensors.
  With `--thermal-status measured`, `thermal_status` is instead derived from the zones read before
  the run, under per-domain limits chosen from one S25 probe run (policy `s25-uncalibrated-v0`, not
  calibrated), and the verifier recomputes it (`thermal_status_derived`); the package then says so.
  `compute_budget` and `power_status` stay declared. A device without the S25's zone types reads
  `unknown` and REFUSEs

## What has been measured

| What | Result | Where |
|---|---|---|
| Test suite | 185 passed, code as at `5b64d8e` | S25, Python 3.14.6 (device) |
| Test suite, fresh clones | 157 passed @ `ed042e7` | container, Python 3.10, 3.11, 3.12, 3.13 |
| Gate: 4608-case decision lattice | identical decision digest | S25 3.14.6; container 3.10 and 3.12 |
| Gate: deliberate bugs planted | 19 of 19 caught | S25 and container |
| A real package made on the S25 | 16 of 16 checks, `CONSISTENT` | S25 |
| Damaged copies of that package | 0 of 17,157 truncations, 0 of 200 bit flips accepted | S25 |
| Fully consistent rewrite | verifies — the documented limit | container |
| Single-field rewrites of a real S25 package, every digest recomputed | 405 of 796 verify (33 fields: recorded data nothing can recompute) | S25, unsigned |
| Same sweep, same S25 package, signed | 0 of 796 verify | S25 |
| Same sweep on the signed fixture package | 0 of 119 verify (44 without the signature) | container |
| Older package after a newer one is witnessed | `STALE`, exit 1 — even with a valid signature | container |
| Published package `evidence/sv_package_5bfc70dfcfa2.json`, all three layers, from a fresh clone of GitHub only | 20 of 20 checks: `CONSISTENT`, `SIGNED:holland202`, `LATEST_WITNESSED(1)` | container x86_64, Python 3.11, OpenSSH 9.6 |
| CI on every push: Linux, macOS, Windows × Python 3.10 / 3.12 / 3.14 | 9 of 9 jobs pass; gate decision digest identical to the S25's in all 9 | GitHub Actions, run 36236747944 @ `197b0b0` |
| Thermal status derived from the zones, at rest | `normal`, ALLOW, 19 of 19 checks | S25 |
| Same, after 30 s all-core load | `hot` (cpu_core 103.8 °C), DEFER, 19 of 19 checks | S25 |
| Reproduction by anyone else | **none yet** | — |

Details and raw output: [docs/GATE_CONSTRAINT.md](docs/GATE_CONSTRAINT.md),
[docs/EVIDENCE_PACKAGE.md](docs/EVIDENCE_PACKAGE.md), [docs/THERMAL_ZONES.md](docs/THERMAL_ZONES.md),
[STATUS.md](STATUS.md). Status of all of it: **self-tested** — one author and his AI tools
(Claude, ChatGPT) wrote the code, the verifier and the tests.

## Repository map

- `sovereign_veritas/` — the kernel: Gate, evidence records and ledgers, capabilities, runtime
  state, verifier registry, thermal evidence, evidence packages
- `tools/verify_package.py` — the independent verifier (imports nothing from the kernel)
- `tools/make_package.py` — produce one package on your machine
- `tools/gate_constraint.py` — checks the Gate's ALLOW set against a fail-closed spec
  (`--mutants` checks that the check itself can fail)
- `tools/package_recovery_sim.py` — feeds the verifier torn and corrupted copies of a package
- `tools/field_sweep.py` — lists every field an attacker can rewrite undetected (optionally with a signature)
- `tools/sign_package.py` — ed25519 signing via `ssh-keygen -Y`; the verifier checks with `--signature`
- `tools/witness.py` — appends a package to the freshness witness log; the verifier checks with `--witness-log`
- `sovereign_veritas/thermal_policy.py` — derives `thermal_status` from zones under a named policy
- `tools/thermal_probe.py`, `tools/physical_durability.py` — device measurements (Android/Linux)
- `tools/nvidia_challenge.py` — optional, EXPLORATORY, **makes network calls**: an NVIDIA-hosted
  model tries to forge a package; the local verifier judges. Needs your own key in `~/.nvidia_api_key`
- `sv_real_inference_test.py` — exploratory; needs a local llama-server; not part of the tests

## Core ideas

1. Models produce observations, not proof.
2. Verification is a separate state from prediction.
3. Actions require a declared capability and evidence sufficiency.
4. The runtime may defer or refuse when evidence is incomplete or the environment is unsafe.
5. Decisions are append-only evidence, not informal status messages.
6. The adversary generates challenges and counterevidence; it never authorizes.
7. Authorization changes are ledgered **before** the registry mutates.

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) and [ROADMAP.md](ROADMAP.md).

Adversarial epistemic contract:
[docs/ADVERSARIAL_EPISTEMIC_VERIFICATION.md](docs/ADVERSARIAL_EPISTEMIC_VERIFICATION.md)

## Authority boundary

```text
Adversary ----X----> Veritas Gate
```

```text
external authorization
        ↓
EvidenceRecord
        ↓
EvidenceSink / Ledger
        ↓
registry mutation
```

If custody fails, the registry does not change.

## License and credit

MIT. You may use, change, share and sell this, including commercially, on one condition: keep the
copyright notice (`Copyright (c) 2026 Chad Holland`) and the license text with every copy or
substantial portion. That is the credit the license requires.

If you use Sovereign Veritas in work you publish — a paper, a product, a post — please also cite
it. GitHub's **Cite this repository** button gives the format (from `CITATION.cff`).
