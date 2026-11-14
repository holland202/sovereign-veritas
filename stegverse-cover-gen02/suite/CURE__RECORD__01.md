# CURE RECORD — GEN 02

StegVerse Build Lane, 2026-11-12. ProjectID LINKEDIN-SOVEREIGN-VERITAS-EVAL.
Each finding below is the subject author's, from his examination of
GEN 01 on 2026-11-12. Each cure names what changed, where, and the
evidence a reader can re-run. GEN 01 is preserved unmodified; nothing in
this record edits it.

## Finding 1 — the Windows lock was a no-op under a contrary claim

**As found.** transition_ledger.py imported msvcrt in its Windows branch
but never called it; both append paths locked only `if fcntl is not
None`. On Windows no lock was taken, while the module docstring claimed
the duplicate refusal was atomic "under an OS file lock — for every
caller."

**The cure.** One helper, _lock_exclusive, implements the lock on both
platforms — fcntl.flock on POSIX; msvcrt.locking over byte 0 of the
ledger file on Windows, so every process appending to the same ledger
contends on the same byte — and every append path calls it. GEN 01's
duplicated lock logic (the append path and begin's inline copy) is
replaced by a single append path; begin's duplicate check runs as a
precheck inside the critical section against the freshly read on-disk
entries, as before. The docstring now names both mechanisms, and states
the Windows behavior exactly, including that msvcrt.locking's bounded
retry ends in a visible OSError rather than an unlocked write. A
drive-by truth fix in the same file: begin's return annotation now
matches what it returns (the entry dict; GEN 01 annotated str).

**Evidence.** The GEN 01 → GEN 02 diff of transition_ledger.py touches
only the regions above. run_cover_tests.py still passes 7/7, including
C2 (the in-process race). test_lock_contention.py races eight separate
processes on one record_id against one ledger file: exactly one
admitted, seven refused, one INTENT on disk, chain verifying on reload,
and a fresh process afterwards still refused. Platform scope, stated
plainly: the author-side run exercises the POSIX branch; the Windows
branch is verified by construction (one helper, both branches
implemented, no path that skips the lock) and stands open for the
subject's reproduction on Windows.

## Finding 2 — the conformance gate could not fail on vacancy

**As found.** SUITE__CHARTER__01.md, SPEC__MEMBER__01.md, and
REFERENCES__01.md shipped as the template's unfilled placeholder text,
and the suite's conformance proof read CONFORMANT: the checker verified
member bytes against the manifest and the funding spine, but nothing
verified that the prose members say anything.

**The cure.** Two parts. (a) The three members are written in full in
this generation: the charter states the suite's purpose and level
discipline; the spec member specifies the covering (grammar, lock
contract, pair verification, case registry, gate); the references
member carries the surrounding record's pointers. (b) The gate itself:
self_check.py retains every template check verbatim and adds a vacancy
layer — no prose member may contain the template's placeholder slot
text; the charter's Purpose section must carry substance; the spec and
references members must carry substance (references: at least three
concrete pointers); no prose member may be a stub. The manifest's
derivation record names the extended checker by its hash, so the
extension is on the record, not silent.

**Evidence.** test_non_vacuity.py runs the suite's own self-check
against copies of the suite: a pristine copy passes (control); copies
with the charter, the spec, or the references member replaced by the
exact placeholder text GEN 01 shipped — manifests re-bound so only
content checks can fail — fail, with every failure attributable to the
vacancy layer. A gate that can fail, shown failing, is the only kind
whose passing means anything.

## Finding 3 — the commercial shape was in the file, not the message

**As found.** GEN 01's funding statement carried the continuation
arrangement before the terms had been stated to the subject in any
message; he learned the shape of the offer from the artifact.

**The cure.** Procedural and on the record. The terms were stated in
the message presenting GEN 01's results (the introductory-session and
continuation prices, the election framing, and the UNFUNDED specimen's
terms), and FUNDING__STATEMENT__01.md in this generation states them in
the same words, with the subject's 2026-11-12 answer recorded beside
them: continuation not elected; the collaboration continues public and
non-commercial. This generation was built after that answer, as cure
work on an UNFUNDED specimen, and creates no charge. The standing rule
the lane works under henceforth: terms are stated in the message
first; the file records what the message said.
