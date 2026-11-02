# SEC-005 results: FIXED_IN_TESTED_SCHEDULES (run1, 2026-11-02)

Registration: [`SEC005_PREREG.md`](SEC005_PREREG.md), committed alone at `31d667d` before any code.
Fix and probe: `a192c68`. Recorded outcome pinned: `8f08769`.

## What could have gone wrong, first

- **Self-tested.** Claude (Opus 5.5) registered the fix, wrote it, wrote the probe that judges it, and ran it.
  Nothing here is independent validation. The SEC-004 probe that found the defect was also not independent of
  this repository's authors.
- **One design detail was fixed after registration, before the first run.** The registration describes
  `--sabotage` as replacing the lock with a no-op. The probe as built also runs a NOLOCK arm in *every* run, and
  P6 is scored on that arm; `--sabotage` additionally disables the lock in the LOCK arm, so the verdict flips to
  `NOT_FIXED`. This adds a control; it removes none. Disclosed here because it is not in the registration's text.
- **"Blocked" means "had not finished after `BLOCK_S` = 3.0 s".** It is not an observation of blocking forever.
  The claim that it would never finish while the other holder is inside rests on the OS lock, not on the timer.
- **P9 (JG-2 P1) could not run in this sandbox** (`ssh-keygen` is missing; the JG-2 probe stops before P1). It
  is covered by CI's `jg2_probe.py` step, not by a local run.
- **Behaviour change, and a liveness cost.** In L1 the stale-but-still-valid holder now wins: its completion
  lands and the operator's `release()` is refused because the key is COMPLETED. Before the fix the release
  "succeeded" and the new reservation was then silently overwritten. A paused holder now also blocks every
  other operation on its key.
- **Not run on the S25.** Android/Termux is **NOT VALIDATED**.

## Raw output

All in `results/sec005/run1/`, unedited (sha256):

| File | What | sha256 |
|---|---|---|
| `sec004_baseline_7e40c12.txt` | unchanged SEC-004 probe, before the fix | `53eb4f3e382540caf11f499456e31eb359cbaf64edd8f24268f08e34d644de5c` |
| `run.txt` | SEC-005 probe, normal run | `a34a0671bec67b5319516230f8feccf56830d6ac48e26a12ebdd18ddae4aa7fe` |
| `sabotage.txt` | SEC-005 probe, `--sabotage` | `ed245d08955c93f07bbdf2477c62b310f21a9d49049d0e2bcb5d9a860fa12dba` |
| `sec004_on_fixed.txt` | unchanged SEC-004 probe, after the fix | `cca402eb5d2d43087d2404725859407035074f9df56e65dd624dbe762d82ba6a` |
| `pytest.txt` | full suite after the fix | `516fb94d031dd8fce91e742615ee56ca8bc9f2b84d74fc125a493cec330a2d9c` |

Excerpts. The `KEY=`, `P`, `VERDICT`, `DIGEST` and `GATE` lines are pasted verbatim. The `LOCK_ARM`/`NOLOCK_ARM`
lines are the case objects from `run.txt`'s JSON, loaded with `json.loads` and re-printed one case per line
(same keys and values; the file itself is indented JSON):

