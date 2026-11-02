# SEC-004 results: SECURITY_FAIL (run 2026-10-11, recorded 2026-11-02)

## What went wrong, first

- **The registered probe found the predicted security failure, and that result was not written down for 22 days.** The SEC-004 workflow ran once on 2026-10-11 (run 38160250976, commit `8338e83`) and failed with `GATE=SECURITY_FAIL`. The research log and the handoff for that day recorded only "SEC-004 registered-release-race CI failed". The verdict itself was never recorded. This file fixes that omission. Recording a failure late is itself a process failure, and it is kept here.
- **The defect is probably still present.** The probed module `sovereign_veritas/idempotency.py` is the same blob (`071fc3fe…`) on `main` as on 2026-11-02, so nothing has changed it since the run.

## Raw evidence

The artifact `sec004-first-registered-run` (id 11710565841), downloaded unchanged, is in `sec004_evidence/`. Its `SHA256SUMS` verifies. The run used Python 3.12.3 on Linux x86_64 (GitHub's runner). The harness `exit_code.txt` is `0`, which per the registration means "the harness ran and scored". Excerpt from `run.log`:

```
"C2": { ... "new_token": "25ddd67d026b26ab", "old_token": "09421816fc20967e",
        "new_token_survives": false, "p2_old_token_replaced_new": true,
        "p3_no_stale_late_event": true, "ordered": true, "pause_count": 1, ... }
"predictions": {"P0": true, "P1": true, "P2": true, "P3": true, "P4": true, "P5": true}
"verdict": "SECURITY_FAIL"
GATE=SECURITY_FAIL
```

## Predictions (`SEC004_PREREG.md`, frozen at `7bbab7c`)

| ID | Prediction | Result |
|---|---|---|
| P0 | C0 keeps the new token; one late event | HELD |
| P1 | C1 likewise, read from a fresh store object | HELD |
| P2 | **expected security failure:** under C2 the old completion overwrites the new active reservation | **HELD: the new token did not survive** |
| P3 | the stale completion is not logged as `late_complete` | HELD |
| P4 | C3 refuses release and keeps the record | HELD |
| P5 | anti-vacuity: two distinguishable snapshots in C2, no early write | HELD |

## What this shows and does not show

- **Shows (implementation, one forced local schedule):** a completion that checked the old token *before* `release()` and a fresh `reserve()` can write *after* them. It replaces the new holder's reservation with the old, completed one, and no late event is logged. Reservation ownership is not isolated across that window.
- **Does not show:**
  - that a real external action ran twice. The registration says this explicitly;
  - how likely the schedule is in practice;
  - anything on other substrates (`cross_substrate_verified: false`);
  - independent validation (`independent_validation: false`).

## Open

- **A fix and its test**, a separate change for the owner to decide on. The obvious direction is to re-check the token under the same lock and in the same read-modify-write that commits the completion (compare-and-swap). A registered re-run of this probe would then be expected to flip P2.
- Re-run the probe on current `main`, to confirm that the defect is still present rather than inferring it from the unchanged blob.

Provenance: probe and registration as committed on 2026-10-11 (see the PR history). This results file was written by Claude (Anthropic, Opus 5.5) from the retained artifact, at Chad Holland's direction (2026-11-02, direction only) → human validation: not performed → human responsibility: Chad Holland.
