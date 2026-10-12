# Contributing

This repository is a research prototype. Contributions that **challenge**, **reproduce**, or **independently implement** the design are more valuable than praise or cosmetic polish.

**Looking for AI agent governance / fail-closed action authorization examples?** Start with [README.md](README.md) for the prototype scope, [CONTRACT.md](CONTRACT.md) for the rules, [STATUS.md](STATUS.md) for unresolved findings, and the [discoverability audit](docs/DISCOVERABILITY_AUDIT_2026-10-11.md) for documentation-only changes. Please distinguish independent verification of a recorded decision from source authenticity or proof of external execution.

## What we value

- **Reproducibility over praise.** Report what you ran, on which commit/OS/Python version, and what it printed.
- **Failures and negative results.** A careful “it broke” or “I could not reproduce this claim” is a first-class contribution.
- **Honest epistemic labels.** State clearly whether a result is *measured*, *reproduced*, *inferred*, or *hypothetical*.
- **Preservation of distinctions.** `CONSISTENT` is not authenticity, not freshness, and not truth. Do not blur those terms in docs or code comments.
- **Fail-closed behavior.** Do not weaken tests or remove refusals to make something pass unless you are proposing a deliberate, documented specification change.

## Independent implementations

Independent implementations of [CONTRACT.md](CONTRACT.md) and its 4690 test vectors are explicitly welcome. Use:

```bash
python tools/gate_contract.py --check-command <your program>
```

A second implementation by someone other than the original author is among the most useful outcomes this repository can have.

## Changing the Gate contract

If you change Gate rules or decision semantics:

1. Update [CONTRACT.md](CONTRACT.md).
2. Update or extend the contract vectors under `contract/`.
3. Ensure the existing and new tests still express the intended fail-closed behavior.
4. Do not silently weaken tests to force a green suite.

## What not to do

- Do not claim production readiness without evidence.
- Do not treat a `CONSISTENT` verdict as proof that the recorded world state is true.
- Do not add production deployment guidance or security guarantees that the prototype does not support.
- Do not use `git add -A` or broad cleanups when contributing community or documentation files; keep changes focused.

## Practical steps

1. Fork and clone.
2. Install and run the suite: `python -m pip install -e ".[test]"` then `python -m pytest -q`.
3. Open an issue for findings (bugs, contract mismatches, reproduction results) before large PRs when possible.
4. Keep PRs focused. Prefer evidence and failing cases over narrative.

Thank you for testing the claims rather than the story.
