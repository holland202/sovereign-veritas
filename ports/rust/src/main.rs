//! rust_gate: an independent implementation of the `sv.gate/0` Gate contract.
//!
//! stdin:  one JSON case per line, {"id": ..., "input": {...}}
//! stdout: one line per case, {"id": ..., "decision": ..., "reasons": [...]}
//! `--digest`: also print the conformance digest (CONTRACT.md) to stderr at the end.
//! A malformed line is fatal (exit 2): the program never guesses a decision for it.

mod gate;
mod json;
mod pyfmt;
mod sha256;

use std::io::{BufRead, Write};

fn main() {
    let want_digest = std::env::args().skip(1).any(|a| a == "--digest");
    let stdin = std::io::stdin();
    let stdout = std::io::stdout();
    let mut out = std::io::BufWriter::new(stdout.lock());
    let mut canon = String::from("[");
    let mut n = 0usize;
    for (lineno, line) in stdin.lock().lines().enumerate() {
        let line = match line {
            Ok(l) => l,
            Err(e) => fail(&format!("line {}: read error: {e}", lineno + 1)),
        };
        if line.trim().is_empty() {
            continue;
        }
        let case = json::parse(&line)
            .unwrap_or_else(|e| fail(&format!("line {}: bad JSON: {e}", lineno + 1)));
        if !matches!(case, json::Value::Obj(_)) {
            fail(&format!("line {}: case is not an object", lineno + 1));
        }
        let id = case.get("id").cloned().unwrap_or(json::Value::Null);
        let input = case
            .get("input")
            .unwrap_or_else(|| fail(&format!("line {}: no input", lineno + 1)));
        let d = gate::decide(input);

        let reasons = json::Value::Arr(d.reasons.iter().map(|r| json::Value::Str(r.clone())).collect());
        let mut s = String::from("{\"id\":");
        json::dumps(&id, false, &mut s);
        s.push_str(",\"decision\":");
        json::dump_str(d.decision, &mut s);
        s.push_str(",\"reasons\":");
        json::dumps(&reasons, false, &mut s);
        s.push('}');
        writeln!(out, "{s}").unwrap_or_else(|e| fail(&format!("write error: {e}")));

        if want_digest {
            if n > 0 {
                canon.push(',');
            }
            let triple = json::Value::Arr(vec![id, json::Value::Str(d.decision.to_string()), reasons]);
            json::dumps(&triple, true, &mut canon);
        }
        n += 1;
    }
    out.flush().unwrap_or_else(|e| fail(&format!("write error: {e}")));
    if want_digest {
        canon.push(']');
        eprintln!("cases {n}");
        eprintln!("conformance_digest {}", sha256::hex(canon.as_bytes()));
    }
}

fn fail(msg: &str) -> ! {
    eprintln!("rust_gate: {msg}");
    std::process::exit(2);
}
