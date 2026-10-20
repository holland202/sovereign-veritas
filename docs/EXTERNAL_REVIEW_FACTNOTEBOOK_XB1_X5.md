# External research record: FactNotebook XB-1 / X5 reconstruction

**Status:** Independent external reconstruction of published evidence; not experimental replication, certification, security validation, or endorsement.  
**Original author:** Patrick Juvet Etoua  
**Originating project:** FactNotebook  
**Finding:** FN-CHAD-XB1-X5-001  
**Reconstruction ID:** FN-9e087ff81fe3759f  
**Canonical publication:** https://github.com/factnotebook/public-reconstructions/tree/main/FN-CHAD-XB1-X5-001

## Scope and finding

FactNotebook analyzed the public Sovereign Veritas XB-1 case X5 preregistration, results, and reference probe, pinned to source commit `fd5cac90587ba65d713b652ac743a8f240860aaa`. It did not independently run the probe or inspect a durable ledger.

The published synthetic experiment reports `effects=1`, `records=0`, `errors=1`: a counting executor reports an effect and the evidence sink fails. FactNotebook separates the experiment's reported behavior from the ledger's preserved evidence and from real-world effects.

Across seven propositions, the reconstruction classifies the reported synthetic-effect/recording divergence as **ESTABLISHED relative to published artifacts**; the inference that zero records implies zero *reported synthetic effects* and the claim that the effect was recorded as **CONTRADICTED** within the published experiment; and ledger-based establishment of authorization, execution, or real-world non-occurrence, and establishment of a real-world effect, as **CANNOT ESTABLISH**.

## Limitations and attribution

This is one synthetic case with a counting stub, not evidence of a physical-world effect. The source experiment lacks a dedicated cryptographic evidence manifest binding the result to the reference code. FactNotebook did not independently re-execute the probe, inspect the ledger, or release its internal reconstruction engine as part of this publication. The reconstruction is independent analytical scrutiny of *our public artifacts*, not an independent experimental reproduction or a finding that Sovereign Veritas is secure.

FactNotebook's original document, detailed seven propositions, provenance, identifiers, and limitations remain authoritative at the canonical publication above. This page is a separately authored project acknowledgment and summary; it does not modify or adopt FactNotebook's work as Sovereign Veritas's own findings.

## Original public sources

- [XB-1 preregistration](https://github.com/holland202/sovereign-veritas/blob/fd5cac90587ba65d713b652ac743a8f240860aaa/docs/EXECUTION_BOUNDARY_PREREG.md)
- [XB-1 results](https://github.com/holland202/sovereign-veritas/blob/fd5cac90587ba65d713b652ac743a8f240860aaa/docs/EXECUTION_BOUNDARY_RESULTS.md)
- [Reference probe](https://github.com/holland202/sovereign-veritas/blob/fd5cac90587ba65d713b652ac743a8f240860aaa/tools/execution_boundary_probe.py)

**Research disposition:** X5's execution/evidence divergence remains an open technical issue. This acknowledgment does not close it or assert that any proposed remedy has been validated.
