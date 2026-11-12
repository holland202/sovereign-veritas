# StegVerse Cover for Sovereign Veritas — Public Reproduction Package

Prepared for Chad Holland (holland202/sovereign-veritas), at his request
(2026-11-12): the covering work published inspectably — source, reproduction
instructions, and raw test outputs — rather than as an executable bundle
from a Drive link. Until independently reproduced, all results herein are
**CONTRIBUTOR REPORTED** (Chad's classification, which matches our own
grading: the suite is author-CONFORMANT and awaits non-author verification).

## Pins

- Upstream repository: `holland202/sovereign-veritas`
- Upstream commit (all runs below): `13c663b3a3b058b7170fd3628325c1361112d07d`
- Cover suite: Sovereign Veritas Covering Suite GEN 01,
  ProjectID LINKEDIN-SOVEREIGN-VERITAS-EVAL (UNFUNDED introductory specimen)
  - Manifest SHA-256: `d6dd92ede0e520cfd82094c098244adbb23722973892daa4c34d4cac2beae7da`
  - Suite zip SHA-256: `c473c4bb7a46e528bf788aa650c064413a91ecc13c76740a557cbf6cf87776b7`

## Contents

- `cover/sv_transition_cover/` — the covering layer source (Python).
  It wraps the upstream executor; the upstream core is **unmodified**.
- `cover/run_cover_tests.py` — the cover's seven registered tests.
- `docs/ASSESSMENT__01.md` — the abilities-first assessment of Sovereign
  Veritas against its own registrations (findings C-1…C-4, XB-1, EO-1/EO-2).
- `docs/EXPLANATION__01.md` — what was built and why, in plain terms.
- `raw-outputs/` — unedited outputs of the runs below, captured 2026-11-12.

## Reproduce

```bash
git clone https://github.com/holland202/sovereign-veritas
cd sovereign-veritas
git checkout 13c663b3a3b058b7170fd3628325c1361112d07d
python3 -m venv .venv && .venv/bin/pip install -e . pytest

# upstream, as registered:
.venv/bin/python tools/demo_30s.py                                  # DEMO PASS
.venv/bin/python tools/execution_boundary_probe.py --expect-fix      # 8 of 8 as registered
.venv/bin/python tools/eo1_probe.py                                  # 5 of 5 as registered
.venv/bin/python -m pytest tests/test_execution_boundary.py \
    tests/test_idempotency.py tests/test_effect_observation.py -q    # 4 + 23 + 6 passed

# the cover (expects the upstream package importable, as installed above):
.venv/bin/python run_cover_tests.py                                  # COVER VERDICT PASS - 7/7
```

Expected results are the verdict lines above; the captured originals are in
`raw-outputs/` for byte-level comparison. Findings exchange: upstream
Issue #79, per Chad's designation.

## Standing notes

- The cover accounts for the subject's registered error surface (pair
  failures, UNKNOWN holds, unobserved effects); it does not modify, patch,
  or replace any upstream file.
- Five establishment slots in the suite remain the author's to fill
  (thresholds, observer wiring, and related authority facts). Nothing in
  this package fills them on his behalf.
