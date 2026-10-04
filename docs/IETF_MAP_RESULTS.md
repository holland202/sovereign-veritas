# IM results: sovereign-veritas against draft-krausz-verification-state-03: 8 conform, 4 differ, 1 not covered, 1 beyond the draft

Registration: `docs/IETF_MAP_PREREG.md`, commit 8a2805b (pushed 2026-10-04 06:00 -0500), before `tools/ietf_map.py`
existed. Baseline main 2c825b8. Linux container. **NOT VALIDATED on the S25.** Claude-assisted (Claude Opus 5.5).
Chad Holland directed it. He has not reviewed this text line by line. The draft is one author's **individual,
Informational** Internet-Draft, not an IETF standard. Its requirements were read through a fetch tool and have not
been checked against the draft by a person.

## What failed (first)
1. **The registered anti-vacuity control failed.** It was a bad design, not a code result. `--sabotage` supplied the
   genuine signature in M5 and was registered to make the probe exit 1. It exited 0. M5 is classified by whether
   the consumer *accepts*, and a correctly signed package is accepted too, so this control could never fail. That
   is the vacuous-check pattern this repository warns about, in our own probe. The failure is kept as registered.
2. **A correct control was run afterwards and is unregistered.** In a throwaway copy, `tools/consumer.py` was
   patched to refuse unsigned packages, and the probe was run unchanged. M5 flips to CONFORMS and the probe exits 1
   (13 of 14), so the probe *can* report CONFORMS where DIFFERS was predicted. Output is below. Because it was
   designed after seeing the failure, it is weaker evidence than a registered control.
3. The predictions were not blind. Most follow from reading the code and from earlier results (JG-2 P7, PR-1, PX).

## Scorecard (the registered run)
| ID | Draft requirement | Our behaviour | Result |
|---|---|---|---|
| M1 | missing receipt halts | consumer: COULD NOT LOOK, exit 2 | CONFORMS |
| M2 | malformed receipt halts | consumer: exit 2 | CONFORMS |
| M3 | stale or expired halts | consumer with the witness log: a package 2 behind is refused | CONFORMS |
| M4 | signature-invalid halts | wrong signature refused | CONFORMS |
| M5 | an unverifiable (unsigned) receipt halts | **unsigned package ACCEPTED, exit 0** | **DIFFERS** |
| M6 | bind to a content-addressed decision mapping | **package carries no contract digest or rule-version hash** | **DIFFERS** |
| M7 | only "verified" acts | INSUFFICIENT_EVIDENCE, missing and unknown give DEFER, REFUSE, REFUSE | CONFORMS |
| M8 | an un-probed adversarial state halts | **PASS with no adversarial check gives ALLOW** | **DIFFERS** |
| M9 | "anything ambiguous halts" (principle; the normative text names error conditions only) | **runtime fields nobody supplied (defaults) give ALLOW** | NOT COVERED, contrary to the principle |
| M10a | an environment HALT is not masked by a verification ACT | PASS with thermal hot gives DEFER | CONFORMS |
| M10b | environment evaluated before verification | **verification is evaluated first** (REFUTED with hot reports only `verification_refuted`); the outcome still halts | **DIFFERS (order only)** |
| M11 | an instrument failure is distinct from an evaluated result | malformed gives exit 2, tampered gives exit 1 | CONFORMS |
| M12 | the relying party recomputes the decision locally | `gate_replay` passes | CONFORMS |
| M13 | (the draft specifies no nonce or jti replay protection) | the consumer refuses the same package a second time | BEYOND THE DRAFT |

## What the data says, in order of usefulness
1. **M5 is a one-line policy away.** The post-hoc copy shows that refusing unsigned packages at the consumer turns
   M5 to CONFORMS without changing anything else. The cost is that every unsigned workflow (the quick start,
   tests, first use) needs a key. That is Chad's decision.
2. **M6 now has two independent pointers.** PX (Perplexity attack, `docs/PX_RESULTS.md`) said recording the check's
   code digest needs `sv.package/1`. This draft makes binding to a content-addressed mapping a halt condition. The
   conformance digest `44823d0f...0628` exists but is not in the package.
3. **M9 is the PR-1 / PR-2 question again, from an outside text.** The draft's principle "Anything ambiguous halts;
   Implementations MUST NOT default to act under any error condition" argues for PR-2 (DEFAULTED blocks ALLOW).
   Strictly, a default isn't one of the error conditions it names, so this is support, not a violation.
4. **M8 is a design difference worth stating, not necessarily fixing.** Requiring an adversarial check before
   every ALLOW would change the Gate's contract. The draft treats "not checked" as "not resilient".
5. **M10b changes only which reason is reported first.** No outcome differs on the tested case. Low priority.
6. **Where SV goes further: M13.** The consumer's replay refusal and the witness log's latest-only freshness have
   no counterpart in the draft. That is something specific to offer its author.

