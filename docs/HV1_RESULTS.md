# HV-1 results: 3 of 7 as registered. Provenance and modality diversity did not reach zero false ALLOWs (H2, H3, H5 refuted, one boundary mechanism); the Gate's reasons already tell stale from contradictory (H6 refuted)

Registration: `docs/HV1_PREREG.md`, commit `378332a`, pushed before `tools/hv1_sim.py` existed. Linux container (x86_64,
Python 3.13.16). Designed, built, run and judged by Claude (Opus 5.5): **self-tested**. Chad Holland directed the work. He
has not reviewed this text or the code line by line. **A simulation:** every number below is MODEL_DEPENDENT. The domain
names are illustrations, not validated models of those domains.

Raw outputs: `results/hv1/hv1_registered.txt` (exit 1), `results/hv1/hv1_sabotage.txt` (exit 0), and the run records in
the sv-lab-vk2 format under `results/hv1/hv1-20261007-2000-*/`. The trials behind each outcome come from
`tools/hv1_trace.py`, written after the run. It re-runs the registered run through wrappers and checks every cell's
decision digest against the registered `events.jsonl`: `registered run re-observed: 128 of 128 cells have the registered
digest` (`results/hv1/hv1_trace.txt`).

## Failures and limits (first)

1. **H2 REFUTED.** `provenance` should have had 0 false ALLOWs under `stale`, `replay` and `copy_spoof`. Under
   `copy_spoof` it had `1/8000 [0.0000, 0.0007]`, robot domain. The `naive` clause held.
2. **H3 REFUTED.** `diverse` should have had 0 false ALLOWs under `common_mode`. It had `4/8000 [0.0001, 0.0013]`, all
   robot. The `provenance` clause held: `2108/8000 [0.2539, 0.2733]`.
3. **H5 REFUTED.** `diverse` should have had 0 false ALLOWs under `adaptive`. It had `1/8000 [0.0000, 0.0007]`, robot. The
   registered order held: naive `6975` > provenance `2085` > diverse `1`.
4. **One mechanism behind all six refuting trials, observed in the trace.** In every one:
   - the truth was just past the fence, between `100.030` and `101.969` m (limit 100, margin 5);
   - spoofed GNSS read `90.000 -> SAFE`;
   - the honest odometry also read SAFE, with an error between `-5.448` and `-7.415` m, beyond the margin.

   Under `copy_spoof` and `adaptive` the honest GNSS read UNCERTAIN (`101.893`, `101.723`). No adapter counts UNCERTAIN as
   a conflict: `conflict` needs both a SAFE and an UNSAFE vote (`tools/hv1_sim.py:200`). Two keys in two modalities
   agreed on SAFE, so the corroboration rule (`:216`) was met.

   Example, `robot_geofence copy_spoof trial 850`:
   ```
   gnss_a [gnss] 90.000 -> SAFE (spoofed)
   gnss_b [gnss] 101.893 -> UNCERTAIN (honest, error -0.076)
   odometry [odometry] 94.553 -> SAFE (honest, error -7.415)
   adapter: status PASS, attestations {'independent_corroboration': True}, quality 1.0000 -> ALLOW
   ```
5. **The cause is my parameter choice, which my predictions missed.** H1's parenthetical says "noise is bounded below the
   safety margin". When building the simulator, before any run, I set odometry's drift to 6 m. With noise, that is a
   worst-case honest error of `8.000` against a margin of `5`: `robot_geofence odometry 8.000 margin 5 EXCEEDS the
   margin`. Every other sensor stays below its margin. The "= 0" predictions for `provenance` and `diverse` silently
   assumed that no counted sensor's honest error crosses the margin. The refutations are kept. The parameters are not
   changed, and no re-run with other parameters is part of this record.
