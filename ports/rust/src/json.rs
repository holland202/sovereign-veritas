//! Minimal JSON parser and serializer with the distinctions the Gate contract needs.
//!
//! * Integers (no fraction, no exponent) keep their exact decimal value as a normalized
//!   big integer; floats are parsed to the nearest f64 (huge -> +/-inf, tiny -> 0.0).
//! * Object members keep source order; duplicate keys resolve to the LAST value on lookup
//!   (Python `json.loads` behaviour).
//! * Like Python's `json.loads`, the literals `NaN`, `Infinity` and `-Infinity` are accepted.
//! * Lone UTF-16 surrogates in `\u` escapes are replaced by U+FFFD (Rust strings cannot hold
//!   them; Python's can). Documented deviation.

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct BigInt {
    pub neg: bool,
    /// Decimal digits, no leading zeros, "0" for zero (zero is never negative).
    pub digits: String,
}

impl BigInt {
    pub fn from_parts(neg: bool, digits: &str) -> BigInt {
        let d = digits.trim_start_matches('0');
        if d.is_empty() {
            BigInt { neg: false, digits: "0".to_string() }
        } else {
            BigInt { neg, digits: d.to_string() }
        }
    }
    pub fn is_zero(&self) -> bool {
        self.digits == "0"
    }
    pub fn to_f64(&self) -> f64 {
        // Rust's decimal parser is correctly rounded and overflows to infinity.
        let v: f64 = self.digits.parse().unwrap_or(f64::INFINITY);
        if self.neg { -v } else { v }
    }
    /// Python str(int).
    pub fn to_decimal(&self) -> String {
        if self.neg { format!("-{}", self.digits) } else { self.digits.clone() }
    }
    pub fn cmp(&self, other: &BigInt) -> std::cmp::Ordering {
        use std::cmp::Ordering::*;
        match (self.neg, other.neg) {
            (false, true) => Greater,
            (true, false) => Less,
            (false, false) => cmp_mag(&self.digits, &other.digits),
            (true, true) => cmp_mag(&other.digits, &self.digits),
        }
    }
    /// Exact integer value of an integral, finite f64.
    pub fn from_integral_f64(f: f64) -> BigInt {
        let s = format!("{:.0}", f.abs()); // exact for integral values
        BigInt::from_parts(f < 0.0, &s)
    }
}

fn cmp_mag(a: &str, b: &str) -> std::cmp::Ordering {
    a.len().cmp(&b.len()).then_with(|| a.cmp(b))
}

#[derive(Debug, Clone)]
pub enum Value {
    Null,
    Bool(bool),
    Int(BigInt),
    Float(f64),
    Str(String),
    Arr(Vec<Value>),
    Obj(Vec<(String, Value)>),
}

impl Value {
    /// Python dict.get on a parsed object: last duplicate wins. None if not an object.
    pub fn get(&self, key: &str) -> Option<&Value> {
        match self {
            Value::Obj(m) => m.iter().rev().find(|(k, _)| k == key).map(|(_, v)| v),
            _ => None,
        }
    }
    pub fn is_null(&self) -> bool {
        matches!(self, Value::Null)
    }
    /// Object members as Python's dict would hold them: first-insertion order, last value.
    pub fn dedup_members(m: &[(String, Value)]) -> Vec<(String, &Value)> {
        let mut out: Vec<(String, &Value)> = Vec::new();
        for (k, v) in m {
            if let Some(slot) = out.iter_mut().find(|(kk, _)| kk == k) {
                slot.1 = v;
            } else {
                out.push((k.clone(), v));
            }
        }
        out
    }
}

pub struct Parser<'a> {
    s: &'a [u8],
    i: usize,
}

pub fn parse(text: &str) -> Result<Value, String> {
    let mut p = Parser { s: text.as_bytes(), i: 0 };
    p.ws();
    let v = p.value()?;
    p.ws();
    if p.i != p.s.len() {
        return Err(format!("trailing data at byte {}", p.i));
    }
    Ok(v)
}

