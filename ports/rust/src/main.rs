//! svgate: a Rust port of the Sovereign Veritas Gate contract `sv.gate/0`, written from CONTRACT.md only (C7 in
//! docs/GATE_CONTRACT.md). Standard library only.
//!
//! Reads one case per line on stdin, `{"id", "input"}`, and writes one line per case, `{"id", "decision", "reasons"}`.
//! Check it with:
//!
//!     (cd ports/rust && cargo build --release) && \
//!       python tools/gate_contract.py --check-command ports/rust/target/release/svgate
use std::io::{self, BufRead, BufWriter, Write};

// ------------------------------------------------------------------ JSON values

/// A JSON value. Numbers keep their literal text, because the contract distinguishes `3` from `3.0`.
#[derive(Debug, Clone)]
enum V {
    Null,
    Bool(bool),
    Num(String),
    Str(String),
    Arr(Vec<V>),
    Obj(Vec<(String, V)>),
}

impl V {
    /// Member lookup. Python's json keeps the last of duplicate keys, so the last match wins.
    fn get(&self, k: &str) -> Option<&V> {
        match self {
            V::Obj(m) => m.iter().rev().find(|(key, _)| key == k).map(|(_, v)| v),
            _ => None,
        }
    }
    fn is_null(&self) -> bool {
        matches!(self, V::Null)
    }
}

/// "Member is null or absent" (both read as Python's None through .get()).
fn none(v: Option<&V>) -> bool {
    matches!(v, None | Some(V::Null))
}

struct P<'a> {
    s: &'a [u8],
    i: usize,
}

impl<'a> P<'a> {
    fn ws(&mut self) {
        while self.i < self.s.len() && matches!(self.s[self.i], b' ' | b'\t' | b'\n' | b'\r') {
            self.i += 1;
        }
    }
    fn err<T>(&self, m: &str) -> Result<T, String> {
        Err(format!("{m} at byte {}", self.i))
    }
    fn value(&mut self) -> Result<V, String> {
        self.ws();
        match self.s.get(self.i) {
            None => self.err("unexpected end"),
            Some(b'{') => {
                self.i += 1;
                let mut m = Vec::new();
                self.ws();
                if self.s.get(self.i) == Some(&b'}') {
                    self.i += 1;
                    return Ok(V::Obj(m));
                }
                loop {
                    self.ws();
                    if self.s.get(self.i) != Some(&b'"') {
                        return self.err("expected key");
                    }
                    let k = self.string()?;
                    self.ws();
                    if self.s.get(self.i) != Some(&b':') {
                        return self.err("expected ':'");
                    }
                    self.i += 1;
                    let v = self.value()?;
                    m.push((k, v));
                    self.ws();
                    match self.s.get(self.i) {
                        Some(b',') => self.i += 1,
                        Some(b'}') => {
                            self.i += 1;
                            return Ok(V::Obj(m));
                        }
                        _ => return self.err("expected ',' or '}'"),
                    }
                }
            }
            Some(b'[') => {
                self.i += 1;
                let mut a = Vec::new();
                self.ws();
                if self.s.get(self.i) == Some(&b']') {
                    self.i += 1;
                    return Ok(V::Arr(a));
                }
                loop {
                    a.push(self.value()?);
                    self.ws();
                    match self.s.get(self.i) {
                        Some(b',') => self.i += 1,
                        Some(b']') => {
                            self.i += 1;
                            return Ok(V::Arr(a));
                        }
                        _ => return self.err("expected ',' or ']'"),
                    }
                }
            }
            Some(b'"') => Ok(V::Str(self.string()?)),
            Some(b't') if self.s[self.i..].starts_with(b"true") => {
                self.i += 4;
                Ok(V::Bool(true))
            }
            Some(b'f') if self.s[self.i..].starts_with(b"false") => {
                self.i += 5;
                Ok(V::Bool(false))
            }
            Some(b'n') if self.s[self.i..].starts_with(b"null") => {
                self.i += 4;
                Ok(V::Null)
            }
            Some(c) if *c == b'-' || c.is_ascii_digit() => {
                let start = self.i;
                self.i += 1;
                while self.i < self.s.len() && matches!(self.s[self.i], b'0'..=b'9' | b'.' | b'e' | b'E' | b'+' | b'-')
                {
                    self.i += 1;
                }
                Ok(V::Num(String::from_utf8_lossy(&self.s[start..self.i]).into_owned()))
            }
            _ => self.err("unexpected character"),
        }
    }
    fn hex4(&mut self) -> Result<u32, String> {
        let h = self.s.get(self.i..self.i + 4).ok_or("short \\u escape")?;
        let t = std::str::from_utf8(h).map_err(|e| e.to_string())?;
        self.i += 4;
        u32::from_str_radix(t, 16).map_err(|e| e.to_string())
    }
    fn string(&mut self) -> Result<String, String> {
        self.i += 1;
        let mut out: Vec<u8> = Vec::new();
        loop {
            match self.s.get(self.i) {
                None => return self.err("unterminated string"),
                Some(b'"') => {
                    self.i += 1;
                    return String::from_utf8(out).map_err(|e| e.to_string());
                }
                Some(b'\\') => {
                    self.i += 1;
                    let e = *self.s.get(self.i).ok_or("truncated escape")?;
                    self.i += 1;
                    let ch: Option<char> = match e {
                        b'"' => Some('"'),
                        b'\\' => Some('\\'),
                        b'/' => Some('/'),
                        b'b' => Some('\u{8}'),
                        b'f' => Some('\u{c}'),
                        b'n' => Some('\n'),
                        b'r' => Some('\r'),
                        b't' => Some('\t'),
                        b'u' => {
                            let u = self.hex4()?;
                            if (0xD800..0xDC00).contains(&u) && self.s[self.i..].starts_with(b"\\u") {
                                self.i += 2;
                                let l = self.hex4()?;
                                char::from_u32(0x10000 + ((u - 0xD800) << 10) + (l.wrapping_sub(0xDC00) & 0x3FF))
                            } else {
                                Some(char::from_u32(u).unwrap_or('\u{FFFD}'))
                            }
                        }
                        _ => return self.err("bad escape"),
                    };
                    let mut buf = [0u8; 4];
                    out.extend_from_slice(ch.unwrap_or('\u{FFFD}').encode_utf8(&mut buf).as_bytes());
                }
                Some(&c) => {
                    out.push(c);
                    self.i += 1;
                }
            }
        }
    }
}

