# BT-001 results: planted faults against the kernel's defences (blue), and a fresh differential run (red)

Registration: [`BT001_PREREG.md`](BT001_PREREG.md) (`d193c00`, amendment A1 `6923777`), committed before any
oracle ran on a mutant. Linux container (x86_64), Python 3.13.16, main `db640a2`. The raw records are in
[`results/bt001/`](../results/bt001/). **Self-tested:** Claude (Anthropic, Opus 5.5) wrote the mutator, the scorer,
the confirming inputs and this file, and the code under test was built with Claude. Chad Holland asked for the run
and has not reviewed it.

## What broke first

1. **Launch 1's null control failed, and the run stopped itself** (BT-P1 refuted for launch 1, kept). The mutator
   re-emitted each file from its syntax tree. That changed quoting and dropped comments, and one test finds its own
   patches by exact source text, so every mutant would have been "killed". Amendment A1 changed the mutator to edit
   only the mutated span (each mutant checked to parse to the registered mutation), and left that one test out of T.
   Details are in the registration. The A1 run's two controls behaved as stated.
2. **BT-P6 is refuted.** Removing the refusal of a NaN or infinite prediction uncertainty (`workflow.py#18`) goes
   unnoticed by the whole test suite (oracle T). The input below then executes the action. CI's separate
   fault-injection job does catch it: `tools/fi_f3_probe.py` exits 1 on that mutant and 0 on the original
   (run 2026-10-22, outside the registered oracles). So the guard is defended in CI, but not by the unit tests.
3. **Some parts of the code nothing notices being changed.** Of the 49 survivors, 42 are real gaps, and 15 of
   those are shown with a concrete input. None is a bug in the current code. Each is a change nothing in the test
   suite would notice.

## Verdicts (from `results/bt001/score.txt`, produced by `tools/bt001_score.py`)

```
per target           mutants  T-killed   T-rate  C-killed   C-rate  T-collection-errors
  decision.py             88        82    93.2%        81    92.0%  0
  verification.py          7         7   100.0%         4    57.1%  0
  idempotency.py          71        54    76.1%         0     0.0%  0
  evidence.py             80        64    80.0%        20    25.0%  0
  capability.py           26        21    80.8%         1     3.8%  0
  runtime.py               9         8    88.9%         7    77.8%  0
  workflow.py             68        64    94.1%         0     0.0%  0
  ALL                    349       300    86.0%
```

| ID | Verdict | Evidence |
|---|---|---|
| BT-P1 controls | **REFUTED at launch 1** (kept); **held at the A1 launch** | launch 1: `T FAIL rc 1` on the null. A1 launch: `control:null … T PASS C PASS as_expected=True`, `control:always-allow … T FAIL C FAIL as_expected=True` |
| BT-P2 T kills ≥ 90% of `decision.py` | **HELD** | 82 of 88, 93.2% |
| BT-P3 C kills ≥ 80% of `decision.py` | **HELD** | 81 of 88, 92.0% |
| BT-P4 C-killed ⊆ T-killed in `decision.py` | **HELD** | `killed by C but not T: none` |
| BT-P5 T kills ≥ 80% overall | **HELD** | 300 of 349, 86.0% |
| BT-P6 every `raise → pass` in idempotency/workflow killed by T | **REFUTED** | `T survivors: ['sovereign_veritas/workflow.py#18']` |
| BT-P7 at least one survivor is a GAP backed by an input | **HELD** | 14 of 15 inputs separate mutant from original (`results/bt001/confirm.txt`) |

No timeouts, and no kills from collection errors: every T kill was an ordinary test failure. The two mutants that
are textually identical to the original (one each in `idempotency.py` and `evidence.py`) are left out of the
rates, as registered.

## Survivor triage (BT-P7)

**7 EQUIVALENT (argued, not run):** no input can tell these apart from the original.
- `decision.py#2`, `#3` and `evidence.py#29`, `#30`: the sign test inside an `OverflowError` branch, which only a
  number beyond about 1.8e308 reaches, so `> 0`, `>= 0` and `> 1` agree.
- `decision.py#18`: unreachable. Every status other than PASS and INSUFFICIENT_EVIDENCE is in `REFUSAL_REASONS`
  and returns earlier.
- `evidence.py#21`: `ensure_ascii` never changes whether the validator's `json.dumps` succeeds.
- `idempotency.py#5`: a missing `lease_expires` defaulting to 1 instead of 0, against a clock near 1.7e9.

**15 GAPs shown by an input** (`tools/bt001_confirm.py`; the output quoted is the original, then the mutant):

