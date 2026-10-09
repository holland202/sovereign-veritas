# JG-2 results: section 6 of James Greenwood's report, checked against the code

The registration is [`JG2_PREREG.md`](JG2_PREREG.md), committed alone at `b7fc1ea`. The report is
[preserved verbatim](external/greenwood_2026-10-03_challenge-and-audit-report.md); it is AI-assisted
(Gemini).

## What could have gone wrong, first

- **Self-tested.** Claude (Opus 5.5) wrote the predictions and the probe, after reading the code they
  check (listed in the registration).
- **The probe crashed on its first run.** It called `record_digest()`, which is a property, and raised
  `TypeError`. That was fixed before the recorded run. It was an implementation error in the
  instrument, not an outcome.
- **The pin covers outcomes only.** The digest covers file lists that will grow as packages and
  external texts are added, so the digest is printed but not pinned. That is a deviation from
  WORKFLOW W4.
- **P2 is NOT RUN.** Nothing was run on Android or the S25.
- P3 and P4 checked only the files present on this branch. James Greenwood's own record (PR #21) and
  Amos Tipton's (PR #20) are not on it yet, but F1's pattern covers them once they merge.

## Raw output

Before F1 (`results/jg2/run_prefix.txt`):

```
$ python tools/jg2_probe.py --pre-fix
HELD    P1  {"differs_from_ascii_json": true, "digest_is_canonical": true, "sha256_sites": ["sovereign_veritas/evidence.py:48", "sovereign_veritas/package.py:44", "sovereign_veritas/package.py:49", "sovereign_veritas/package.py:92"], "sites_not_canonical_or_artifact": []}
HELD    P3  {"of": 19, "unset": 19}
HELD    P4  {"attrs": {"docs/external/perplexity_2026-10-02_gsn_prov_formal_mapping.md": "unspecified", "docs/external/perplexity_2026-10-02_repository_analysis.md": "unspecified", "docs/external/perplexity_2026-10-02_strongest_opposite.md": "unspecified"}, "expect": "unspecified"}
HELD    P5  {"key_type": "ssh-ed25519", "of": 8, "verified": 8}
HELD    P6  {"tampered_copy_verifies": false}
HELD    P7  {"consumer_accepts_without_signature": "sv_package_7548237bceca.json", "verify_authenticity": "NOT_PROVEN", "verify_without_signature_exit": 0}
NOT RUN P2  (Android / Termux: not run here)
VERDICT 6 of 6 as registered (P2 not run)
DIGEST 37b7a4d53a0b20fc08acfce4e86315d2f1ab6786cfd14339b756e2f653734f59
RECORDED not pinned yet
exit 0
```

After F1, with the sabotage control (`results/jg2/run.txt`):