fn parse(line: &str) -> Result<V, String> {
    let mut p = P { s: line.as_bytes(), i: 0 };
    let v = p.value()?;
    p.ws();
    if p.i != p.s.len() {
        return p.err("extra data");
    }
    Ok(v)
}

fn enc_str(s: &str, out: &mut String) {
    out.push('"');
    for c in s.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if (c as u32) < 0x20 => out.push_str(&format!("\\u{:04x}", c as u32)),
            c => out.push(c),
        }
    }
    out.push('"');
}

// ------------------------------------------------------------------ numbers (CONTRACT.md: rules 10, 11, 13)

/// "An integer is a JSON number written without a fraction or exponent."
fn is_int_lit(n: &str) -> bool {
    !n.contains(['.', 'e', 'E'])
}

/// A JSON number as a double; "an integer too large for a double is +infinity or -infinity".
fn to_f64(n: &str) -> f64 {
    n.parse::<f64>().unwrap_or(f64::NAN)
}

/// An integer literal as (negative, digits without leading zeros); zero is ("0", not negative).
fn int_parts(n: &str) -> (bool, String) {
    let (neg, d) = match n.strip_prefix('-') {
        Some(rest) => (true, rest),
        None => (false, n),
    };
    let d = d.trim_start_matches('0');
    if d.is_empty() {
        (false, "0".to_string())
    } else {
        (neg, d.to_string())
    }
}

/// Plain decimal of an integer literal, as Python's str(int) prints it.
fn int_str(n: &str) -> String {
    let (neg, d) = int_parts(n);
    if neg {
        format!("-{d}")
    } else {
        d
    }
}

/// Compare two non-negative decimal digit strings without leading zeros.
fn cmp_digits(a: &str, b: &str) -> std::cmp::Ordering {
    a.len().cmp(&b.len()).then_with(|| a.cmp(b))
}

/// Exact comparison of two integer literals.
fn cmp_int(a: &str, b: &str) -> std::cmp::Ordering {
    use std::cmp::Ordering::*;
    let (an, ad) = int_parts(a);
    let (bn, bd) = int_parts(b);
    match (an, bn) {
        (false, true) => Greater,
        (true, false) => Less,
        (false, false) => cmp_digits(&ad, &bd),
        (true, true) => cmp_digits(&bd, &ad),
    }
}

