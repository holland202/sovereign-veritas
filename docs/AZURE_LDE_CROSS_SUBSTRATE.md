# Cross-substrate research note — Azure / LDE (2026-10-07)

**Status: EXPERIMENTAL; cross-substrate reproduction NOT VALIDATED. This is not a Sovereign Veritas Azure test.**

This note links related Local Discovery Engine (LDE-2G) research for traceability, without incorporating its findings into the SV Gate's validation claims.

## Sources
- Source: https://codeberg.org/badatchess/local-discovery-engine
- Reported tested source commit: `f979705293849de48e4b40aa8988c046fa5871da`
- Published dataset: https://huggingface.co/datasets/holland202/lde-cross-substrate-research
- Environments: Azure AMD EPYC x86_64 and Samsung Galaxy S25 Ultra ARM64/Termux.

## Reported observations (not independently audited here)
- LDE-2G confirmatory trial: 60 seeds; 49/60 maximal-discrimination selections (81.6667%); 11 non-maximal (seeds 7, 8, 9, 17, 20, 28, 30, 34, 44, 54, 59).
- The confirmatory stdout was reported byte-identical across Azure and S25 (SHA-256 beginning `966108`). This is an output comparison, not a validated cross-substrate execution.
- Azure evidence contains a direct-invocation `ModuleNotFoundError` and `exit_code.txt=1`, alongside a separate `confirmatory_exit_code.txt=0`. These cannot be silently collapsed into a successful end-to-end run.
- An exploratory split-RNG run reportedly gave 46/60; this is exploratory, not a replacement for the registered confirmatory result.
- The LDE-2G information-priority hypothesis was **not supported** by the 49/60 confirmatory outcome on this trial set.

## Verification boundary and next work
The result does not establish statistical generalization, correct information-gain estimation, independent replication of the complete workflow, Azure failure root cause, or any SV authorization/ledger correctness on Azure. Reconcile the conflicting exit-code artifacts and validate commands, environments, source hashes, and full raw logs before upgrading the cross-substrate claim. Preserve all failures and negative results.

**Provenance:** documentation compiled from the project owner's prior experiment records; this change did not rerun the experiment or independently fetch and audit the dataset. AI-assisted drafting; human review required.