```
$ python tools/jg2_probe.py
HELD    P1  {"differs_from_ascii_json": true, "digest_is_canonical": true, "sha256_sites": ["sovereign_veritas/evidence.py:48", "sovereign_veritas/package.py:44", "sovereign_veritas/package.py:49", "sovereign_veritas/package.py:92"], "sites_not_canonical_or_artifact": []}
HELD    P3  {"of": 19, "unset": 19}
HELD    P4  {"attrs": {"docs/external/perplexity_2026-10-02_gsn_prov_formal_mapping.md": "unset", "docs/external/perplexity_2026-10-02_repository_analysis.md": "unset", "docs/external/perplexity_2026-10-02_strongest_opposite.md": "unset"}, "expect": "unset"}
HELD    P5  {"key_type": "ssh-ed25519", "of": 8, "verified": 8}
HELD    P6  {"tampered_copy_verifies": false}
HELD    P7  {"consumer_accepts_without_signature": "sv_package_7548237bceca.json", "verify_authenticity": "NOT_PROVEN", "verify_without_signature_exit": 0}
NOT RUN P2  (Android / Termux: not run here)
VERDICT 6 of 6 as registered (P2 not run)
DIGEST 8616b4d867f0262542953dd947509c3fe798b3aecf0a0362a30bd7bd89ece213
RECORDED not pinned yet
exit 0
$ python tools/jg2_probe.py --sabotage
SABOTAGE: P6 checks an untampered copy
HELD    P1  {"differs_from_ascii_json": true, "digest_is_canonical": true, "sha256_sites": ["sovereign_veritas/evidence.py:48", "sovereign_veritas/package.py:44", "sovereign_veritas/package.py:49", "sovereign_veritas/package.py:92"], "sites_not_canonical_or_artifact": []}
HELD    P3  {"of": 19, "unset": 19}
HELD    P4  {"attrs": {"docs/external/perplexity_2026-10-02_gsn_prov_formal_mapping.md": "unset", "docs/external/perplexity_2026-10-02_repository_analysis.md": "unset", "docs/external/perplexity_2026-10-02_strongest_opposite.md": "unset"}, "expect": "unset"}
HELD    P5  {"key_type": "ssh-ed25519", "of": 8, "verified": 8}
REFUTED P6  {"tampered_copy_verifies": true}
HELD    P7  {"consumer_accepts_without_signature": "sv_package_7548237bceca.json", "verify_authenticity": "NOT_PROVEN", "verify_without_signature_exit": 0}
NOT RUN P2  (Android / Termux: not run here)
VERDICT 5 of 6 as registered (P2 not run)
DIGEST f2a3d291f3f5925a49e843913a4af7fdcbaeee6126ebe8658f876449c56c80a8
exit 1
```

The existing tests are unchanged: `python -m pytest -q` gives 450 passed, 1 skipped.

## The three statements, judged

| Statement | Verdict | Basis |
|---|---|---|
| **S1** canonical JSON | **SUPPORTED within the package; Android NOT RUN** | P1: all 4 `sha256` sites in `sovereign_veritas/` hash `canonical_json(...)` or raw artifact bytes, and a non-ASCII record's digest is the canonical one. P2 is not run. Harness digests in `tools/` use their own `json.dumps`; they are experiment digests, not evidence records |
| **S2** `.gitattributes` protects package signatures and witness logs | **SUPPORTED as stated** | P3: 19 of 19 such files are `-text`. **Gap beyond it (ours):** `docs/external/*.md`, whose sha256 is recorded, were unprotected (P4). **F1** closes it |
| **S3** non-repudiation "strictly enforced" | **NOT SUPPORTED as worded** | The signatures are real: P5, 8 of 8 Ed25519 SSH signatures verify; P6, a one-byte change breaks one. But checking them is **opt-in** (P7): `consumer.py` accepted a package with no signature check, and `verify_package.py` exits 0 reporting `authenticity=NOT_PROVEN`. The repository says this itself, so the overstatement is the report's, not the code's |

**VERDICT 6 of 6 as registered; P2 not run.** The sabotage control refutes P6 and exits 1.

## Proposal (Chad Holland's decision; not done)

Should `consumer.py` (and any acting consumer) **require** `--signature`, refusing when it is absent?
That would make S3 true as worded. It changes the consumer contract, so it is not done here.

## Next unrun test

P2, P5 and P7 on the S25 under Termux.

## Addendum 2026-10-09: P7 superseded by P-001 W1 (additive; the record above is unchanged)

P7 ("signatures are opt-in") HELD as registered and is kept above exactly as recorded. P-001 W1
(frozen acceptance `coordination/p001/ACCEPTANCE.md` @ `1c16e66`) made `--signature`,
`--allowed-signers` and `--identity` required for `tools/consumer.py accept`. On code that includes W1,
the probe's default mode checks the fixed behaviour instead: every package run without a signature is
refused as an argparse usage error (exit 2) and none is accepted, while `verify_package.py --legacy` still
inspects the unsigned file as `authenticity=NOT_PROVEN`. `--pre-w1` keeps the original P7 expectation and
can only reproduce it on code from before W1. Added by Claude (Opus 5.5) under Chad Holland's direction.