/// The exact integer value of an integral finite double, as (negative, digits).
fn f64_exact_int(x: f64) -> (bool, String) {
    let neg = x.is_sign_negative() && x != 0.0;
    let bits = x.abs().to_bits();
    let exp = ((bits >> 52) & 0x7ff) as i32;
    let mut mant = bits & ((1u64 << 52) - 1);
    if exp == 0 {
        return (false, "0".to_string()); // integral subnormal is zero
    }
    mant |= 1u64 << 52;
    let shift = exp - 1075;
    // decimal digits, little-endian
    let mut digits: Vec<u8> = Vec::new();
    let mut m = mant;
    if shift < 0 {
        m >>= -shift; // integral, so no bits are lost
    }
    if m == 0 {
        digits.push(0);
    }
    while m > 0 {
        digits.push((m % 10) as u8);
        m /= 10;
    }
    for _ in 0..shift.max(0) {
        let mut carry = 0u8;
        for d in digits.iter_mut() {
            let v = *d * 2 + carry;
            *d = v % 10;
            carry = v / 10;
        }
        if carry > 0 {
            digits.push(carry);
        }
    }
    let s: String = digits.iter().rev().map(|d| (b'0' + d) as char).collect();
    (neg && s != "0", s)
}

/// Python's numeric value of a JSON number or boolean: an integer (exact) or a double.
enum Numv {
    Int(bool, String),
    Flt(f64),
}

fn numv(v: &V) -> Option<Numv> {
    match v {
        V::Bool(b) => Some(Numv::Int(false, if *b { "1".into() } else { "0".into() })),
        V::Num(n) if is_int_lit(n) => {
            let (neg, d) = int_parts(n);
            Some(Numv::Int(neg, d))
        }
        V::Num(n) => Some(Numv::Flt(to_f64(n))),
        _ => None,
    }
}

fn num_eq(a: &Numv, b: &Numv) -> bool {
    match (a, b) {
        (Numv::Int(an, ad), Numv::Int(bn, bd)) => an == bn && ad == bd,
        (Numv::Flt(x), Numv::Flt(y)) => x == y,
        (Numv::Int(n, d), Numv::Flt(x)) | (Numv::Flt(x), Numv::Int(n, d)) => {
            if !x.is_finite() || x.fract() != 0.0 {
                return false;
            }
            let (fneg, fd) = f64_exact_int(*x);
            fneg == *n && fd == *d
        }
    }
}

/// Python `==` on JSON values: 1, 1.0 and true are equal; containers compare elementwise.
fn py_eq(a: &V, b: &V) -> bool {
    if let (Some(x), Some(y)) = (numv(a), numv(b)) {
        return num_eq(&x, &y);
    }
    match (a, b) {
        (V::Null, V::Null) => true,
        (V::Str(x), V::Str(y)) => x == y,
        (V::Arr(x), V::Arr(y)) => x.len() == y.len() && x.iter().zip(y).all(|(p, q)| py_eq(p, q)),
        (V::Obj(_), V::Obj(_)) => {
            let ka = obj_keys(a);
            let kb = obj_keys(b);
            ka.len() == kb.len() && ka.iter().all(|k| matches!((a.get(k), b.get(k)), (Some(p), Some(q)) if py_eq(p, q)))
        }
        _ => false,
    }
}

fn obj_keys(v: &V) -> Vec<String> {
    let mut ks: Vec<String> = match v {
        V::Obj(m) => m.iter().map(|(k, _)| k.clone()).collect(),
        _ => vec![],
    };
    ks.sort();
    ks.dedup();
    ks
}

/// "Present" means present and truthy in Python's sense.
fn present(v: Option<&V>) -> bool {
    match v {
        None | Some(V::Null) => false,
        Some(V::Bool(b)) => *b,
        Some(V::Num(n)) if is_int_lit(n) => int_parts(n).1 != "0",
        Some(V::Num(n)) => to_f64(n) != 0.0,
        Some(V::Str(s)) => !s.is_empty(),
        Some(V::Arr(a)) => !a.is_empty(),
        Some(V::Obj(m)) => !m.is_empty(),
    }
}

fn is_true(v: Option<&V>) -> bool {
    matches!(v, Some(V::Bool(true)))
}

// ------------------------------------------------------------------ formatting (CONTRACT.md: Formatting)

