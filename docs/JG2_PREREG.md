# JG-2: checking section 6 of James Greenwood's report (non-repudiation and canonicalization) — registration

**Status:** REGISTERED 2026-10-03, in a commit of its own. The probe does not exist yet. This file is
not edited after this commit; results go in `docs/JG2_RESULTS.md`.

**Method:** principia-artificialis `METHOD.md` at `646eed7`. This is the next unrun test named by JG-1.

**Source:** section 6 of the report, preserved verbatim in
`docs/external/greenwood_2026-10-03_challenge-and-audit-report.md`. The report is AI-assisted (Gemini).
Its three statements are claims about this repository. Here they are checked against the code
(C-EXT), not adopted.

**Provenance:** AI participation → human validation → human editing/curation → human responsibility.
- **AI participation:** Claude (Anthropic, Opus 5.5).
- **Human review:** direction only (Chad Holland).
- **Responsibility:** Chad Holland.
- **Self-tested.**

## The three statements, paraphrased (the exact text is in the preserved report)

- **S1.** All evidence records use `canonical_json()` (sorted keys, compact separators,
  `ensure_ascii=False`), giving byte-level hash determinism across Linux, Android, macOS and Windows.
- **S2.** The `.gitattributes` rules prevent line-ending drift from corrupting package signatures or
  witness logs.
- **S3.** Non-repudiation is strictly enforced by detached Ed25519 signatures (`.json.sig`), bound to
  the keys in `keys/allowed_signers`.

## What was read before this registration (exploratory, C-EXPLORE)

The following was read, and partly run, before this file was written:
- `.gitattributes`;
- `evidence.canonical_json` and its single `sha256` call site;
- `package.sha256_hex` and its callers;
- the signature options of `tools/verify_package.py` and `tools/consumer.py`;
- `git check-attr` on six paths.

The predictions below rest on that reading. The checks themselves are run only by the probe.

## Predictions

| ID | Statement | Prediction |
|---|---|---|
| P1 | S1 | Every `sha256` in the `sovereign_veritas/` package hashes either `canonical_json(...)` or raw artifact bytes. For a record whose values contain non-ASCII text, the evidence digest equals `sha256(canonical_json(payload))` and does not equal the digest of `ensure_ascii=True` JSON |
| P2 | S1, "across … Android" | **NOT RUN here.** CI covers Linux, macOS and Windows; this probe runs on Linux only |
| P3 | S2 | `git check-attr text` is `unset` for `contract/gate_vectors.jsonl`, `evidence/*.json`, `evidence/*.sig`, `witness/packages.log` and `keys/allowed_signers` |
| P4 | S2, beyond its scope (ours) | `git check-attr text` is `unspecified` for `docs/external/*.md`, files whose recorded sha256 is of their exact text. They are therefore **not** protected from line-ending conversion on checkout. A gap |
| P5 | S3 | All 8 `evidence/*.json` packages verify with `ssh-keygen -Y verify` (namespace `sv-package`, identity `holland202`), and the key in `keys/allowed_signers` is `ssh-ed25519` |
| P6 | S3, anti-vacuity | A copy of a package with one byte changed fails the same check |
| P7 | S3, "strictly enforced" | **Signatures are opt-in:** `tools/consumer.py accept` on a valid package without `--signature` exits 0, and `tools/verify_package.py` without `--signature` reports authenticity `NOT_PROVEN` rather than failing. So "strictly enforced" holds only when the caller asks for the check |

## Fix (design, frozen here)

- **F1:** add `docs/external/*.md -text` to `.gitattributes`. After it, P4's paths report `unset`.
- **Not fixed here:** whether signatures should become mandatory (P7). That is a contract and format
  decision, and it is Chad Holland's. It is recorded as a proposal.

## Simplest rival

"S3 is only wording, since the repository already says that an unsigned package is NOT_PROVEN." P7
tests the behaviour itself. The rival is consistent with P7 holding: then the overstatement is in the
report, not in the code.

## Trigger table (METHOD.md §3)

| Trigger | Answer |
|---|---|
| Feasibility | No. Fixed files |
| Noise | No |
| Statistics | No |
| Evidence | **No.** These are integrity and authenticity checks of stored artifacts, not a rule's handling of fresh, stale or replayed evidence |
| Independence | No independence is claimed. Greenwood's Windows run of D1 (signature PASS) is his re-run, reported in his words |
| External | **Yes** (C-EXT): the claims are checked one by one, here |
| Device | **Yes**, for P2's "Android". It is not run here and is labelled NOT RUN |
| Verdict code | **Yes** (C-BUILD): the probe's checks fail closed. A missing `ssh-keygen` gives exit 2 (COULD NOT RUN), not a pass |
| Exploration | **Yes**: the reading listed above |
| Method comparison | No |

**Probe:** `tools/jg2_probe.py`. It prints a HELD, REFUTED or NOT RUN line for each prediction, a
VERDICT line and a DIGEST, and has a `--sabotage` switch that skips the byte change in P6. Under
sabotage, P6 must be REFUTED and the probe must exit 1.

## Next unrun test

Run P5–P7 on the S25 under Termux (`pkg install openssh`). That is the Android part of S1 and S3.

## Amendment 1 (2026-10-04, after a failure; the text above is unchanged)

**What failed.** P1 was REFUTED in CI (job `red-team`) at `2b7f8a2` (RK-2, PR #38) and at `c7e96a6` (MP-1, PR #42,
built on RK-2). RK-2 added a fifth `sha256` site that hashes neither `canonical_json(...)` nor artifact bytes.
Output at `2b7f8a2`, verbatim:

```
REFUTED P1  {"differs_from_ascii_json": true, "digest_is_canonical": true, "sha256_sites": ["sovereign_veritas/evidence.py:48", "sovereign_veritas/idempotency.py:108", "sovereign_veritas/package.py:44", "sovereign_veritas/package.py:49", "sovereign_veritas/package.py:92"], "sites_not_canonical_or_artifact": ["sovereign_veritas/idempotency.py:108"]}
```

P1 stays REFUTED at those two commits. This amendment does not change that record.

**What the site is.** `FileReservations._path` hashes the idempotency key to name its reservation file. The hash is
never stored as evidence, never signed and never compared with a digest. It is a file name.

**What the failure taught.** Hashing a key means comparing it byte for byte. The same visible key in two Unicode
forms (NFC and NFD) is two keys, so a caller that re-normalizes its key between attempts can run the action
twice. `MemoryReservations` behaves the same way (dictionary keys), so the two stores agree. This is now pinned by
`tests/test_idempotency.py::test_keys_compared_byte_for_byte_no_unicode_normalization` and stated as a limit in
RK-2's results. It is not fixed: the key is the caller's, and normalizing it inside the store would change RK-2's
registered behaviour after its run.

**The amended rule.** P1 now allows a third kind of site: a hash used only to name a file, matched to the exact
line in `sovereign_veritas/idempotency.py` (`FILE_NAME_LINE` in `tools/jg2_probe.py`) and reported separately as
`file_name_only_sites`. Any other new hash is still refused. Decided by Chad Holland on 2026-10-04 after the
failure, from options set out by Claude (Opus 5.5); written after the result, so it is not a prediction.

**The amended check can still fail.** With a second unclassified hash planted in `idempotency.py`, P1 is REFUTED
again and the probe exits 1:

```
REFUTED P1  {"differs_from_ascii_json": true, "digest_is_canonical": true, "file_name_only_sites": ["sovereign_veritas/idempotency.py:108"], "sha256_sites": ["sovereign_veritas/evidence.py:48", "sover
VERDICT 5 of 6 as registered (P2 not run) ...
```

After the amendment, on the RK-2 branch:

```
HELD    P1  {"differs_from_ascii_json": true, "digest_is_canonical": true, "file_name_only_sites": ["sovereign_veritas/idempotency.py:108"], "sha256_sites": ["sovereign_veritas/evidence.py:48", "sovereign_veritas/idempotency.py:108", "sovereign_veritas/package.py:44", "sovereign_veritas/package.py:49", "sovereign_veritas/package.py:92"], "sites_not_canonical_or_artifact": []}
VERDICT 6 of 6 as registered (P2 not run)
DIGEST 5281e7697a2913fa1d296d1fea32ae917e25b14fa106d61daa06c48c5b6b4f67
```

## Record 2 (2026-10-07): REFUTED at `b7d072b`, the code changed to meet the rule; the rule is unchanged

**What failed.** P1 was REFUTED in CI (job `red-team`) at `b7d072b` (EX-1, `docs/EX1_RESULTS.md`). EX-1 added three
`sha256` sites that hashed a local copy of canonical JSON (`_canon`) instead of `canonical_json(...)`. Reproduced
locally at `b7d072b`; the detail, verbatim:

```
"sha256_sites": ["sovereign_veritas/evidence.py:48", "sovereign_veritas/execution.py:103", "sovereign_veritas/execution.py:198", "sovereign_veritas/idempotency.py:166", "sovereign_veritas/package.py:45", "sovereign_veritas/package.py:50", "sovereign_veritas/package.py:93", "sovereign_veritas/receipts.py:45"],
"sites_not_canonical_or_artifact": ["sovereign_veritas/execution.py:103", "sovereign_veritas/execution.py:198", "sovereign_veritas/receipts.py:45"]
```

P1 stays REFUTED at `b7d072b`. Because the red-team job stopped at this step, none of the EX-1 steps after it ran in CI at that
commit.

**What the sites were.** Two hashed journal events and receipts, and one named a journal file (the intent id). The copy
differed from `canonical_json` only in refusing NaN/Infinity: on 20000 random finite values the bytes were identical.

**What changed.** The code, not the rule. The three sites now hash `canonical_json(...)`, and the NaN/Infinity refusal is a
separate check before hashing. No digest changes for any finite value. The intent id hashes `canonical_json([domain,
principal, key])`, which is a hash of canonical JSON under P1's original wording, so it needs no amendment. This was decided
by Claude (Opus 5.5) without asking Chad Holland, because it changes code to meet a registered rule. Changing the rule to
fit the code would have needed his decision, as Amendment 1 did. After the change:

```
HELD    P1  {"differs_from_ascii_json": true, "digest_is_canonical": true, "file_name_only_sites": ["sovereign_veritas/idempotency.py:166"], "sha256_sites": ["sovereign_veritas/evidence.py:48", "sovereign_veritas/execution.py:114", "sovereign_veritas/execution.py:209", "sovereign_veritas/idempotency.py:166", "sovereign_veritas/package.py:45", "sovereign_veritas/package.py:50", "sovereign_veritas/package.py:93", "sovereign_veritas/receipts.py:50"], "sites_not_canonical_or_artifact": []}
VERDICT 6 of 6 as registered (P2 not run)
DIGEST ae0ba90174049b9ae240d0191756faf16e7950ced8e1a6c4e80c64676450ae5d
```
