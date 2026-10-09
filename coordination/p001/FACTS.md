# P-001 facts: current behaviour on main 709da9e (run by Claude in a Linux container, 2026-10-09; NOT on the S25)

```
$ python tools/consumer.py accept evidence/sv_package_7548237bceca.json --witness-log witness/packages.log --state STATE.json   # no --signature
PASS  consumer                           first use; anchor now 6 entries
CONSUMER  ACCEPTED  (state updated)
exit 0

$ grep -c 44823d0f evidence/sv_package_7548237bceca.json   # is the contract digest recorded in the package?
0

$ python tools/gate_contract.py --check kernel | tail -2
conformance digest 44823d0ff707213ae8bc310ed8b21e135f8e742fd8834e8f9474743d3a250628  (expected 44823d0ff707213ae8bc310ed8b21e135f8e742fd8834e8f9474743d3a250628)
VERDICT  CONFORMS
PR5 all-DEFAULTED: replay ('ALLOW', []) | failed checks none
  PR5   HELD
VERDICT  6 of 6 as registered (PR0b: run --sabotage, expect exit 1)
```

Earlier sources: PR #36 (PR-1, all-DEFAULTED gets ALLOW), PR #39 (IM map: M5 unsigned accepted, M6 no rule binding, M8, M9), PR #38 (RK-2 reserved keys).

Open older PRs that touch the same ground: #54 PV-1 (is an OPERATOR tag evidence of a declaration? confirmed gap), #55 AMB-1 (how much of the Gate the vectors pin down). Not part of P-001 unless the scope phase adds them.
