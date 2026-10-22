# KC-1 results: a reused idempotency key with changed action parameters

Registration: [`KC1_PREREG.md`](KC1_PREREG.md), with pre-run revisions R1–R3, merged in PR #90 (`e69cdf2`) before
`tools/kc1_probe.py` existed. Run 2026-10-22 ~21:10Z, Linux container (x86_64), Python 3.13.16.
`tools/kc1_probe.py` SHA-256 `7ca7784d…e07e`. The raw outputs are in [`results/kc1/`](../results/kc1/), with
`SHA256SUMS`. **Self-tested:** Claude (Anthropic, Opus 5.5) wrote the probe, ran it, and wrote this file.
Chad Holland gave direction and has not reviewed it. Joe Krausz proposed the question, not the cases.

## What broke first

1. **The first probe run crashed.** It ended with
   `TypeError: Object of type mappingproxy is not JSON serializable`, while printing the ledger summary. The
   ledger holds the action's parameters frozen. All four modes exited 1 because of the crash, which made a
   crash look like a refutation. Reading the raw output caught it. The fixes:
   - convert the frozen parameters with `dict(...)`;
   - make an uncaught probe error exit **2** with `PROBE ERROR … (no verdict)`, so a crash can never pass for a
     verdict.

   The crashed outputs are not used. All results below are from the fixed probe.
2. **The printed records sort parameter keys.** `json.dumps(..., sort_keys=True)` shows D7r's `{"b": 2, "a": 1}`
   as `{"a": 1, "b": 2}`. A field `param_order` was added to every record, so the raw output shows the order
   actually sent. It reads `"param_order": ["b", "a"]` for D7r in both stores.
3. **KC-P7 needed a reading.** The registration's "the same message as D1" cannot hold literally, because
   refusal messages name their key, and D7r uses key `K7`. It is scored as "the same type and message as the
   same-order duplicate D7 on the same key". The probe's docstring records this reading.

## Verdicts

| ID | Verdict | Raw evidence (quoted from `results/kc1/`) |
|---|---|---|
| KC-P1 safety | **HELD** | `normal.txt`: `KC-P1  HELD`. Every D and C line has `"effects_added": 0` and `"exc_type": "ReservationRefused"`. K0 has `"effects_added": 1`. Both stores |
| KC-P2 the gap | **HELD (the gap is confirmed)** | `KC-P2 pairs: memory:C1=D1:same memory:C2=D1:same memory:C3=D3:same memory:C4=D4:same file:C1=D1:same file:C2=D1:same file:C3=D3:same file:C4=D4:same`. For example, C1 (amount 2) and D1 (amount 1) both raise `"idempotency key 'K' is COMPLETED: refused before execution"` |
| KC-P3 no trace (as narrowed by R2) | **HELD** | every D and C line has `"records_added": 0, "history_changed": false`. `K-records [{"parameters": {"amount": 1}, "record_id": "r0"}]` in both stores. Nothing is claimed about logs or other telemetry |
| KC-P4 string-level anti-vacuity | **HELD** | `tagged-refusal.txt`: all eight pairs `DIFFERENT`, `KC-P2  REFUTED`, exit 1. For example, `"idempotency key 'K' is COMPLETED: refused before execution [call 2]"` |
| KC-P4b decisive anti-vacuity | **HELD** | `digest-bound.txt`: all eight pairs `DIFFERENT`, `KC-P2  REFUTED`, exit 1. C1 raises `"idempotency key 'K' conflicting reuse: decided action differs from the one the key was reserved for: refused before execution"`; D1 still raises the plain `COMPLETED` message |
| KC-P5 anti-vacuity for safety | **HELD** | `accept-all.txt`: `KC-P1  REFUTED`, exit 1. For example, `memory D1` has `"effects_added": 1` |
| KC-P6 regression | **HELD** | `git diff origin/main -- sovereign_veritas` is empty. Suite: `544 passed, 1 skipped in 111.33s` |
| KC-P7 key order | **HELD** | `normal.txt`: D7r (`"param_order": ["b", "a"]`) and D7 raise the same `"idempotency key 'K7' is COMPLETED: refused before execution"`, with 0 effects, `KC-P7  HELD`. Under `digest-bound`: `KC-P7  HELD`, so the canonical digest treats key order as a duplicate, not a conflict |

Exit codes: normal **0**; `tagged-refusal` **1**; `accept-all` **1**; `digest-bound` **1**. These are the
registered outcomes. Side effects of the mutants, which the registration did not predict and which are recorded
here:
- `tagged-refusal` also refutes KC-P7, because every message differs;
- `accept-all` also refutes KC-P3 and KC-P7, because accepted attempts add records and effects.

## What this means, and what it does not

- **Safety holds; the distinction is missing.** Both stores fail closed on every conflicting reuse: no effect,
  and the attempt is refused before execution. A caller cannot tell a conflicting reuse from a harmless retry:
  the exception type and the message are byte-identical in all four key states and both stores. No ledger
  record or store history keeps the attempt.
- **The probe can see the difference when it exists.** The digest-bound mutant, which is a sketch of the KC-2
  door, is credited as distinguishing every conflict. It still treats reordered keys as a duplicate.
- **Not shown:**
  - anything about the relying-party consumer, which reads no key;
  - whether a caller *should* be told "conflict";
  - concurrency;
  - other machines, network filesystems, or the phone;
  - application logs or telemetry.

## Trigger table, as run

| Trigger | Answer |
|---|---|
| C-FEAS | 4 modes × 2 stores × (12 workflow attempts + 1 direct reservation). Runtime was not measured |
| C-NOISE | deterministic. Messages compared byte for byte. The only randomness is the reservation token, which never appears in a message |
| C-INDEP | self-tested (see above) |
| C-DEVICE | Linux container only, **not the S25 or S23**. `FileReservations` on Android storage is untested |
| C-BUILD | crash → exit 2 (added after the crash above). Any refuted prediction → exit 1, which all three mutants produce |
| C-EXPLORE | the crashed first run (§ What broke first, item 1) is the only run before these |
| C-DESIGN | a deterministic case test. It supports existence claims (this pair is indistinguishable) and conformance on these 12 attempts per store. No rate |
| C-SYNTH | no generated inputs. All cases are written out in the registration and the probe |

## Door (unrun)

**KC-2**, as registered: bind the decided action's canonical digest to the reservation at `reserve` time, and
refuse a mismatch with a distinct reason. Then rerun this probe with KC-P2 flipped and KC-P1 and KC-P7
unchanged. The `digest-bound` mutant shows the probe would credit such a change. Where KC-2 belongs is the
owner's decision.