6. **H6 REFUTED, completely.** The prediction: `diverse`'s DEFER reasons are identical under `stale` and `contradictory`.
   Observed: `diverse: 0.0000 of DEFERs indistinguishable by reasons (stale 8000, contradictory 2679)`. Under `stale`
   there is one reason tuple, `('verification_insufficient_evidence', 'missing_required_evidence:independent_corroboration',
   'evidence_quality_below_threshold:0.0000<0.8000')`. Under `contradictory` there are 5 tuples, and none is shared.
   - **Mechanism.** The Gate's reasons carry more than the attestation name. They also carry:
     - the verification status (`sovereign_veritas/decision.py:64-65`);
     - the quality value to four decimals (`:111-113`).

     Under `stale` the adapter drops every reading for age, so quality is `0.0000`. Under `contradictory` the readings are
     fresh.
   - **This depends on a design choice.** The quality definition (usable distinct keys / expected keys) was fixed in the
     simulator's docstring before the run. Had quality counted readings regardless of age, the tuples could coincide.
     That variant was not run.
   - `split_reasons` told them apart too (`0.0000`), as predicted.
   - The proposal that depended on H6 (one `required_evidence` attestation per property in sv.gate/1) gets **no support
     from HV-1**, and is not proposed on its strength.
7. **H4 held, but for a different reason than registered.** The registration named "odometry drift and unavailable
   reviews". False holds under `fresh`, by domain (trace), `provenance` vs `diverse`:
   - ICS `62/1014` vs `1014/1014`;
   - robot `40/989` vs `50/989`;
   - banking `14/1037` vs `14/1037`;
   - legal `582/997` vs `582/997`.

   ICS has one modality, so `diverse` can never corroborate there. ICS accounts for 952 of the 962-trial difference. The
   cost of diversity here is mostly "a domain without a second modality never acts".
8. **H2's `naive` replay clause held on 3 of 8000 trials, all robot, through the same boundary mechanism.** Trials 261,
   1197 and 1557 each pair a replayed `gnss_b` SAFE with an odometry error of `-5.748`, `-6.065` and `-6.616`, and an
   UNCERTAIN `gnss_a`. In the other three domains, one replayed source never beats `naive`'s majority (0 each). In this
   model, `naive`'s weaknesses are copies and staleness, not single-source replay.
9. **Model limits that the results expose.**
   - In banking and legal, `common_mode` is the same manipulation as `copy_spoof`. Those domain models have no second
     independent sensor of the same modality (`COMMON` is `("ledger",)` and `("classifier",)`).
   - In the adaptive set, `spoof_one` and `copy_spoof` are the same manipulation (`manipulate` treats them alike). The
     adaptive attacker has 3 distinct moves, not 4.
   - Each cell has its own random stream. `adaptive` `diverse` (1) is below `common_mode` `diverse` (4) because they are
     different samples, not because of a contradiction.
   - The rates average over a truth drawn uniformly from the unsafe range. An attacker who strikes only when the truth is
     near the boundary faces a different rate, which was not measured.
10. **Provenance of the run.** `run.json` says `code_commit 378332a`, but `tools/hv1_sim.py` was uncommitted when it
    ran. Its sha256 in `artifact_manifest.json` (`945d7c65…1a046f`) equals that of the file committed with this
    document.

## Outcome

| ID | Prediction | Result |
|---|---|---|
| H1 | `fresh`: false ALLOW 0 for every adapter | **HELD**: `0/3963 [0.0000, 0.0009]` for each of the four |
| H2 | `naive` > 0 under `stale`, `replay` and `copy_spoof`; `provenance` 0 under each | **REFUTED**: `naive` `1664/4003`, `3/8000`, `4980/8000` (held); `provenance` `0/4003`, `0/8000`, **`1/8000`** |
| H3 | `common_mode`: `provenance` > 0, `diverse` 0 | **REFUTED**: `provenance` `2108/8000` (held); `diverse` **`4/8000`** |
| H4 | `fresh`: `diverse` false hold > `provenance`'s | **HELD**: `1660/4037 [0.3960, 0.4266]` > `698/4037 [0.1614, 0.1849]`, mostly through ICS (item 7) |
| H5 | `adaptive`: `naive` > `provenance` > `diverse` = 0 | **REFUTED**: `6975` > `2085` > **`1`** |
| H6 | `diverse` reasons identical under `stale` and `contradictory`; `split_reasons` distinct in 100% of DEFERs | **REFUTED**: `diverse` `0.0000` indistinguishable; `split_reasons` `0.0000` (held) |
| H7 | anti-vacuity: margin 0 refutes H1 | **HELD**: `fresh` false ALLOW `naive 17/3963`, `provenance 7/3963`, `diverse 5/3963`, `split_reasons 5/3963`; `H7: with margin 0, H1 is refuted (as it must be)` |