| Mutant | What it changes | Input → original / mutant |
|---|---|---|
| `capability.py#0` | `Capability.authorized` defaults to True | Gate on `Capability('x')` → `REFUSE` / **`ALLOW`** |
| `capability.py#16` | registry `check` on a missing capability returns True | `(False, …)` / **`(True, …)`** |
| `workflow.py#18` | NaN-uncertainty refusal removed (FI-FIX F3) | `effects 0 \| ValueError …` / **`effects 1 \| 'ALLOW'`**. Caught by CI's `fi_f3_probe.py` (exit 1) |
| `workflow.py#16` | the same check made unreachable (`not` dropped) | `fi_f3_probe.py` exit 1, as for `#18` |
| `decision.py#72` | `step_count > max_steps` → `>=` | `step_count == max_steps` → `ALLOW` / `REFUSE`. Neither the suite nor the 4,690 contract vectors pin this boundary |
| `evidence.py#59` | `Ledger.append` no longer requires record_id/input_digest | empty record_id → `ValueError` / accepted |
| `evidence.py#56` | the same check needs both missing | id present, empty digest → `ValueError` / accepted |
| `evidence.py#70` | the ledger chain-link check removed | wrong predecessor with consistent digests → `ledger chain broken at index 1` / `True` |
| `evidence.py#18` | canonical JSON escapes non-ASCII | `{"name":"café"}` / `{"name":"café"}`. Every digest of such a record would change |
| `evidence.py#20` | the validator stops sorting keys | `{1:'a','b':2}` → `TypeError` / accepted |
| `evidence.py#7` | tuples dropped when a record is frozen | parameters `{'t': (1, 2)}` → `(1, 2)` / `None` |
| `idempotency.py#44` | an unreadable reservation file returns None | reserve on a corrupt file → `ReservationRefused` / `AttributeError` (still no effect, but the wrong refusal) |
| `idempotency.py#42` | the file-shape check `and` → `or` | file `["state"]` → `ReservationRefused` / `AttributeError`. The first input tried, `{}`, did not separate them; it is kept in the output |
| `idempotency.py#38` | `mkdir(parents=False)` | a store under a missing parent → created / `FileNotFoundError` |
| `idempotency.py#4` | lease expiry `>=` → `>` | `lease_s=0` with a frozen clock → `UNKNOWN` / `IN_FLIGHT` |

**27 GAPs argued, not run:** the difference is observable, and mostly low-stakes.
- **Immutability** (`frozen=False`): `decision.py#5`, `workflow.py#2`, `evidence.py#43`, `#54`,
  `capability.py#2`, `runtime.py#8`.
- **A public method returning `None`:** `decision.py#4` (`to_dict`), `evidence.py#45` (`serialize`),
  `capability.py#3`, `#15`, and `idempotency.py#30`, `#31`, `#61`, `#67` (history and late-event readers).
- **Freezing and thawing sets:** `evidence.py#5`, `#14`.
- **Default lease 30 → 31 s:** `workflow.py#4`, `idempotency.py#0`.
- **`quality_or_default`'s default 0.0 → 1.0:** `evidence.py#36`.
- **`has_record` True when a ledger has no `contains`** (fails closed): `evidence.py#80`.
- **On-disk details:**
  - key order (`idempotency.py#45`, `#49`, `#58`);
  - token length (`#19`, `#46`);
  - file mode `0o600` → `0o601` (`#47`);
  - the expiry timestamp recorded for a corrupt entry (`#14`).

## The contract check (C) by file

C is designed for the Gate, and it shows. It kills 92% of `decision.py`'s mutants and 0% of `idempotency.py`'s
and `workflow.py`'s, which the Gate does not call.

## Red arm

Anti-vacuity control (RT-P1), run before segment 1 and pasted:
`{"cases": 20000, "disagreeing_pairs": {"KI": 221, "VI": 221}, "disagreement_cases": 221, "kernel_decisions": {"ALLOW": 864, "DEFER": 5689, "REFUSE": 13447}, "label": "mutant-steps-ge", "seconds": 6.7}`,
exit 0. **RT-P1 HELD.**

**Segment 1** (`--worker 1000000000 --workers 1 --until 2026-10-22T22:40:00Z`), from
`results/bt001/red/worker1000000000.summary.json`:
`"cases": 21361718`, `"disagreement_cases": 0`, `"disagreeing_pairs": {}`, `"final": true`,
`"kernel_decisions": {"ALLOW": 953208, "DEFER": 6049300, "REFUSE": 14359210}`, `"seconds": 6844.0`. The
disagreements file is empty (0 bytes).

**Segment 2: NOT RUN.** It was to start after segment 1 ended at 22:40Z. Its launch depended on the session being
woken at that time, and the session was not woken until about 00:30Z, after the registered end of
2026-10-23T00:00Z. It was not started late, because that would run outside the registered window.

**RT-P2: HELD for segment 1** (21,361,718 cases, 0 disagreements among K, V and I). It is **not tested for
segment 2.** What this supports (C-DESIGN): K, V and the independent port agree on these 21.4 million generated
inputs at main `db640a2`. That is conformance on the inputs tried, not a rate for other inputs. About 4.5% of the
cases reached ALLOW (953,208), so the ALLOW path was exercised, though less than the others.

## Door (unrun)

**BT-002:** turn each of the 15 GAPs shown by an input into a unit test. Each test must fail on its mutant and
pass on main. Then rerun BT-001's operators on the same targets, and predict that those 15 are killed with no new
survivors. The `capability.py#0`, `#16` and `decision.py#72` tests come first: the first two guard fail-open
defaults, and the third pins a boundary that neither defence fixes today.

Note on the raw files: `confirm.txt` had one container temporary path replaced by `<tmpdir>`. Nothing else was
edited. The `.jsonl` files are force-added: the repository's `.gitignore` excludes `*.jsonl`.
