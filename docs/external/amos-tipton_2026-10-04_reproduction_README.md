# Amos Tipton — two reproduction bundles (2026-10-04)

> **Reproduction run by Amos Tipton, Founder & Chief Architect of HYBRID WAYSS (AI-assisted using OpenAI tools).**
>
> This is a reproduction of the referenced implementation. It is **not** an endorsement, **not** a
> certification and **not** an independent implementation. The reports say the same: they are a separate
> execution of mostly author-supplied tests.
>
> Amos Tipton gave permission on 2026-10-04, in a message to Chad Holland, to publish these two bundles
> unedited under `docs/external/`, with their original checksums and commit references preserved. The
> permission covers these two bundles only.

## What is here

| Directory | Commit tested | Files | Contents |
|---|---|---|---|
| [`amos-tipton_2026-10-04_reproduction_d37779c/`](amos-tipton_2026-10-04_reproduction_d37779c/) | `d37779c504f8b03c9e8429eeeb07aeb5576301f9` | 24 (23 listed + the manifest) | Bounded reproduction: signed packages, test suite, kernel and verifier conformance, contract mutants, verifier-guard mutants, attack harness, corruption, corridor, execution boundary, four extra CLI checks |
| [`amos-tipton_2026-10-04_reproduction_2c825b8/`](amos-tipton_2026-10-04_reproduction_2c825b8/) | `2c825b8b02083bf3373b9bd857f699507029b865` | 19 (18 listed + the manifest) | Follow-up at the merge of PR #35: packages, test suite, conformance, attack harness, signature-guard mutant, source diff against `d37779c` |

Files are exactly as received. Each bundle carries its own checksum list (`SHA256SUMS.json` and
`bundle-sha256.json`); every entry matched when the bundles were added here.

SHA-256 of the two zip files as received (the zips themselves are not stored):

- d37779c bundle: `15ad5008afc147a6b1666930f839757f3c6245bf8e5424e2374ac6686803b11c`
- 2c825b8 bundle: `9ce08358e453ceaf0a1cce6efa1ee7e655e74b89166da86eb9563cbdf3275f61`

`run_checks.py` (in the second bundle) is the reviewer's orchestration script. Its absolute paths are local to
the reviewer's environment, and it is stored as text, not run by anything in this repository.

## What this project checked and found (not part of the bundles)

Written by Chad Holland with Claude (Opus 5.5) on 2026-10-04. The bundles above were not edited.

- All 43 file hashes recorded in the bundles' provenance files match this repository at the stated commits.
- Results agree with this project's own runs: the pinned package `sv_package_7548237bceca.json` is `CONSISTENT`,
  `LATEST_WITNESSED(6)`, `SIGNED:holland202`; the other seven fail freshness (five `STALE`, two `NOT_WITNESSED`);
  conformance digest `44823d0f…0628`; attack harness 14 of 14 `HELD`; verifier guards 27 of 27 killed.
- "The seven negative controls" in the reports are the seven older published packages, not attack cases A1–A10.

## Findings from the reproduction

1. **The README's "0 of 17,157 truncations" row cannot be reproduced from this repository.** It was measured on
   a package kept only on the S25. The reviewer ran the same tool on a published package: 0 of 17,131 strict
   prefixes and 0 of 200 bit flips accepted. The README row now says where the result was measured.
2. **The corruption tool does not exercise the hardened parser or the signature and witness path.** It calls
   `verify()` directly with ordinary `json.loads`. The README row now says so.
3. **Two skipped tests in the first run** (git-checkout-only tests) were the mutants-tool defect fixed in PR #35.
   The second run, at `2c825b8`, shows no skips: an outside confirmation of that fix.
4. **Two published, signed packages took an action under ALLOW while two inputs were DEFAULTED**
   (`sv_package_3a9dbf53aee6.json` and `sv_package_ed144097dece.json`: `compute_budget=DEFAULTED`,
   `power_status=DEFAULTED`, note written). This is the gap tested in PR #36 (a DEFAULTED tag never changes the
   Gate's decision), now visible in real packages. Whether DEFAULTED should block ALLOW (PR-2) is not decided.

## Limits stated by the reviewer

No new independent Gate implementation; the Go port was not run; no phone hardware; no all-platform run; no
exhaustive adversarial search; no key-custody assessment; the second bundle did not re-run the full 27-guard
mutation experiment, the corruption sweep, the corridor or the execution-boundary probe. Freshness is relative to
the witness log at the stated commit, and signature validity does not establish the real-world identity or custody
of the key.