impl<'a> Parser<'a> {
    fn ws(&mut self) {
        while self.i < self.s.len() && matches!(self.s[self.i], b' ' | b'\t' | b'\n' | b'\r') {
            self.i += 1;
        }
    }
    fn peek(&self) -> Option<u8> {
        self.s.get(self.i).copied()
    }
    fn lit(&mut self, w: &str) -> bool {
        if self.s[self.i..].starts_with(w.as_bytes()) {
            self.i += w.len();
            true
        } else {
            false
        }
    }
    fn value(&mut self) -> Result<Value, String> {
        match self.peek() {
            None => Err("unexpected end".into()),
            Some(b'{') => self.object(),
            Some(b'[') => self.array(),
            Some(b'"') => Ok(Value::Str(self.string()?)),
            Some(b't') if self.lit("true") => Ok(Value::Bool(true)),
            Some(b'f') if self.lit("false") => Ok(Value::Bool(false)),
            Some(b'n') if self.lit("null") => Ok(Value::Null),
            Some(b'N') if self.lit("NaN") => Ok(Value::Float(f64::NAN)),
            Some(b'I') if self.lit("Infinity") => Ok(Value::Float(f64::INFINITY)),
            Some(b'-') if self.lit("-Infinity") => Ok(Value::Float(f64::NEG_INFINITY)),
            Some(c) if c == b'-' || c.is_ascii_digit() => self.number(),
            Some(c) => Err(format!("unexpected byte {:?} at {}", c as char, self.i)),
        }
    }
    fn object(&mut self) -> Result<Value, String> {
        self.i += 1;
        let mut m = Vec::new();
        self.ws();
        if self.peek() == Some(b'}') {
            self.i += 1;
            return Ok(Value::Obj(m));
        }
        loop {
            self.ws();
            if self.peek() != Some(b'"') {
                return Err(format!("expected key at {}", self.i));
            }
            let k = self.string()?;
            self.ws();
            if self.peek() != Some(b':') {
                return Err(format!("expected ':' at {}", self.i));
            }
            self.i += 1;
            self.ws();
            let v = self.value()?;
            m.push((k, v));
            self.ws();
            match self.peek() {
                Some(b',') => self.i += 1,
                Some(b'}') => {
                    self.i += 1;
                    return Ok(Value::Obj(m));
                }
                _ => return Err(format!("expected ',' or '}}' at {}", self.i)),
            }
        }
    }
    fn array(&mut self) -> Result<Value, String> {
        self.i += 1;
        let mut a = Vec::new();
        self.ws();
        if self.peek() == Some(b']') {
            self.i += 1;
            return Ok(Value::Arr(a));
        }
        loop {
            self.ws();
            a.push(self.value()?);
            self.ws();
            match self.peek() {
                Some(b',') => self.i += 1,
                Some(b']') => {
                    self.i += 1;
                    return Ok(Value::Arr(a));
                }
                _ => return Err(format!("expected ',' or ']' at {}", self.i)),
            }
        }
    }
    fn hex4(&mut self) -> Result<u32, String> {
        if self.i + 4 > self.s.len() {
            return Err("short \\u escape".into());
        }
        let h = std::str::from_utf8(&self.s[self.i..self.i + 4]).map_err(|e| e.to_string())?;
        let v = u32::from_str_radix(h, 16).map_err(|_| format!("bad \\u escape {h}"))?;
        self.i += 4;
        Ok(v)
    }
    fn string(&mut self) -> Result<String, String> {
        self.i += 1; // opening quote
        let mut out = String::new();
        loop {
            let start = self.i;
            while self.i < self.s.len() && self.s[self.i] != b'"' && self.s[self.i] != b'\\' {
                if self.s[self.i] < 0x20 {
                    return Err(format!("control character in string at {}", self.i));
                }
                self.i += 1;
            }
            out.push_str(std::str::from_utf8(&self.s[start..self.i]).map_err(|e| e.to_string())?);
            match self.peek() {
                None => return Err("unterminated string".into()),
                Some(b'"') => {
                    self.i += 1;
                    return Ok(out);
                }
                _ => {
                    self.i += 1; // backslash
                    let c = self.peek().ok_or("bad escape")?;
                    self.i += 1;
                    match c {
                        b'"' => out.push('"'),
                        b'\\' => out.push('\\'),
                        b'/' => out.push('/'),
                        b'b' => out.push('\u{8}'),
                        b'f' => out.push('\u{c}'),
                        b'n' => out.push('\n'),
                        b'r' => out.push('\r'),
                        b't' => out.push('\t'),
                        b'u' => {
                            let u = self.hex4()?;
                            if (0xD800..0xDC00).contains(&u)
                                && self.s[self.i..].starts_with(b"\\u")
                            {
                                let save = self.i;
                                self.i += 2;
                                let lo = self.hex4()?;
                                if (0xDC00..0xE000).contains(&lo) {
                                    let cp = 0x10000 + ((u - 0xD800) << 10) + (lo - 0xDC00);
                                    out.push(char::from_u32(cp).unwrap());
                                } else {
                                    out.push('\u{FFFD}');
                                    self.i = save;
                                }
                            } else {
                                out.push(char::from_u32(u).unwrap_or('\u{FFFD}'));
                            }
                        }
                        _ => return Err(format!("bad escape \\{}", c as char)),
                    }
                }
            }
        }
    }
    fn number(&mut self) -> Result<Value, String> {
        let start = self.i;
        let neg = self.peek() == Some(b'-');
        if neg {
            self.i += 1;
        }
        let ds = self.i;
        match self.peek() {
            Some(b'0') => self.i += 1,
            Some(c) if c.is_ascii_digit() => {
                while self.peek().is_some_and(|c| c.is_ascii_digit()) {
                    self.i += 1;
                }
            }
            _ => return Err(format!("bad number at {start}")),
        }
        let int_digits = std::str::from_utf8(&self.s[ds..self.i]).unwrap().to_string();
        let mut is_int = true;
        if self.peek() == Some(b'.')
            && self.s.get(self.i + 1).is_some_and(|c| c.is_ascii_digit())
        {
            is_int = false;
            self.i += 1;
            while self.peek().is_some_and(|c| c.is_ascii_digit()) {
                self.i += 1;
            }
        }
        if matches!(self.peek(), Some(b'e' | b'E')) {
            let save = self.i;
            self.i += 1;
            if matches!(self.peek(), Some(b'+' | b'-')) {
                self.i += 1;
            }
            if self.peek().is_some_and(|c| c.is_ascii_digit()) {
                is_int = false;
                while self.peek().is_some_and(|c| c.is_ascii_digit()) {
                    self.i += 1;
                }
            } else {
                self.i = save; // Python's regex would stop before the 'e'; then it is trailing junk
            }
        }
        let text = std::str::from_utf8(&self.s[start..self.i]).unwrap();
        if is_int {
            Ok(Value::Int(BigInt::from_parts(neg, &int_digits)))
        } else {
            let f: f64 = text.parse().map_err(|_| format!("bad float {text}"))?;
            Ok(Value::Float(f))
        }
    }
}

