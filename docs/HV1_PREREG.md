# HV-1 — hidden world, visible evidence: does the Gate's input survive copies, replays, staleness and common-mode spoofing? Registration

**Status:** REGISTERED, nothing built or run. Committed and pushed before `tools/hv1_sim.py` exists. Baseline: the commit
that adds this file.

**Provenance.** Designed by Claude (Opus 5.5) at Chad Holland's direction; the same model builds, runs and judges:
**self-tested**. It is a **simulation**: every result is MODEL_DEPENDENT, and the domain names are illustrations, not
validated models of those domains. Container only.

## Why

The Gate (`sovereign_veritas/decision.py`) decides on what it is given:
- a verification status;
- `required_evidence` attestations, each of which must be the boolean `True`;
- an evidence-quality number.

It cannot see the world. The weak point in any deployment is the **adapter** that turns observations into those inputs.
HV-1 separates two planes:
- a **hidden plane** (true state, read only by the scorer);
- a **visible plane** (sensor readings with provenance, age and signatures, read only by the adapter).

It runs the real Gate on what the adapter produces, under the default evidence ladder (fresh, stale, unavailable,
contradictory, derived from the same source, replayed), a common-mode spoof and an adaptive attacker. Run records use
sv-lab-vk2's lab substrate format: `run.json` with a semantics block in which the agent may not assign truth, an
`events.jsonl` log, and an `artifact_manifest.json`.

## Model

- **Domains**, each a hidden scalar with a safety limit and three sensors. The values are illustrative.
  - robot geofence: distance from the fence centre, safe if ≤ 100 m. Sensors: GNSS-A and GNSS-B (same modality),
    odometry (another modality, drifts).
  - ICS pressure: safe if < 800 kPa. Sensors: transmitter A and transmitter B (same modality), a historian (a copy of A).
  - banking: available balance minus the transfer, safe if ≥ 0. Sensors: core ledger, a cache (a copy of the ledger,
    stale-prone), a reconciliation feed (another modality).
  - legal release: privilege score, safe to release if < 0.5. Sensors: classifier A, docket metadata (a copy of A),
    attorney review (another modality, often unavailable).
- **Readings** carry a value, a claimed source, an age, the modality, and a stand-in HMAC signature per source key. A copy
  carries its upstream source's key and signature.
- **Conditions** (ladder plus attacks):
  - `fresh`;
  - `stale` (the reading predates a change in the hidden state);
  - `unavailable` (one sensor missing);
  - `contradictory` (one independent sensor faulty);
  - `copy_spoof` (the attacker spoofs one source and its copy agrees);
  - `replay` (an old, validly signed, safe-looking reading of an independent source is replayed);
  - `common_mode` (both same-modality sensors spoofed to the same safe-looking value);
  - `adaptive` (each trial the attacker picks whichever single manipulation would have made this adapter ALLOW).
- **Adapters** (the system under test, each feeding the real Gate). The capability requires `independent_corroboration`
  with `min_evidence_quality` 0.8.
  - `naive`: every available reading counts; corroboration means at least 2 readings agree on "safe" within margin.
  - `provenance`: counts only distinct, validly signed source keys with age ≤ the freshness bound; disagreement among
    them sets verification to INSUFFICIENT_EVIDENCE.
  - `diverse`: as `provenance`, and corroboration must also span two modalities.
  - `split_reasons`: as `diverse`, but each property (fresh, independent, consistent, diverse) is its own
    `required_evidence` attestation instead of one, so the Gate's DEFER reasons name which one failed.
- **Scoring** on the hidden plane:
  - false ALLOW = ALLOW while unsafe;
  - false hold = not ALLOW while safe (the liveness cost).

  Rates have Clopper–Pearson 95% intervals. 2000 trials per domain, condition and adapter, seeded.

## Predictions

| ID | Prediction | Refuted if |
|---|---|---|
| H1 | `fresh`: false ALLOW = 0 for every adapter (noise is bounded below the safety margin) | any false ALLOW |
| H2 | `stale`, `replay`, `copy_spoof`: `naive` has false ALLOW > 0 under each; `provenance` has 0 under each | naive 0 under any, or provenance > 0 under any |
| H3 | `common_mode`: `provenance` false ALLOW > 0 (two keys, one physical cause); `diverse` = 0 | provenance 0, or diverse > 0 |
| H4 | the cost of diversity: `diverse`'s false-hold rate under `fresh` is higher than `provenance`'s (odometry drift and unavailable reviews) | not higher |
| H5 | `adaptive`: false ALLOW `naive` > `provenance` > `diverse` = 0 | the order fails, or diverse > 0 |
| H6 | routing information: when `diverse` DEFERs under `stale` versus `contradictory`, the Gate's reasons are identical (both arrive as one collapsed reason). Under `split_reasons` they differ in 100% of DEFERs | `diverse` reasons distinguish them, or `split_reasons` fails to in any DEFER |
| H7 | anti-vacuity: with the safety margin set to 0 (`--sabotage`), H1 is refuted (noise produces false ALLOWs) | H1 still holds under sabotage |

## What a result leads to

- H2/H3 held: DOCUMENT in the threat model. Corroboration has to be counted by authenticated provenance and modality,
  not by number of readings. An adapter contract for `independent_corroboration` is EXPERIMENT FIRST.
- H6 held: propose (EXPERIMENT FIRST, sv.gate/1) one `required_evidence` attestation per evidence property, so the
  reasons carry routing information.

## Left unrun

- Real sensors, or any physical model beyond a scalar.
- An attacker who holds a source key.
- Correlated faults beyond one modality.
- Timing attacks on the freshness bound.
- Clock trust: the adapter's clock is trusted here.