/// Python's repr of a double: shortest round-trip digits; exponent form when the exponent is below -4 or at
/// least 16; a whole number keeps `.0`.
fn py_repr(x: f64) -> String {
    if x.is_nan() {
        return "nan".into();
    }
    if x.is_infinite() {
        return if x > 0.0 { "inf".into() } else { "-inf".into() };
    }
    if x == 0.0 {
        return if x.is_sign_negative() { "-0.0".into() } else { "0.0".into() };
    }
    let e = format!("{:e}", x.abs()); // shortest round-trip digits, e.g. "1.5e16", "1e-5"
    let (mant, exp) = e.split_once('e').unwrap();
    let exp: i32 = exp.parse().unwrap();
    let digits: String = mant.chars().filter(|c| *c != '.').collect();
    let sign = if x < 0.0 { "-" } else { "" };
    if exp < -4 || exp >= 16 {
        let m = if digits.len() > 1 { format!("{}.{}", &digits[..1], &digits[1..]) } else { digits.clone() };
        return format!("{sign}{m}e{}{:02}", if exp < 0 { '-' } else { '+' }, exp.abs());
    }
    let decpt = exp + 1; // position of the decimal point relative to the digit string
    let body = if decpt <= 0 {
        format!("0.{}{}", "0".repeat((-decpt) as usize), digits)
    } else if digits.len() as i32 <= decpt {
        format!("{}{}.0", digits, "0".repeat((decpt - digits.len() as i32) as usize))
    } else {
        format!("{}.{}", &digits[..decpt as usize], &digits[decpt as usize..])
    };
    format!("{sign}{body}")
}

/// Fixed point with four decimals, rounded correctly from the exact binary value, ties to even.
fn fixed4(x: f64) -> String {
    format!("{:.4}", x)
}

/// Python's str() of a value, for `<parent>` in reasons.
fn py_str(v: &V) -> String {
    match v {
        V::Str(s) => s.clone(),
        V::Bool(b) => if *b { "True".into() } else { "False".into() },
        V::Null => "None".into(),
        V::Num(n) if is_int_lit(n) => int_str(n),
        V::Num(n) => py_repr(to_f64(n)),
        other => format!("{other:?}"), // not reachable from the vectors' documented types
    }
}

// ------------------------------------------------------------------ the Gate (CONTRACT.md: Rules)

const STATUSES: [&str; 6] = ["PASS", "FAIL", "REFUTED", "INSUFFICIENT_EVIDENCE", "NOT_VERIFIED", "UNKNOWN"];

fn str_in(v: Option<&V>, set: &[&str]) -> bool {
    matches!(v, Some(V::Str(s)) if set.contains(&s.as_str()))
}

