# P-001 — one finite build, done by two AIs reviewing each other, finished by Chad

**Status:** OPEN, phase 1 (scope). Started 2026-10-09. Chad Holland directed that Claude and ChatGPT collaborate through GitHub notes on every phase of one real build: what to build, how, building it, and deciding when it is done. This charter was drafted by Claude (Opus 5.5). It is itself open to ChatGPT's challenge in phase 1, and Chad has not reviewed it line by line.

## Why this shape
A two-model exchange is worth its cost only if each round changes code or a result, and only if it ends. So: one project, four phases, a round limit on every phase, a written finish line, and a tally that shows whether the collaboration is paying off.

## Roles (so neither model grades its own work)
| | ChatGPT | Claude | Chad |
|---|---|---|---|
| Scope | contests the proposal | proposes | picks if they disagree |
| Acceptance ("what done means") | **writes it** | critiques it once | **freezes it** |
| Implementation plan | critiques it once | writes it | — |
| Code | reviews the diff, tries to break it | **writes it**, turns the frozen acceptance into tests verbatim | — |
| Done | files a DONE or NOT-DONE note | files a DONE or NOT-DONE note | **merges, or not** |

CI is the referee for anything a test can decide. Agreement between the two models is never evidence.

## Phases
1. **Scope:** what we build. Claude proposes (notes/…_claude_001.md). ChatGPT accepts, amends or replaces it. **At most 2 rounds**, then Chad picks. Output: `SCOPE.md`, frozen (commit SHA recorded here).
2. **Design:** how we build it and how we'll know it works. ChatGPT writes `ACCEPTANCE.md`: for each item, the exact cases, expected outcomes and at least one anti-vacuity case (something the change must still allow). Claude writes `PLAN.md`. Each critiques the other **once**. Chad freezes `ACCEPTANCE.md` **before any code** (SHA recorded here).
3. **Build:** Claude implements on this branch. The frozen acceptance cases become tests exactly as written. Frozen cases are never edited; new attacks are **added**. ChatGPT reviews the diff and tries to break it. **At most 2 review rounds per item**; anything still disputed becomes `STOPPED_CONTESTED` and goes to Chad.
4. **Done:** an item is DONE when every frozen acceptance test passes in CI, the existing suite is green, and any change to the Gate contract digest is recorded. Each model files one DONE or NOT-DONE note with its reasons. Chad merges, or doesn't. Then a tagged release with a release note that says what is claimed and what isn't, **and the project closes**.

**Workflow states** (per item): `OPEN → EVIDENCE_IN → SETTLED`, or `CONTESTED → STOPPED_CONTESTED` (terminal, Chad decides). **Outcome flag**, separate: `SUPPORTED / REFUTED / INCONCLUSIVE`.

## Rules
- New ideas go to `BACKLOG.md`, never into this project. Scope changes only by Chad.
- Notes are additive: `notes/YYYY-MM-DD_<model>_NNN.md`. Never edit another model's note; correct it in a new one.
- Every claim about the code cites a file and line, or a command and its output. "I read it" and "I ran it" are kept distinct.
- Stop rule: if three consecutive rounds change no code, test or result, the project pauses and Chad decides whether to continue.
- The veritas-origin discrimination precheck (approved 2026-10-09) is **parked until P-001 closes** unless Chad says otherwise, so there is one project at a time.

## Tally (filled in each round)
| Round | Phase | By | What it changed (code / test / result / nothing) | Chad's minutes (Chad fills) |
|---|---|---|---|---|
| 1 | Scope | Claude | Charter, facts and scope proposal (no code) | |

## Frozen artefacts
- SCOPE.md: _not yet frozen_
- ACCEPTANCE.md: _not yet frozen_
