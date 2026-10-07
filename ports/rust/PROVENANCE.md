# Provenance of `ports/rust`

Written 2026-10-07 by a Claude (Opus 5.5) subagent given **only** `CONTRACT.md` and `contract/gate_vectors.jsonl` in an
otherwise empty directory, with instructions not to read this repository's code (`sovereign_veritas/`,
`tools/verify_package.py`, `ports/go`) or search the web for it. Isolation was by instruction and by directory, not
enforced by the sandbox. No crates: JSON parser, Python-compatible number formatting and SHA-256 are hand-written.

What this is evidence of, and what not:

- **Separation of context**, not independence of judgment: same vendor and model family as the session that hardened the
  kernel. It is not the "implementation by someone other than the author" that CONTRACT.md asks for.
- The implementer saw the expected outputs of the first one or two vectors before its first run (its own record), and
  matched 4690 of 4690 on that first run with no fixes. `python tools/gate_contract.py --check-command
  ports/rust/target/release/rust_gate` prints the contract digest (`44823d0f…0628`), reproduced in the author session.
- Its `NOTES.md` lists 13 ambiguities in CONTRACT.md and a coverage gap in the vectors (vocabulary words `high`,
  `critical`, `unsafe`, `low` appear in no vector). Both are recorded in `docs/DIFFERENTIAL_RESULTS.md`.

Build: `cd ports/rust && cargo build --release --offline`.
