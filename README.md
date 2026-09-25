# Sovereign Veritas

Sovereign Veritas is the runtime and governance layer for evidence-first
autonomous systems.

It is intentionally small and tool-oriented. The goal is not to replace domain
models or scientific verification packages, but to provide a deterministic
contract for:

- local evidence capture
- claim/prediction provenance
- capability enforcement (including hierarchy and quality bounds)
- resource-aware runtime gating
- decision records that separate observation from action
- auditable operation on edge devices
- adversarial challenge that cannot authorize actions

## Core ideas

1. Models produce observations, not proof.
2. Verification is a separate state from prediction.
3. Actions require a declared capability and evidence sufficiency.
4. The runtime may defer or refuse when evidence is incomplete or the environment is unsafe.
5. Decisions are append-only evidence, not informal status messages.
6. The adversary generates challenges and counterevidence; it never authorizes.
7. Authorization changes are ledgered **before** the registry mutates.

## Quick start

```bash
python -m pip install -e .
pytest -q
```

## Status

See [STATUS.md](STATUS.md) for what has actually been measured.

This repository is a **v0.1.1** kernel. Claims in STATUS.md are limited to
passing tests at a recorded SHA. Broader trust or autonomy claims are out of
scope until supported by further evidence.

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