fn gate(input: &V) -> (&'static str, Vec<String>) {
    let null = V::Null;
    let empty = V::Obj(vec![]);
    let record = input.get("record").unwrap_or(&null);
    let mut defer: Vec<String> = Vec::new();
    macro_rules! refuse {
        ($r:expr) => {
            return ("REFUSE", vec![$r.to_string()])
        };
    }

    // 1
    if !present(record.get("input_digest")) {
        refuse!("evidence_invalid:missing_input_digest");
    }
    // 2
    let verification = record.get("verification");
    let status: &str = match verification {
        None | Some(V::Null) => "NOT_VERIFIED",
        Some(v) => match v.get("status") {
            None | Some(V::Null) => "NOT_VERIFIED",
            Some(V::Str(s)) if STATUSES.contains(&s.as_str()) => *STATUSES.iter().find(|x| **x == s.as_str()).unwrap(),
            Some(_) => "UNKNOWN",
        },
    };
    match status {
        "FAIL" | "NOT_VERIFIED" | "UNKNOWN" => refuse!("verification_not_passed"),
        "REFUTED" => refuse!("verification_refuted"),
        "INSUFFICIENT_EVIDENCE" => defer.push("verification_insufficient_evidence".into()),
        "PASS" => {}
        _ => refuse!("verification_not_passed"),
    }
    // 3
    let cap = match input.get("capability") {
        None | Some(V::Null) => refuse!("capability_missing"),
        Some(c) => c,
    };
    // 4
    if !is_true(cap.get("authorized")) {
        refuse!("capability_not_authorized");
    }
    // 5
    if present(cap.get("parent")) {
        let parent = cap.get("parent").unwrap();
        let registry = match input.get("capability_registry") {
            None | Some(V::Null) => refuse!("capability_parent_requires_registry"),
            Some(r) => r,
        };
        let entry = match parent {
            V::Str(p) => registry.get(p),
            _ => None, // object keys are strings; a non-string parent has no entry
        };
        match entry {
            None | Some(V::Null) => refuse!(format!("capability_parent_missing:{}", py_str(parent))),
            Some(e) if !is_true(e.get("authorized")) => {
                refuse!(format!("capability_parent_not_authorized:{}", py_str(parent)))
            }
            _ => {}
        }
    }
    // 6
    let action = match record.get("action") {
        None | Some(V::Null) => &empty,
        Some(a) => a,
    };
    if present(action.get("capability")) && !py_eq(action.get("capability").unwrap(), cap.get("name").unwrap_or(&null)) {
        refuse!("action_capability_mismatch");
    }
    // 7, 8
    let runtime = input.get("runtime").unwrap_or(&empty);
    let fields: [(&str, &[&str], &[&str]); 3] = [
        ("thermal_status", &["normal", "cool"], &["warning", "high", "hot", "critical", "unsafe"]),
        ("compute_budget", &["available", "constrained", "low"], &["exhausted"]),
        ("power_status", &["stable"], &["unsafe"]),
    ];
    let mut degraded = false;
    for (name, healthy, bad) in fields {
        let v = runtime.get(name);
        if str_in(v, bad) {
            degraded = true;
        } else if !str_in(v, healthy) {
            refuse!("runtime_state_unavailable");
        }
    }
    if degraded {
        defer.push("runtime_not_healthy".into());
    }
    // 9
    let metadata = record.get("metadata").unwrap_or(&empty);
    if let Some(V::Arr(names)) = cap.get("required_evidence") {
        for n in names {
            let name = py_str(n);
            if !is_true(metadata.get(&name)) {
                defer.push(format!("missing_required_evidence:{name}"));
            }
        }
    }
    // 10
    if let Some(floor_v) = cap.get("min_evidence_quality").filter(|v| !v.is_null()) {
        let as_num = |v: Option<&V>| -> f64 {
            match v {
                Some(V::Num(n)) => to_f64(n),
                _ => 0.0,
            }
        };
        let q = if !none(record.get("evidence_quality")) {
            as_num(record.get("evidence_quality"))
        } else {
            as_num(metadata.get("evidence_quality"))
        };
        let floor = match numv(floor_v) {
            Some(Numv::Flt(f)) => f,
            Some(Numv::Int(neg, d)) => to_f64(&format!("{}{}", if neg { "-" } else { "" }, d)),
            None => f64::NAN,
        };
        if !q.is_finite() || !(0.0..=1.0).contains(&q) {
            defer.push(format!("evidence_quality_invalid:{}", py_repr(q)));
        } else if q < floor {
            defer.push(format!("evidence_quality_below_threshold:{}<{}", fixed4(q), fixed4(floor)));
        }
    }
    // 11
    if !none(cap.get("max_steps")) && !none(metadata.get("step_count")) {
        let sc = metadata.get("step_count").unwrap();
        match sc {
            V::Num(n) if is_int_lit(n) && cmp_int(n, "1") != std::cmp::Ordering::Less => {
                let max = cap.get("max_steps").unwrap();
                let exceeded = match max {
                    V::Num(m) if is_int_lit(m) => cmp_int(n, m) == std::cmp::Ordering::Greater,
                    V::Num(m) => to_f64(n) > to_f64(m),
                    V::Bool(b) => cmp_int(n, if *b { "1" } else { "0" }) == std::cmp::Ordering::Greater,
                    _ => false,
                };
                if exceeded {
                    refuse!(format!("capability_max_steps_exceeded:{}>{}", int_str(n), py_str(max)));
                }
            }
            _ => defer.push("invalid_step_count_metadata".into()),
        }
    }
    // 12
    let policy = match input.get("policy") {
        None | Some(V::Null) => &empty,
        Some(p) => p,
    };
    let allow_only = policy.get("allow_only");
    if !none(allow_only) && !matches!(allow_only, Some(V::Arr(_))) {
        refuse!("policy_invalid:allow_only_must_be_a_collection");
    }
    // 13
    if present(action.get("requested")) {
        if let Some(V::Arr(items)) = allow_only {
            let req = action.get("requested").unwrap();
            if !items.iter().any(|it| py_eq(req, it)) {
                refuse!("action_not_permitted_by_policy");
            }
        }
    }
    if defer.is_empty() {
        ("ALLOW", vec![])
    } else {
        ("DEFER", defer)
    }
}

fn main() {
    let stdin = io::stdin();
    let mut out = BufWriter::new(io::stdout().lock());
    for line in stdin.lock().lines() {
        let line = line.expect("stdin");
        if line.trim().is_empty() {
            continue;
        }
        let case = match parse(&line) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("svgate: cannot parse a case: {e}");
                std::process::exit(2);
            }
        };
        let (decision, reasons) = gate(case.get("input").unwrap_or(&V::Null));
        let mut s = String::from("{\"id\":");
        match case.get("id") {
            Some(V::Str(id)) => enc_str(id, &mut s),
            _ => s.push_str("null"),
        }
        s.push_str(",\"decision\":");
        enc_str(decision, &mut s);
        s.push_str(",\"reasons\":[");
        for (i, r) in reasons.iter().enumerate() {
            if i > 0 {
                s.push(',');
            }
            enc_str(r, &mut s);
        }
        s.push_str("]}\n");
        out.write_all(s.as_bytes()).expect("stdout");
    }
}
