# Physical Durability Experiment

## Purpose

Measure `FileLedger` behavior after an actual process or device interruption
on the target Galaxy S25 / Termux environment.

This is distinct from the software torn-write simulation already covered by
`DurabilityProbe`.

The evidence remains **durability_characterization**. It must not be promoted
to a general power-loss, filesystem, or storage durability claim.

## Safety

- Use only a disposable experiment directory.
- Never point this experiment at production evidence.
- Prefer SIGKILL or a controlled Termux force-stop before attempting device
  reboot or physical power interruption.
- Do not interrupt unrelated workloads.
- Preserve the complete experiment directory after each run.

## Environment capture

Before each experiment, record:

```bash
git rev-parse HEAD
git status --short
python --version
uname -a
getprop ro.product.model
getprop ro.build.version.release
getprop ro.build.version.sdk
```

The writer also records environment metadata in `SESSION.json`.

## Start

From the repository root:

```bash
python tools/physical_durability.py writer \
  ./runtime-durability-physical \
  --interval-s 0.01
```

The program prints its PID.

The writer handles SIGINT and SIGTERM as clean shutdowns. Therefore those
signals are **not** abrupt interruption tests.

## Abrupt process interruption

For SIGKILL:

```bash
kill -9 <PID>
```

Do not restart the writer.

After SIGKILL, `SESSION.json` normally remains `"status": "running"` because
the clean-stop handler did not execute.

Labels for recovery:

| Method | `--interruption-method` |
|--------|-------------------------|
| `kill -9` | `sigkill` |
| Termux force-stop | `termux-force-stop` |
| Device reboot | `device-reboot` |
| Genuine power interrupt | `power-loss` |
| Other | `other` |

The interruption label is **operator-declared** metadata and is not
independently attested by the harness.

## Recovery

```bash
python tools/physical_durability.py recover \
  ./runtime-durability-physical \
  --interruption-method sigkill
```

Recovery:

1. Loads the saved ledger
2. Reconstructs `FileLedger`
3. Verifies the complete hash chain
4. Records whether reload succeeded
5. Records recovered count when successful
6. Records exact reload failure when recovery fails
7. Records ledger byte size and SHA-256
8. Writes `RECOVERY.json`

## Evidence preservation

Preserve:

- `SESSION.json`
- `durability_ledger.jsonl`
- `RECOVERY.json`
- checkout SHA and environment notes

Do not edit generated JSON before recording the experiment.

## Interpretation

### `recovered_ok: true`

Supports only: under the tested interruption method, workload, path, device
environment, and checkout, the persisted ledger reloaded and its chain verified.

Does **not** establish general power-loss durability, FS journal guarantees,
storage-controller guarantees, concurrent-writer safety, or arbitrary FS robustness.

### `recovered_ok: false`

Supports only: under the tested method and environment, persisted state was
rejected during reload. Preserve the exception and ledger SHA-256.

A failed reload is not automatically data loss; it may be intended fail-closed behavior.

## Suggested repetition matrix

| Interruption | Suggested runs |
|--------------|----------------|
| SIGKILL | 5 |
| Termux force-stop | 5 |
| Device reboot | 3 |
| Actual power interruption | Only if safely controlled |

Record every run independently. Do not pool success/failure into one claim
without individual evidence.

## Relationship to Stage 1

Single writer supported. Concurrent writers remain unsupported. This experiment
does not change that boundary.

## Claim boundary

Physical interruption may strengthen the **specific interruption class** measured.
It does not authorize a broader durability claim from one surviving run.
Promotion requires fresh evidence tied to the exact claim.
