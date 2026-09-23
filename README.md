# Sovereign Veritas

Sovereign Veritas is the runtime and governance layer for evidence-first autonomous systems.

It is intentionally small and tool-oriented. The goal is not to replace domain models or scientific verification packages, but to provide a deterministic contract for:

- local evidence capture
- claim/prediction provenance
- capability enforcement
- resource-aware runtime gating
- decision records that separate observation from action
- auditable operation on edge devices

## Architecture

The project is organized around a few core ideas:

1. Models produce observations, not proof.
2. Verification is a separate state from prediction.
3. Actions require a declared capability and evidence sufficiency.
4. The runtime may defer or refuse when the evidence is incomplete or the environment is unsafe.
5. Decisions are append-only evidence, not informal status messages.

## Status

This repository is the v0.1 kernel for Sovereign Veritas. It establishes the first hard contract:

- evidence must be recorded;
- verification must be explicit;
- action requires declared capability and required evidence;
- the runtime controls whether the system is currently permitted to act;
- decisions are deterministic and auditable.
