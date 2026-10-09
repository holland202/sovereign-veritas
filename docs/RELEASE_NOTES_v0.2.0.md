# Sovereign Veritas v0.2.0: signed, contract-bound evidence packages

**EXPERIMENTAL research prototype. NOT PRODUCTION-READY. NOT INDEPENDENTLY SECURITY-VALIDATED.**

## What changed (P-001 W1, W2, A08)
- **New packages are `sv.package/1`.** They carry `contract: {id: "sv.gate/0", conformance_digest: 44823d0f…0628}` inside the canonical, signed body. `tools/verify_package.py` compares those fields with its own locally pinned `TRUSTED_CONTRACTS`, never with the package's claim, and prints a `CONTRACT …` line before `VERDICT`.
- **`tools/consumer.py accept` requires `--signature`, `--allowed-signers` and `--identity`.** A missing option is an argparse usage error (exit 2), so there is no unsigned mode. Only `sv.package/1` is accepted. The state file is written to a temporary file in the same directory and moved into place with `os.replace`; that is atomic replacement, not durability against power loss.
- **Legacy `sv.package/0` files are unchanged.** They are byte-identical to `tests/p001/legacy_manifest_709da9e.sha256`. Inspect them with `verify_package.py --legacy`, which reports `CONTRACT LEGACY_UNBOUND`. The consumer refuses them.
- **Gate decisions are unchanged.** The kernel and the verifier match all 4,690 vectors (digest `44823d0f…0628`).
- **The version is now consistent.** `pyproject.toml` and `__init__.py` both say 0.2.0; before this they said 0.1.0 and 0.1.1.

## Compatibility (breaking)
- Scripts that check `schema == "sv.package/0"` need updating.
- Scripts that call `consumer.py` without the signature options will now get exit 2.
- `tools/witness.py append` witnesses only bound v1 packages.

## Evidence
- Frozen acceptance: `coordination/p001/ACCEPTANCE.md` @ `1c16e66` (sha256 `dc54e8c1…b4d28d`).
- Case-by-case results: [docs/P001_ACCEPTANCE_REPORT.md](P001_ACCEPTANCE_REPORT.md). A01–A08 and B01–B08 pass. `tools/p001_mutants.py` kills all three planted mutants: skipping the signature check, trusting the package's own contract fields, and refusing everything.
- The signed workflow and its limits: [docs/P001_SIGNED_WORKFLOW.md](P001_SIGNED_WORKFLOW.md).
- The CI matrix covers Linux x86/arm, macOS and Windows on Python 3.10, 3.12 and 3.14.

## Negative findings and known limitations (kept, not fixed)
- **W3:** an honest all-DEFAULTED package still gets ALLOW (PR-1, `docs/PR1_RESULTS.md`).
- **PV-1 (#54):** a DEFAULTED→OPERATOR relabel verifies CONSISTENT, and verifies SIGNED when signed. No field names who declared a value.
- **AMB-1 (#55):** the 4,690 vectors underdetermine the Gate. The worst impostor gives a false ALLOW on 1,235 of 10,000 inputs. The 800 added vectors are not adopted.
- **XB-1:** the race (X4) and effect-without-record (X5) cases are still open.
- **EO-1:** the record reports the workflow's account of an action, not its effect.
- **Consumers:** two concurrent consumers sharing one state file are not serialised. A consumer on first use has no anchor.
- **Signatures:** a signature proves who signed these bytes. It does not prove the content is true or fresh, and a fully consistent rewrite still verifies.
- **Not established:** a run on the S25 for this release, independent reproduction, and an outside security review. Nothing here supports a FIPS or MFA claim.

## Also merged: #61 VK-1, a negative hardware finding outside the SV kernel (`tools/accel/vk1/`)
- **What it shows:** llama.cpp 0.6.0 Vulkan on the S25 Ultra's Adreno 830 gives **wrong decode output** for Q4_0 and Q4_K_M. The Q4_K mat-vec path aborts from ngl 2 upward. Vulkan inference with correct output is **NOT DEMONSTRATED**.
- **Limits kept:**
  - The perplexity instrument failed its own control (P2a refuted), so every perplexity cell is void.
  - The registration was committed after the run; its sha256 was logged on the device first.
  - The TinyLlama CPU reference is degenerate (an empty generation).
- **Correction to the P-001 close-out:** the close-out recommended closing #61 as "raw evidence unavailable", and that was wrong. The raw `device_run/results.jsonl`, preflights and per-cell logs had been committed to the PR on 2026-10-06 (`11bdad2`). Claude and ChatGPT both relied on the PR description's unchecked box and on `RESULTS_VK1.md`'s "still on the device" line, without checking the files. Re-checked 2026-10-09: `vk1_probe.py --report` run on the committed `device_run/` re-derives the pinned digest `e464c944…f8055a4` (`RECORDED match`).
- #61 was merged rather than closed. It is kept as a negative finding: it changes nothing in the Gate, the verifier or the consumer.

## Closed without merging (reasons on each PR)
- **#60 SM-1:** a registration that was never run.
- **#62:** overlaps #34 and concerns a different project (LDE).

## Provenance
Code, tests and documents were written by Claude (Opus 5.5). ChatGPT wrote the frozen acceptance criteria and reviewed the source without running it. Chad Holland directed the work, approved the scope, the acceptance criteria and this release plan, and reviewed the outcome summaries rather than every line. Chad holds responsibility for the release.
