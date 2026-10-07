//! The bits of Python semantics the contract leans on: truthiness, `==`, `repr(float)`,
//! `str(x)`, and `format(x, ".4f")`.

use crate::json::{BigInt, Value};

/// Python's `repr` of a float: shortest round-trip digits, `.0` on whole numbers,
/// exponent form when the decimal exponent is < -4 or >= 16.
pub fn repr_f64(x: f64) -> String {
    if x.is_nan() {
        return "nan".into();
    }
    if x.is_infinite() {
        return if x > 0.0 { "inf".into() } else { "-inf".into() };
    }
    let sign = if x.is_sign_negative() { "-" } else { "" };
    if x == 0.0 {
        return format!("{sign}0.0");
    }
    // Rust's `{:e}` gives the shortest round-trip digits: "d.ddde<exp>".
    let e = format!("{:e}", x.abs());
    let (mant, exp) = e.split_once('e').unwrap();
    let exp: i32 = exp.parse().unwrap();
    let digits: String = mant.chars().filter(|c| *c != '.').collect();
    let body = if (-4..16).contains(&exp) {
        if exp >= 0 {
            let ip = (exp + 1) as usize;
            if digits.len() <= ip {
                format!("{}{}.0", digits, "0".repeat(ip - digits.len()))
            } else {
                format!("{}.{}", &digits[..ip], &digits[ip..])
            }
        } else {
            format!("0.{}{}", "0".repeat((-exp - 1) as usize), digits)
        }
    } else {
        let m = if digits.len() > 1 {
            format!("{}.{}", &digits[..1], &digits[1..])
        } else {
            digits.clone()
        };
        let es = if exp < 0 { "-" } else { "+" };
        format!("{m}e{es}{:02}", exp.abs())
    };
    format!("{sign}{body}")
}

/// Python `format(x, ".4f")` on a float: exact binary value, round-half-even, 4 decimals.
/// Rust's `{:.4}` uses the exact value and ties-to-even (checked against CPython in NOTES.md).
pub fn fixed4(x: f64) -> String {
    if x.is_nan() {
        return "nan".into();
    }
    format!("{:.4}", x) // inf -> "inf", -inf -> "-inf", -0.0 -> "-0.0000", as in Python
}

/// Python truthiness of a JSON value.
pub fn truthy(v: Option<&Value>) -> bool {
    match v {
        None | Some(Value::Null) => false,
        Some(Value::Bool(b)) => *b,
        Some(Value::Int(i)) => !i.is_zero(),
        Some(Value::Float(f)) => *f != 0.0, // NaN is truthy in Python, and NaN != 0.0
        Some(Value::Str(s)) => !s.is_empty(),
        Some(Value::Arr(a)) => !a.is_empty(),
        Some(Value::Obj(m)) => !m.is_empty(),
    }
}

/// A Python number: bool is an int subclass.
pub enum Num {
    I(BigInt),
    F(f64),
}

pub fn as_num(v: &Value) -> Option<Num> {
    match v {
        Value::Bool(b) => Some(Num::I(BigInt::from_parts(false, if *b { "1" } else { "0" }))),
        Value::Int(i) => Some(Num::I(i.clone())),
        Value::Float(f) => Some(Num::F(*f)),
        _ => None,
    }
}

pub fn num_to_f64(n: &Num) -> f64 {
    match n {
        Num::I(i) => i.to_f64(),
        Num::F(f) => *f,
    }
}

/// Exact Python comparison of an int with a float. None when the float is NaN (unordered).
pub fn cmp_int_float(i: &BigInt, f: f64) -> Option<std::cmp::Ordering> {
    use std::cmp::Ordering::*;
    if f.is_nan() {
        return None;
    }
    if f == f64::INFINITY {
        return Some(Less);
    }
    if f == f64::NEG_INFINITY {
        return Some(Greater);
    }
    let fl = f.floor();
    let fb = BigInt::from_integral_f64(fl);
    match i.cmp(&fb) {
        Less => Some(Less),
        Greater => Some(Greater),
        Equal => Some(if fl == f { Equal } else { Less }),
    }
}

pub fn num_cmp(a: &Num, b: &Num) -> Option<std::cmp::Ordering> {
    match (a, b) {
        (Num::I(x), Num::I(y)) => Some(x.cmp(y)),
        (Num::F(x), Num::F(y)) => x.partial_cmp(y),
        (Num::I(x), Num::F(y)) => cmp_int_float(x, *y),
        (Num::F(x), Num::I(y)) => cmp_int_float(y, *x).map(|o| o.reverse()),
    }
}

/// Python `==` between two values decoded from JSON.
pub fn py_eq(a: &Value, b: &Value) -> bool {
    if let (Some(x), Some(y)) = (as_num(a), as_num(b)) {
        return num_cmp(&x, &y) == Some(std::cmp::Ordering::Equal);
    }
    match (a, b) {
        (Value::Null, Value::Null) => true,
        (Value::Str(x), Value::Str(y)) => x == y,
        (Value::Arr(x), Value::Arr(y)) => {
            x.len() == y.len() && x.iter().zip(y).all(|(p, q)| py_eq(p, q))
        }
        (Value::Obj(x), Value::Obj(y)) => {
            let dx = Value::dedup_members(x);
            let dy = Value::dedup_members(y);
            dx.len() == dy.len()
                && dx.iter().all(|(k, v)| {
                    dy.iter().find(|(kk, _)| kk == k).is_some_and(|(_, w)| py_eq(v, w))
                })
        }
        _ => false,
    }
}

/// Python `str(x)` of a decoded JSON value.
pub fn py_str(v: &Value) -> String {
    match v {
        Value::Str(s) => s.clone(),
        other => py_repr(other),
    }
}

/// Python `repr(x)` of a decoded JSON value (string repr approximated: see NOTES.md).
pub fn py_repr(v: &Value) -> String {
    match v {
        Value::Null => "None".into(),
        Value::Bool(b) => (if *b { "True" } else { "False" }).into(),
        Value::Int(i) => i.to_decimal(),
        Value::Float(f) => repr_f64(*f),
        Value::Str(s) => repr_str(s),
        Value::Arr(a) => format!("[{}]", a.iter().map(py_repr).collect::<Vec<_>>().join(", ")),
        Value::Obj(m) => format!(
            "{{{}}}",
            Value::dedup_members(m)
                .iter()
                .map(|(k, v)| format!("{}: {}", repr_str(k), py_repr(v)))
                .collect::<Vec<_>>()
                .join(", ")
        ),
    }
}

fn repr_str(s: &str) -> String {
    let q = if s.contains('\'') && !s.contains('"') { '"' } else { '\'' };
    let mut out = String::new();
    out.push(q);
    for c in s.chars() {
        match c {
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if c == q => {
                out.push('\\');
                out.push(c)
            }
            c if (c as u32) < 0x20 || (0x7f..0xa0).contains(&(c as u32)) => {
                out.push_str(&format!("\\x{:02x}", c as u32))
            }
            c => out.push(c),
        }
    }
    out.push(q);
    out
}
