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
- **verify_package:** 16 `PASS` lines and `VERDICT  CONSISTENT`.

Anything else is a finding. Please open an issue with your OS, Python version and the raw output.
Without `--thermal-status`, nothing vouches for the runtime state and the Gate REFUSEs: that is
the fail-closed default, not an error. Windows is untested by the author.

Want to break it? Edit a package so the verifier still says CONSISTENT while it claims something
false. One way is already known and documented (a fully consistent rewrite, below). Anything
else is a real bug and will be credited.

## What a CONSISTENT package does not prove

Every package states these, and the verifier fails a package that drops one:

- **authenticity** — there is no signature; a fully consistent rewrite verifies
- **freshness** — an older valid package is indistinguishable from the newest
- **verifier identity** — declared by the caller, not bound to the verifier object that ran
- **resource state** — runtime fields are declared, not derived from the device's sensors

## What has been measured

| What | Result | Where |
|---|---|---|
| Test suite | 157 passed @ `ed042e7` | S25, Python 3.14.6 (device); fresh clones on Python 3.10, 3.11, 3.12, 3.13 (container) |
| Gate: 4608-case decision lattice | identical decision digest | S25 3.14.6; container 3.10 and 3.12 |
| Gate: deliberate bugs planted | 19 of 19 caught | S25 and container |
| A real package made on the S25 | 16 of 16 checks, `CONSISTENT` | S25 |
| Damaged copies of that package | 0 of 17,157 truncations, 0 of 200 bit flips accepted | S25 |
| Fully consistent rewrite | verifies — the documented limit | container |
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

## License

MIT
