# STD-1 results: what the AAP conformance suite pins, checked by removing its verifier's checks

Registration: [`STD1_PREREG.md`](STD1_PREREG.md), committed alone at `f51e060` before the probe existed.
Target: `opena2a-standards/aap-conformance` at `95580cd`; `verifiers/python/verify.py` sha256
`478c32be5880aab354247c6d5c1bad7092135299f023de200c073e63be1cab49`. Linux x86_64 container, Python 3,
`cryptography` 50.0.2, `dilithium-py` 1.4.0, Node v22.22.0. Not run on the S25.

Drafted by Claude (Opus 5.5), which also wrote and ran the harness, at Chad Holland's direction. Chad has not
reviewed it line by line. Nothing has been filed upstream.

## What went wrong, first

- **P3 is REFUTED.** 28 of 54 reject sites survive removal. Most of them fall outside the list of things the
  suite's README says it does not verify.
- **The registration was wrong about one fact.** It named "the single `BAD_SIGNATURE` site". There are two,
  one for each token form. The harness control was changed before the registered run to use the compact-form
  site (line 828), since the fixture it checks is a compact token. That was a deviation, made after a
  `COULD NOT RUN` and before any mutant was judged.
- **SURVIVED does not mean fail-open.** It means no fixture fails when that one check is removed. A later
  check may still reject the token. Only one survivor (line 622) was followed up to show the token is
  actually accepted. That follow-up was post-hoc, not registered.
- **Self-tested.** The harness's author also judged the results.

## Outcome

| ID | Registered prediction | Result |
|---|---|---|
| P1 | both reference verifiers: `43 pass, 0 fail (43 fixtures)` | **HELD** (Python and Node, verbatim below) |
| P2 | harness control: unmutated 0 failing; signature check removed → `cgt-compact-bad-signature` fails | **HELD** (after the deviation above). Under `--sabotage` the control fails and the harness exits 1 |
| P3 | survivors exist, and all of them are in the README's "implemented ... not pinned" scope | **REFUTED.** 28 survive. At most 3 are arguably in the disclosed scope |
| P4 | no fixture kills more than half of the killed sites | **HELD.** No fixture kills more than 1 of 24 |

Raw output: [`results/std1/mutation_run.txt`](../results/std1/mutation_run.txt). The final lines, verbatim:

```
TOTAL    54 sites: 24 killed, 2 crashed only, 28 survived
SPREAD   most kills by one fixture: 1 of 24 (cgt-compact-crit-header.json)
```

P1, verbatim: Python `summary: 43 pass, 0 fail (43 fixtures)`; Node `summary: 43 pass, 0 fail (43 fixtures)`.

Under the registration, "crashed only" counts as killed (the verifier exits non-zero): 26 killed, 28 survived.

## The 28 survivors

| Group | Lines | In the README's "does not verify" list? |
|---|---|---|
| Malformed token, header or payload (base64url, segment count, non-object JSON, missing `alg`/`typ`/`kid`) | 155, 221, 230, 237, 240, 815, 818, 834, 836, 844, 849, 853, 899, 901 | No |
| `UNKNOWN_KEY` (kid not in the key set; kid for another suite) | 242, 246 | No |
| Unknown `fixtureType` (a harness input, not a spec rule) | 508 | No |
| `session_label` at a level below 3 (§6.4) | 532 | No |
| `cnf` details: proof key not Ed25519, `cnf.jwk` not Ed25519, invalid public key | 600, 604, 618 | No |
| **Presenter proof signature does not verify (§4.6)** | **622** | **No. The README says the suite "pins key binding (RFC 7638 thumbprint against `cnf`) and the signature over the challenge"** |
| Delegation: act chain not continued (751); delegator token invalid (965) | 751, 965 | No |
| Delegating past a terminal (`max_depth` 0) delegator (§5.3) | 783 | No. A fixture exists for this rule, `da-compact-past-terminal-depth`, but it still passes with the check removed (below) |
| Unsupported presentation binding (597); challenge under 16 bytes (612); orphan `authorization_details` entry (728) | 597, 612, 728 | Arguably yes (other §6.8 bindings, challenge channel properties, §5.4 relations not exercised) |

### Line 622: a verifier that skips proof of possession passes the whole suite

With line 622 removed, all 43 fixtures still pass. I added one fixture outside the suite: the suite's own
`cgt-compact-fgc-valid` with one bit of the presenter proof's signature flipped (same key, same thumbprint), and
an expectation copied from `cgt-compact-cnf-mismatch` (`REJECT`, `CNF_MISMATCH`, reason contains `cnf`). The
fixture is [`results/std1/std1_cnf_bad_proof_signature.json`](../results/std1/std1_cnf_bad_proof_signature.json)
(sha256 `2ac95d9e66a9ee4c5c7187d3e6c0b2b431b260a16ced0b83de84176f8235eb87`). Output, verbatim:

```
PY UNMUTATED         exit 0 | observed: REJECT[CNF_MISMATCH: presenter proof signature does not verify under the cnf-bound key (AAP-SPEC §4.6)]
PY SITE 622 REMOVED  exit 1 | observed: ACCEPT
NODE UNMUTATED       exit 0 | observed: REJECT[CNF_MISMATCH: presenter proof signature does not verify under the cnf-bound key (AAP-SPEC §4.6)]
```

Both reference verifiers are correct. The gap is in the suite: no fixture would catch an independent
implementation that checks the thumbprint but never verifies the signature, and that implementation would
accept anyone who copies the presenter's public key. The existing `cnf-mismatch` fixture uses a different key,
so the thumbprint check (line 606) rejects it before the signature is reached.

### Line 783: a fixture that passes for another reason

`da-compact-past-terminal-depth` pins `NOT_ATTENUATED` with the reason containing `max_depth`. With the
terminal-delegator check removed, the remaining-depth check rejects the same token with the same category
and a reason that also contains `max_depth`:

```
removed:   REJECT[NOT_ATTENUATED: max_depth 0 exceeds the delegator's remaining depth -1 (AAP-SPEC §5.3)]
unmutated: REJECT[NOT_ATTENUATED: the delegator is a terminal delegation (max_depth 0); delegating past it is not permitted (AAP-SPEC §5.3)]
```

The token is still rejected, so this is not a security gap. But the README says a negative fixture fails a
verifier that skips "that verification step (and only that step)", and for this fixture that isn't true: the
pinned category and reason substring can't tell the two checks apart.

## What this does not show

- Whether any implementation in use skips these checks.
- Anything about the Node verifier's survivors. That is the unrun test below.
- Anything at the action boundary (scenarios 4, 5 and 8 of the registration). The suite tests token wire form,
  which it says itself.

## Next unrun test

Run the mutation harness against the Node verifier and compare survivor sets (registered in `STD1_PREREG.md`).