/// Python `json.dumps(..., ensure_ascii=False, separators=(",", ":"), sort_keys)` encoding.
pub fn dumps(v: &Value, sort_keys: bool, out: &mut String) {
    match v {
        Value::Null => out.push_str("null"),
        Value::Bool(b) => out.push_str(if *b { "true" } else { "false" }),
        Value::Int(i) => out.push_str(&i.to_decimal()),
        Value::Float(f) => {
            if f.is_nan() {
                out.push_str("NaN")
            } else if f.is_infinite() {
                out.push_str(if *f > 0.0 { "Infinity" } else { "-Infinity" })
            } else {
                out.push_str(&crate::pyfmt::repr_f64(*f))
            }
        }
        Value::Str(s) => dump_str(s, out),
        Value::Arr(a) => {
            out.push('[');
            for (n, e) in a.iter().enumerate() {
                if n > 0 {
                    out.push(',');
                }
                dumps(e, sort_keys, out);
            }
            out.push(']');
        }
        Value::Obj(m) => {
            let mut mem = Value::dedup_members(m);
            if sort_keys {
                mem.sort_by(|a, b| a.0.cmp(&b.0));
            }
            out.push('{');
            for (n, (k, e)) in mem.iter().enumerate() {
                if n > 0 {
                    out.push(',');
                }
                dump_str(k, out);
                out.push(':');
                dumps(e, sort_keys, out);
            }
            out.push('}');
        }
    }
}

pub fn dump_str(s: &str, out: &mut String) {
    out.push('"');
    for c in s.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            '\u{8}' => out.push_str("\\b"),
            '\u{c}' => out.push_str("\\f"),
            c if (c as u32) < 0x20 => out.push_str(&format!("\\u{:04x}", c as u32)),
            c => out.push(c),
        }
    }
    out.push('"');
}