```
# sec004_baseline_7e40c12.txt (idempotency.py blob 071fc3fe…, Python 3.13.18)
  "verdict": "SECURITY_FAIL"
GATE=SECURITY_FAIL

# run.txt
IDEMPOTENCY_BLOB=8013269f8051653c4dd0c900a86927453f448cd9
LOCK_ARM L1   {"a_errors": [], "b_blocked_while_a_paused": true, "b_error": "ValueError", "b_released": false,
               "final_is_old": true, "final_state": "COMPLETED", "new_token_issued": false, "overwrite": false,
               "pause_count": 1, "released_history": 0}
NOLOCK_ARM L1 {"a_errors": [], "b_blocked_while_a_paused": false, "b_error": null, "b_released": true,
               "final_is_old": true, "final_state": "COMPLETED", "new_token_issued": true, "overwrite": true,
               "pause_count": 1, "released_history": 1}
LOCK_ARM L2   {"a_errors": [], "final_is_new": true, "final_state": "IN_FLIGHT", "late_complete_for_old": 1}
LOCK_ARM L3   {"blocked_while_child_held": true, "child_rc": 0, "release_done": true, "release_error": null}
NOLOCK_ARM L3 {"blocked_while_child_held": false, "child_rc": 0, "release_done": true, "release_error": null}
LOCK_ARM L4   {"child_rc": 0, "release_done_after_crash": true, "release_error": null}
P1 HELD
P2 HELD
P3 HELD
P4 HELD
P5 HELD
P6 HELD
DURATION_S=6.4
VERDICT FIXED_IN_TESTED_SCHEDULES: 6 of 6 as registered
DIGEST=41c7e72443d77b2e3f7b1b7697a67bd05809661afb9d1c08b9b9858d5e2a96de

# sabotage.txt
P2 REFUTED
P4 REFUTED
VERDICT NOT_FIXED: 4 of 6 as registered

# sec004_on_fixed.txt
GATE=INCONCLUSIVE_SOURCE_CHANGED sovereign_veritas/idempotency.py
EXPECTED_BLOB=071fc3fe64672c6cdbe7a3fe6e6406554c03a574
OBSERVED_BLOB=8013269f8051653c4dd0c900a86927453f448cd9

# pytest.txt
492 passed, 49 skipped in 43.53s
```

The normal run was repeated three more times in this sandbox; each printed the same `DIGEST`.

## Predictions

| ID | Prediction | Result |
|---|---|---|
| P1 | L0: SEC-004 controls C0, C1, C3 hold | HELD |
| P2 | **L1: no fresh reservation overwritten**; B blocked while A paused; A's COMPLETED lands; B's release refused | **HELD** |
| P3 | L2: a late holder is recorded, not obeyed | HELD |
| P4 | L3: the lock holds across processes | HELD |
| P5 | L4: a crashed holder leaves no stuck lock | HELD |
| P6 | anti-vacuity: with no lock, L1 reproduces SEC-004 and L3 is not blocked | HELD (NOLOCK arm: `overwrite: true`) |
| P7 | full suite green on the CI matrix (Linux x86_64 and arm64, macOS, Windows; Python 3.10, 3.12, 3.14) | see "CI" below |
| P8 | unchanged SEC-004 probe refuses the fixed module, `INCONCLUSIVE_SOURCE_CHANGED`, exit 2 | HELD (exit 2) |
| P9 | JG-2 P1 unchanged (no new hash site) | NOT RUN locally; CI |

## What this shows and does not show

- **Shows (implementation, forced local schedules):** with the lock, the SEC-004 interleaving can no longer
  happen: the release cannot start while a holder is between its token check and its write, so it sees the
  completed key and is refused. Without the lock, the same probe in the same run reproduces SEC-004's overwrite.
  The lock is also observed to hold between two processes, and a holder that dies without unlocking does not
  leave the key stuck.
- **Does not show:** correctness under schedules the probe did not force; network filesystems; anything on
  Android; that a late holder's *external* effect is prevented (that still needs a fence at the target, OBS-1);
  independent validation.

## CI

To be appended after the matrix run on the PR.

## Still open (the door)

- Run `tools/sec005_lock_probe.py` on the S25 under Termux.
- A many-thread randomized-schedule stress run, registered separately before it is written.
- `tools/sv_attack_001_probe.py` and `tools/sv_fix_001_probe.py` now fail their own preconditions if re-run
  (registered consequence); they are left unedited.

## Provenance (M13)

Claude (Anthropic, Opus 5.5) designed, built, ran and wrote this up → human validation: not performed → human
editing/curation: direction by Chad Holland, 2026-11-02 → human responsibility: Chad Holland. Review level:
direction only.
