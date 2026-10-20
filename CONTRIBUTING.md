# Contributing

This repository is a research prototype. Contributions that **challenge**, **reproduce**, or **independently implement** the design are more valuable than praise or cosmetic polish.

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

## Licensing of contributions

By opening a pull request, or otherwise submitting code or documentation for inclusion, you agree that your
contribution is licensed under the MIT License in [`LICENSE`](LICENSE), the same terms as the rest of the project,
and you confirm that you have the right to submit it under those terms.

If you want something kept here **only as a record** and not under MIT (a review, a report, test cases you
want to keep control of), say so in the issue or pull request. It will be stored under `docs/external/` with its
terms written down; see [`docs/external/README.md`](docs/external/README.md).

## Practical steps

1. Fork and clone.
2. Install and run the suite: `python -m pip install -e ".[test]"` then `python -m pytest -q`.
3. Open an issue for findings (bugs, contract mismatches, reproduction results) before large PRs when possible.
4. Keep PRs focused. Prefer evidence and failing cases over narrative.

Thank you for testing the claims rather than the story.

## License and independent review permissions

The repository remains **MIT-licensed** and maintenance-only; see [LICENSING.md](LICENSING.md). Code proposed for incorporation should be contributed only by someone entitled to offer it under the existing MIT terms, with any required third-party notices.

For an independently authored review, record the author's publication permission and approved attribution. Publication consent does not automatically confer copyright ownership, unrelated republication rights, or an endorsement. No blanket copyright assignment or contributor license agreement is introduced here. Any separate paid evaluation, confidential materials or non-public testing scope requires explicit arrangements; none modifies the rights previously granted under MIT.

**Provenance (2026-10-19):** This explanatory section was prepared with ChatGPT (OpenAI, GPT-6) at Chad Holland's direction; legal review not performed.
