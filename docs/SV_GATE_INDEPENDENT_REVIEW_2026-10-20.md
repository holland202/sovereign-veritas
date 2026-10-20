# Independent `sv.gate/0` implementation: bounded conformance review

**Status:** local review draft; not a security validation or production claim.

## Source and independence

Public base revision: `d3a9a881c92413cb63a279434405e0412ef443f6`. Contract: `CONTRACT.md`, `sv.gate/0`, SHA-256 `b160ab2c09294c72e01d72804bc8e19277ed2faca160e63b280aff1bb2354163`. Published vector file SHA-256 `4534d15d348e54a29897677234fd3c8b28984fd836ea855dff2fafc4377edf68`; checker SHA-256 `14b7dcf901263d9acfdc573382c80957fe46464c434cf19bc8941961bbf8021a`.

`ports/python_independent/independent_gate.py` was written from the public contract. The reference kernel and verifier decision code were not opened, imported, or called. The program imports only Python standard-library modules and reads/writes the published JSON-lines protocol. This process evidence supports implementation independence, although it cannot prove absence of shared misunderstandings of the written rules.

## Exact reproducibility

Observed on macOS 27.0.1 arm64, CPython 3.14.5 (`/usr/local/bin/python3`). From repository root:

```sh
python3 tools/gate_contract.py --check-command python3 ports/python_independent/independent_gate.py
python3 ports/python_independent/boundary_cases.py python3 ports/python_independent/independent_gate.py
```

The published checker exited **0**, reported **4,690 vectors**, digest `44823d0ff707213ae8bc310ed8b21e135f8e742fd8834e8f9474743d3a250628` and `VERDICT  CONFORMS`. The independently derived boundary runner exited **0**: **22/22** decision cases passed, and three malformed/unsupported line inputs each produced exit **2**. The retained local evidence package contains exact stdout, stderr, exit files, commands, environment and stream hashes. A deliberately incorrect always-ALLOW candidate was also checked; the checker exited **1** with **4,675/4,690** mismatches.

Source SHA-256: `independent_gate.py` `015924869d4e1b75175e2a0d26e38cea6bd94a8072dc6eef1198b259317ae6b0`; `boundary_cases.py` `8fb8417991871c4df85c3282cc367339962b2ea922cee54c0a0ae457f0f1acbf`.

## Scope gaps and negative findings

The contract has no expiry or revocation field. With `authorized=true`, hand-derived cases adding a past `expires_at` or `revoked=true` still returned `ALLOW`; `authorized=false` returned `REFUSE`. Extra input members are ignored under the documented contract. This is a contract-scope limitation, not a finding that another upstream authorization layer fails. The rule-2 fallback is unreachable under today's status vocabulary, as `CONTRACT.md` records. The contract does not specify a Gate decision for wrong-type containers or malformed JSON; this runner uses process exit 2, not an ALLOW decision, for those unsupported inputs. No contradiction with the documented decision rules was reproduced in the tested cases.

Passing published vectors establishes agreement on those vectors, not independent security correctness, live effect safety, authenticity of upstream records, or production readiness.

## Attribution

OpenAI Codex authored this standalone implementation, boundary runner, and review report at Putluru Sandeep's direction. Human code and evidence review remains pending. The proposed contribution is offered for review under the repository's MIT contribution terms, subject to contributor approval before publication.
