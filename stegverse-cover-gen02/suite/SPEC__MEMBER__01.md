# Spec Member — The Covering Specification — 01

Status: GEN 02. Issued 2026-11-12 by the StegVerse Build Lane. GEN 01
shipped this member as an unfilled template placeholder (the subject's
second finding); this generation writes it. The covering design specified
here is GEN 01's, unchanged; GEN 02's changes are the lock contract in
section 2 and the vacancy layer in section 5.
Source: Built by the StegVerse Build Lane (coordinator session, Muse) 2026-11-12: GEN 02 cure generation of the covering for holland202/sovereign-veritas; GEN 01 preserved separately as the baseline

## 1. The transition grammar

The covering writes a hash-chained, append-only ledger of transitions
around the subject's EvidenceWorkflow. Each entry is one canonical-JSON
line carrying the previous entry's hash and its own hash over the entry
without the hash field; reload verifies the chain and refuses a broken
one. Three entry kinds:

- **INTENT** — written durably (flush + fsync) BEFORE any external
  effect, one per record_id, ever. A second INTENT for the same
  record_id is refused before execution.
- **COMPLETION** — written after the effect and BEFORE the evidence
  record is delegated to the subject's sink, carrying the effected
  side's attestation: the before/after observation of the target's
  state, read back through a probe that does not go through the
  executor, and the subject's EO-2 verdict recomputed from it.
- **UNKNOWN** — written when the executor raised: the effect may or may
  not have happened. The transition stays open and the record_id stays
  refused.

An INTENT with no COMPLETION and no UNKNOWN is an OPEN transition: a
first-class, enumerable state, never silence.

## 2. The lock contract (GEN 02)

The duplicate refusal is atomic under an exclusive OS file lock on the
ledger file itself, taken by a single helper (_lock_exclusive) used by
every append path:

- POSIX: fcntl.flock, LOCK_EX / LOCK_UN.
- Windows: msvcrt.locking over byte 0 of the ledger file, LK_LOCK /
  LK_UNLCK. Every process appending to the same ledger contends on the
  same byte. msvcrt.locking retries for roughly ten seconds and then
  raises OSError: a caller that cannot acquire the lock fails visibly
  instead of writing unlocked.

Inside the critical section the append re-reads the on-disk tail (so two
processes cannot fork the chain), runs any precheck against the freshly
read entries (begin's duplicate check is such a precheck), then appends,
flushes, and fsyncs. GEN 01 imported msvcrt but never called it, so on
Windows no lock was taken; the duplicated lock logic in GEN 01's two
append paths is replaced by the single helper and the single append
path. test_lock_contention.py exercises the contract with separate
processes racing one record_id.

## 3. Pair verification

verify_transition.py checks the ledger against the subject's evidence
records as a PAIR (V1–V6): chain integrity; no duplicate INTENT; every
SUCCEEDED claim backed by a COMPLETION whose EO-2 verdict recomputes and
attests; every COMPLETION matched by its evidence record (a lone
completion is NAMED — the X5 asymmetry made visible); no COMPLETION
standing behind a record that claims no execution (the EO-1 construction
fails here); open and UNKNOWN transitions listed, never counted as
success. The verifier shares no code with the writer path beyond the
published formats.

## 4. The registered cases

run_cover_tests.py registers seven cases against the subject's own
constructions: C0 anti-vacuity (two record_ids, two effects, pair
CONSISTENT); C1 duplicate refused with a has_record-less sink (one
effect, where the subject's unguarded configuration gives two); C2 the
X4 race (exactly one effect); C3 the X5 asymmetry (the COMPLETION stands
and is named); C4 the EO-1 construction (the pair FAILS, V5); C5 an
unattested SUCCEEDED claim (FAILS, V3); C6 executor failure (UNKNOWN
held, retry refused before the executor is reached). GEN 02 adds L1–L2
(lock contention across processes) and T0–T3 (gate non-vacuity).

## 5. The conformance gate (GEN 02)

self_check.py carries the template checks verbatim (manifest members
verify by size + SHA-256; no unlisted files; the funding spine: ProjectID
and Funding on the suite's face and in its funding statement; derivation
recorded) and a GEN 02 vacancy layer: no prose member may contain the
template's placeholder slot text; the charter's Purpose section must
carry substance; the spec and references members must carry substance
and, for references, at least three concrete pointers; no prose member
may be a stub. test_non_vacuity.py proves the layer can fail by running
the gate against deliberately vacated copies whose manifests are
re-bound, so only the vacancy checks can be the cause.