## Output, registered run (verbatim)
```
ID    predicted    observed     detail
M1    CONFORMS     CONFORMS     exit 2: COULD NOT LOOK: FileNotFoundError: [Errno 2] No such file or directory
M2    CONFORMS     CONFORMS     exit 2: COULD NOT LOOK: JSONDecodeError: Expecting ',' delimiter: line 1 colum
M3    CONFORMS     CONFORMS     exit 1: CONSUMER  REFUSED  (state unchanged)
M4    CONFORMS     CONFORMS     exit 1: CONSUMER  REFUSED  (state unchanged)
M5    DIFFERS      DIFFERS      exit 0 with no signature: CONSUMER  ACCEPTED  (state updated)
M6    DIFFERS      DIFFERS      contract digest in package: False; mapping-like keys: ['python_version']
M7    CONFORMS     CONFORMS     INSUFFICIENT_EVIDENCE/missing/unknown -> ['DEFER', 'REFUSE', 'REFUSE']
M8    DIFFERS      DIFFERS      PASS, no adversarial check -> ALLOW
M9    NOT COVERED  NOT COVERED  compute_budget='available' power_status='stable' (defaults, nobody supplied them) -> ALLOW
M10a  CONFORMS     CONFORMS     PASS + thermal hot -> ('DEFER', ('runtime_not_healthy',))
M10b  DIFFERS      DIFFERS      REFUTED + thermal hot -> ('REFUSE', ('verification_refuted',))
M11   CONFORMS     CONFORMS     malformed -> exit 2 (could not look); tampered decision -> exit 1 (evaluated)
M12   CONFORMS     CONFORMS     PASS  gate_replay                        replayed DEFER ['runtime_not_healthy']
M13   BEYOND       BEYOND       first accept exit 0, second exit 1: CONSUMER  REFUSED  (state unchanged)

mode: normal
observed: CONFORMS 8, DIFFERS 4, NOT COVERED 1, BEYOND 1
VERDICT  14 of 14 as registered
exit 0
```

## Output, `--sabotage` (registered control, failed as described above; verbatim)
```
ID    predicted    observed     detail
M1    CONFORMS     CONFORMS     exit 2: COULD NOT LOOK: FileNotFoundError: [Errno 2] No such file or directory
M2    CONFORMS     CONFORMS     exit 2: COULD NOT LOOK: JSONDecodeError: Expecting ',' delimiter: line 1 colum
M3    CONFORMS     CONFORMS     exit 1: CONSUMER  REFUSED  (state unchanged)
M4    CONFORMS     CONFORMS     exit 1: CONSUMER  REFUSED  (state unchanged)
M5    DIFFERS      DIFFERS      exit 0 with signature (SABOTAGE): CONSUMER  ACCEPTED  (state updated)
M6    DIFFERS      DIFFERS      contract digest in package: False; mapping-like keys: ['python_version']
M7    CONFORMS     CONFORMS     INSUFFICIENT_EVIDENCE/missing/unknown -> ['DEFER', 'REFUSE', 'REFUSE']
M8    DIFFERS      DIFFERS      PASS, no adversarial check -> ALLOW
M9    NOT COVERED  NOT COVERED  compute_budget='available' power_status='stable' (defaults, nobody supplied them) -> ALLOW
M10a  CONFORMS     CONFORMS     PASS + thermal hot -> ('DEFER', ('runtime_not_healthy',))
M10b  DIFFERS      DIFFERS      REFUTED + thermal hot -> ('REFUSE', ('verification_refuted',))
M11   CONFORMS     CONFORMS     malformed -> exit 2 (could not look); tampered decision -> exit 1 (evaluated)
M12   CONFORMS     CONFORMS     PASS  gate_replay                        replayed DEFER ['runtime_not_healthy']
M13   BEYOND       BEYOND       first accept exit 0, second exit 1: CONSUMER  REFUSED  (state unchanged)

mode: SABOTAGE (M5 given the genuine signature)
observed: CONFORMS 8, DIFFERS 4, NOT COVERED 1, BEYOND 1
VERDICT  14 of 14 as registered
exit 0
```

## Output, post-hoc control (unregistered: consumer patched in a throwaway copy to refuse unsigned packages; verbatim)
```
ID    predicted    observed     detail
M1    CONFORMS     CONFORMS     exit 1: CONSUMER  REFUSED  (unsigned)
M2    CONFORMS     CONFORMS     exit 1: CONSUMER  REFUSED  (unsigned)
M3    CONFORMS     CONFORMS     exit 1: CONSUMER  REFUSED  (state unchanged)
M4    CONFORMS     CONFORMS     exit 1: CONSUMER  REFUSED  (state unchanged)
M5    DIFFERS      CONFORMS     [NOT AS REGISTERED] exit 1 with no signature: CONSUMER  REFUSED  (unsigned)
M6    DIFFERS      DIFFERS      contract digest in package: False; mapping-like keys: ['python_version']
M7    CONFORMS     CONFORMS     INSUFFICIENT_EVIDENCE/missing/unknown -> ['DEFER', 'REFUSE', 'REFUSE']
M8    DIFFERS      DIFFERS      PASS, no adversarial check -> ALLOW
M9    NOT COVERED  NOT COVERED  compute_budget='available' power_status='stable' (defaults, nobody supplied them) -> ALLOW
M10a  CONFORMS     CONFORMS     PASS + thermal hot -> ('DEFER', ('runtime_not_healthy',))
M10b  DIFFERS      DIFFERS      REFUTED + thermal hot -> ('REFUSE', ('verification_refuted',))
M11   CONFORMS     CONFORMS     malformed -> exit 2 (could not look); tampered decision -> exit 1 (evaluated)
M12   CONFORMS     CONFORMS     PASS  gate_replay                        replayed DEFER ['runtime_not_healthy']
M13   BEYOND       BEYOND       first accept exit 0, second exit 1: CONSUMER  REFUSED  (state unchanged)

mode: normal
observed: CONFORMS 9, DIFFERS 3, NOT COVERED 1, BEYOND 1
VERDICT  13 of 14 as registered
exit 1
```

## Door (unrun)
Fix the probe's own control (register a control that changes behaviour, as the post-hoc one did) before this probe
is pinned in CI. Then consider M5 and M6 as registered changes.
