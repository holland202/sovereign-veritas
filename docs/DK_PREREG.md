# DK registration: duplicate JSON keys and non-finite literals in evidence packages (nothing run under this registration)

Status: registration only. Written 2026-10-03, before `tools/dk_probe.py` exists and before any verifier change.
Claude-assisted (Claude Opus 5.5). Chad Holland gave direction ("let's pick up where you left off"); he has not
reviewed this text.

## Origin, and what was run before this (disclosed, C-EXPLORE)
An external review (docs/EXTERNAL_REVIEW_2026-10-03.md) recommended specifying canonical serialization. One
unregistered run on one package (`evidence/sv_package_118a02b75646.json`) is recorded there: a second `"decision"`
key placed **before** the real one verified CONSISTENT (exit 0), because Python's `json.loads` keeps the last
duplicate and the package digest is computed over the parsed object. The same key placed **after** gave exit 1
(4 checks failed). A `NaN` literal gave exit 1 (2 checks failed). That run informs K1, K2 and K5 below; those
three are therefore not blind. Everything else here has not been run.

## The change under test (not yet made)
`tools/verify_package.py::loads_bounded` will reject (raise ValueError, so the verifier prints COULD NOT LOOK and
exits 2):
- any JSON object with a repeated key (`object_pairs_hook`), at any depth, including embedded artifacts;
- the non-standard literals `NaN`, `Infinity`, `-Infinity` (`parse_constant`).
`tools/consumer.py` will parse packages with the verifier's `loads_bounded` instead of its own `json.loads`.

## Cells (each applied to all 8 packages in `evidence/`, by text edits on the original bytes)
| cell | edit |
|---|---|
| K0 | none (control) |
| K1 | a second top-level `"decision"` key, value `{"decision": "REFUSE", "reasons": ["planted"]}`, inserted **before** the real one |
| K2 | the same planted key appended **after** the last top-level key |
| K3 | inside `gate_inputs`, a duplicate of its first key with value `"planted"`, inserted **before** the real one |
| K4 | an exact duplicate (same key, same value) of the top-level `"schema"` member, inserted before it (harmless meaning, still a duplicate) |
| K5 | top-level member `"x_nan": NaN` added |
| K6 | top-level member `"x_inf": Infinity` added |

## Predictions (verifier exit code; 0 CONSISTENT, 1 checks failed, 2 COULD NOT LOOK)
| ID | Prediction | conf. |
|---|---|---|
| DK1 | **Before the change:** K1 and K3 exit 0 in 8/8 packages (the planted first value is invisible); K4 exits 0 in 8/8; K0 exits 0 in 8/8 | K1 0.9, K3 0.7, K4 0.9 |
| DK2 | **Before the change:** K2 exits 1 in 8/8; K5 and K6 exit 1 in 8/8 (an unknown top-level key fails `schema_closed`) | K2 0.9, K5/K6 0.8 |
| DK3 | **After the change:** K1–K6 exit 2 in 8/8; K0 exits 0 in 8/8 | 0.9 |
| DK4 | **Regression after the change:** `pytest` passes with the same count as before the change; `tools/nonfinite_probe.py` still reports 0 FAIL-OPEN and 0 CRASH over 8 packages | pytest 0.9, nonfinite 0.6 |
| DK5 | **Cost, stated not hidden:** K4 is refused after the change. A semantically harmless file is rejected. This is the intended strictness (reject ambiguous input rather than normalize it) | 0.9 |
| DK6 | **Anti-vacuity:** `--sabotage` (the probe swaps the strict parser for the old `json.loads` inside the loaded verifier) reproduces the DK1 pattern, so the probe exits 1 | 0.9 |

The "before" values are measured by the probe's `--baseline` mode on the unchanged tree and recorded in the
results. The pinned outcome is the "after" run.

## What it cannot show
Which consumer parsers in other languages keep the first duplicate (the cross-language risk is argued, not
measured). Unicode normalization, `-0`, very large integers, null-vs-absent and size limits are not tested here.

## Door (M15)
A cross-language parse-differential test (Go `encoding/json` vs Python) on the same K1–K6 files. Unregistered.