The registered run prints `VERDICT  2 of 6 as registered (H7 is the --sabotage run)`. With H7: **3 of 7**.

## Observed, not predicted (M9: observations, MODEL_DEPENDENT)

- **A dissenting human review let a spoof through.** Under `legal_release copy_spoof`, `naive` ALLOWed in every trial
  with the attorney reading present and in none without it: `present: 979/979 ALLOW (attorney said {'UNSAFE': 827,
  'UNCERTAIN': 152})   absent: 0/1021 ALLOW`. The cause is `naive`'s quality, available readings / sensors. A third
  reading, even a dissenting one, lifts it from 2/3 to 3/3, past the 0.8 threshold. The spoofed classifier and its copy
  still outvote the attorney. All three provenance-based adapters: `0/979` and `0/1021`. This is assurance laundering
  through a quality number: the reading that disagreed is the reading that made the action pass.
- **Losing one sensor holds everything.** Under `unavailable`, every adapter held every safe trial (`4017/4017`). With
  `min_evidence_quality` 0.8 and three sensors, any single loss drops quality below 0.8.
- **Copies count as corroboration for `naive`:** `copy_spoof` ICS 2000/2000 and banking 2000/2000. `provenance`: 0 in
  both.
- **Legal holds most safe actions under every adapter:** `fresh` false hold 576–582 of 997, because the attorney review is
  unavailable half the time.

## Mechanism (interpretation, tied to the code and the trace)

- **Corroboration is only as strong as the weakest counted source's error bound.** In this model, modality diversity
  stops an attacker who spoofs one modality only if the other modality's honest error stays below the margin. Odometry's
  does not. Near the fence, the attacker spoofs GNSS and the odometry's own error supplies the second modality.
- **UNCERTAIN is treated as an abstention.** A counted source that cannot say SAFE does not block. Under `copy_spoof`
  and `adaptive`, that is the honest GNSS reading.
- **The Gate is not implicated.** On every traced trial it decided correctly on what it was given: status PASS, the
  attestation `True`, quality `1.0000`. HV-1 measures the adapters, which Sovereign Veritas does not ship.

## What this leads to

| Item | Class | Why |
|---|---|---|
| Threat model: corroboration counted by number of readings can be laundered by copies and staleness (`naive` `4980/8000` `copy_spoof`, `1664/4003` `stale`); counting by authenticated provenance and modality is necessary in this model but **not sufficient** (`diverse` `4/8000` `common_mode`) | DOCUMENT | the registered trigger ("H2/H3 held") did not fire as worded. These are the observed parts, stated with their refutations |
| Adapter contract for `independent_corroboration`: each counted source's honest error bound below the margin, and a counted UNCERTAIN blocks | EXPERIMENT FIRST (HV-1b, registered before any run) | items 4–5 suggest both rules. Neither is tested |
| One `required_evidence` attestation per property (sv.gate/1) | not proposed | H6 refuted |
| Quality computed from available readings (`naive`) | REJECT as an adapter pattern, in this model | the attorney observation above |

## Left unrun

- HV-1b: the two adapter rules above, plus the false-ALLOW rate when the truth is within one worst-case error of the
  limit (the attacker who picks the moment).
- From the registration: real sensors; an attacker who holds a source key; correlated faults beyond one modality; timing
  attacks on the freshness bound; clock trust.
- A quality definition that ignores age (item 6).
