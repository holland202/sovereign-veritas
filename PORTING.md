# Porting between the v0.2 line (this repo) and the v0.3 line

Two lines of Sovereign Veritas exist: this public repo (v0.2.x, MIT, maintenance) and a private development
repo (v0.3, BSL 1.1). Both kept doing research after they split on 2026-10-16, and for 27 days neither carried
the other's fixes: this repo's SEC-005 reservation lock (2026-11-02) reached the 0.3 store only on 2026-11-12,
found by a manual cross-repo comparison rather than by any process either repo runs. This file is that process.

## The rule

Every fix or finding that lands on either line gets an explicit **ported / won't-port** decision recorded in the
table below, in the same PR where it lands or the next working session. "Won't port" is a fine answer; silence is
the defect. A row's decision names the other line's commit or PR when ported, and the reason when not.

## Decisions

| Date | Item (where it landed) | Decision for the other line |
|---|---|---|
| 2026-11-12 | SEC-004 race + SEC-005 lock (this repo, 2026-10-11 / 11-02) | **PORTED** to 0.3 as SD-13 after a registered probe reproduced the race there (`SECURITY_FAIL`, 6 of 6) |
| 2026-11-12 | BT-002 gap pins (this repo) | **PORTED** to 0.3; all 15 pass unmodified, two spot mutants re-killed |
| 2026-11-12 | OVF-1 oversized-floor fix (this repo) vs SD-6 D9 (0.3) | **WON'T PORT** either way — both fail closed; the verdict difference (DEFER vs REFUSE `malformed_input`) is deliberate and recorded in 0.3's `MIGRATION_0.2_TO_0.3.md` |
| 2026-11-12 | EO-2 effect observation (this repo) vs EF-1 `effects.py` (0.3) | **OPEN** — parallel answers to the same EO-1 gap; EF-1 is 0.3's effects story; EO-2's observer-trust finding (P5) not yet reflected in 0.3 (recorded in 0.3's LINEAGE) |
| 2026-11-12 | SD-1..SD-12 safe-defaults hardening, RT-1/RT-2 red team (0.3) | **WON'T PORT** to v0.2 — that is the v0.3 feature line; v0.2 stays maintenance-only |
| 2026-11-12 | Pinned action SHAs + dependabot (0.3's supply-chain setup) | **PORTED** to this repo (this PR) |

## Provenance

File and initial decisions written by Claude (Anthropic, Fable 5) at Chad Holland's direction (2026-11-12,
direction only), from a measured comparison of both repos at `13c663b` (public) and `5eb29f9` (dev).
