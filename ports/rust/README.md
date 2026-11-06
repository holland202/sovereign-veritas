# svgate (Rust)

A Rust port of the Sovereign Veritas Gate contract `sv.gate/0`, written from [`CONTRACT.md`](../../CONTRACT.md)
only, using the standard library alone. Registered and reported as C7 in
[`docs/GATE_CONTRACT.md`](../../docs/GATE_CONTRACT.md).

```
cd ports/rust && cargo build --release && cd ../..
python tools/gate_contract.py --check-command ports/rust/target/release/svgate
```

Expected: `VERDICT  CONFORMS` with conformance digest `44823d0f…0628`. Self-tested: written by Claude
(Anthropic, Opus 5.5) at Chad Holland's direction, not independently validated.
