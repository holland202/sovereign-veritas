# XPLAT — the verifier and the Gate across operating systems and instruction sets (registration)

Status: **Registered, UNRUN.** This file is committed alone, before the comparator, the leg script and the workflow
exist. Results go in a dated amendment below. This text is not edited after commit.

Registered 2026-10-04. Drafted by Claude (Opus 5.5) at Chad Holland's request ("Yes proceed", after Arm's Works on
Arm runners came up). Chad owns the decision to merge. The method is the one already run in veritas-eval-harness
(`XPLAT_PREREG.md` there, all six legs, 2026-10-04).

## Question

`tests.yml` already runs the suite on Linux x86_64, macOS arm64 and Windows x86_64. It has never run on Linux on
Arm, and nothing here has run on a big-endian machine. A verifier that answers differently on different machines
is the failure this project most needs to rule out, and it has happened once already: on 2026-10-02, macOS with
Python 3.14 parsed 100,000-deep JSON without RecursionError and the verifier gave a different verdict there
(fixed with `MAX_JSON_DEPTH = 64`, PR #6). Does the same code give the same verdicts everywhere?

## Legs

| Leg | Runner | ISA | Byte order | Python |
|---|---|---|---|---|
| L1 | ubuntu-latest | x86_64 | little | 3.14 |
| L2 | ubuntu-24.04-arm (GitHub's Arm runner, Works on Arm) | aarch64 | little | 3.14 |
| L3 | macos-latest | arm64 | little | 3.14 |
| L4 | windows-latest | x86_64 | little | 3.14 |
| L5 | QEMU-emulated s390x (IBM Z instruction set) | s390x | **big** | distro python3 |
| L6 | QEMU-emulated ppc64le (IBM Power instruction set) | ppc64le | little | distro python3 |

Scope, stated now:
- L5 and L6 emulate the instruction sets under QEMU. They are **not** runs on IBM hardware and must never be
  described as such.
- L2 is an Arm Neoverse server core. The S25 runs Qualcomm's own cores implementing the Arm instruction set. L2
  shares the S25's ISA, not its CPU design or its OS. The S25 enters only through digests already pinned from it.
- Intel macOS and Windows on Arm are not tested.

## What each leg runs (stdout and stderr, one file each)

| File | Command |
|---|---|
| `gate.txt` | `tools/gate_constraint.py --target .` |
| `contract_kernel.txt` | `tools/gate_contract.py --check kernel` |
| `contract_verifier.txt` | `tools/gate_contract.py --check verifier` |
| `packages.txt` | `tools/verify_package.py` on every `evidence/sv_package_*.json`, with `--signature`, `--allowed-signers keys/allowed_signers`, `--identity holland202`, `--witness-log witness/packages.log`, and each exit code |
| `attacks.txt` | `tools/attack_harness.py --round2 --round3` |
| `corridor.txt` | `tools/corridor_challenge.py` |
| `recovery.txt` | `tools/recovery_admissibility.py` |
| `xb1.txt` | `tools/execution_boundary_probe.py --expect-fix` |

## Predictions

- **P0 — Arm in the main suite.** Adding `ubuntu-24.04-arm` to the `tests.yml` matrix, the suite and every step in
  that job pass on Python 3.10, 3.12 and 3.14.
- **P1 — every leg runs.** On every leg, each command above exits as it does on Linux x86_64: 0 for all, except
  `verify_package.py`, which exits 0 for `sv_package_7548237bceca.json` and 1 for the other seven (five STALE, two
  NOT_WITNESSED).
- **P2 — pinned values.** On every leg: gate `DIGEST ab816905b1faf69aeaf24119b207cf7b80fcebd2ffcddac80d3edfa5e4da2d65`
  (the value pinned in `tests.yml` as identical to the S25); conformance digest
  `44823d0ff707213ae8bc310ed8b21e135f8e742fd8834e8f9474743d3a250628` for kernel and verifier; corridor
  `DIGEST 4f09350ea05ee3d30ee9e2cd69c62d5fd459ddcb5984cd700c94509369afa665`.
- **P3 — one answer everywhere.** Each of the eight files has a single normalized sha256 across all legs that ran.
- **P4 — big-endian.** L5 satisfies P1–P3. Registered separately because it is the leg most likely to break. A
  read of the code before registering found one explicit byte-order use, `int.from_bytes(..., "big")` in
  `tools/model_action.py`, which is order-independent by construction. Nothing else was found; that is a reading,
  not evidence.

Known risk, registered: L4 needs `ssh-keygen` for the signature checks. Git for Windows ships one and `tests.yml`
already passes there, but this run calls it from a script rather than from pytest.

## Normalization (declared before any leg runs; nothing else is removed)

1. `\r` removed (Windows writes `\r\n` to redirected output).
2. Lines starting `gate_constraint v` removed (they name the interpreter version and machine).
3. Lines starting `target ` removed (they name the checkout's absolute path).

Measured before registering, in a Linux x86_64 container (Python 3.13): two full runs of the leg script gave
byte-identical files, and no other line named a path, a time or a version.

## Anti-vacuity

- `python tools/xplat_digest.py --selftest` must report agreement on identical legs, a split when one byte of one
  file differs, and a P2 failure when a pinned digest is missing. If the selftest passes but the comparator cannot
  fail, P2 and P3 are void.
- Per leg, the commands keep their own controls (`gate_contract.py` exits 1 on any mismatch; the attack harness's
  P0 and the corridor's V14a are anti-vacuity predictions of their own).

## Outcome rules

- A leg that never starts (runner label or action unavailable) is **VOID**, not FAIL.
- A leg that starts and disagrees is a **finding**, kept, not tuned away. No normalization rule is added after
  seeing results; a new rule needs a new registration.
- No claim about hardware, operating systems or Python versions outside the table.

## Left unrun

- The same eight files computed on the S25 itself and compared with the legs.
- Real IBM hardware rather than emulation; Intel macOS; Windows on Arm.
- A real Arm server outside GitHub (Works on Arm cloud instances).

---

## Amendment 1 — 2026-10-04 (UTC), first run, all six legs

Run A: GitHub Actions run 37211950455 on `025f4ed` (the workflow commit, after the registration `08237a0`).
Nothing above this line was edited. `tests.yml` (P0) was still running at the time of writing; its outcome goes in
Amendment 2.

Platforms as each leg reported them (`platform.platform()`, machine, `sys.byteorder`, Python):

| Leg | Reported | Byte order | Python |
|---|---|---|---|
| L1 | Linux x86_64 (Azure) | little | 3.14.7 |
| L2 | Linux aarch64 (Azure, GitHub Arm runner) | little | 3.14.7 |
| L3 | macOS 26.6.2 arm64 | little | 3.14.7 |
| L4 | Windows Server 2025 AMD64 | little | 3.14.7 |
| L5 | Linux s390x, QEMU | **big** | 3.12.3 |
| L6 | Linux ppc64le, QEMU | little | 3.12.3 |

No leg was VOID. The comparator selftest passed (agreement on legs differing only in platform lines and `\r\n`; a
split on one added byte; a P2 failure on a missing pinned digest).

| | Result |
|---|---|
| **P1** every leg runs | holds on all six: every command exited 0 |
| **P2** pinned digests | holds on all six: gate `ab816905…`, conformance `44823d0f…` (kernel and verifier), corridor `4f09350e…` |
| **P3** one sha256 per file | **fails on L4 for `attacks.txt`**; holds for the other seven files on all six legs |
| **P4** big-endian (L5) | holds |

**Finding (L4), kept:** the only difference is the first line of `tools/attack_harness.py`'s output:

    L1..L3, L5, L6:  corpus 21 packages, latest runs/vehicle_sitl_v13/sv_package_a911244dfcf7.json
    L4:              corpus 21 packages, latest runs\vehicle_sitl_v13\sv_package_a911244dfcf7.json

The harness prints a path built with `os.path.relpath`, which uses the platform's separator. Every result line
(GENUINE, A1–A10, D3 rows, P0–P15) is identical on all six legs, and the same package is chosen as latest. So this
is a reporting difference, not a different verdict. But P3 as registered compares whole files, and on L4 it fails.
No normalization rule is added for it (the registration forbids that). The fix goes in the tool, in a separate
commit, and is judged by a fresh run in Amendment 2. This amendment does not count the fixed run as a pass for the
code as registered.

Correction to the PR description: five, not four, of these outputs (`contract_kernel`, `contract_verifier`,
`attacks`, `corridor`, `xb1`) have the same sha256 as the matching logs in Amos Tipton's reproduction bundle.
Exploratory, not a registered prediction.
