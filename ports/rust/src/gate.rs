//! The Gate, rule by rule, from CONTRACT.md (`sv.gate/0`). Rule numbers match the contract.
//! Choices for inputs the contract does not specify are marked `CHOICE` and listed in NOTES.md.

use crate::json::Value;
use crate::pyfmt::{
    as_num, fixed4, num_cmp, num_to_f64, py_eq, py_str, repr_f64, truthy, Num,
};

pub struct Decision {
    pub decision: &'static str,
    pub reasons: Vec<String>,
}

fn refuse(r: impl Into<String>) -> Decision {
    Decision { decision: "REFUSE", reasons: vec![r.into()] }
}

static EMPTY: Value = Value::Obj(Vec::new());

/// `d.get(key)` treating a missing key as null. A non-object `d` reads as `{}` (CHOICE).
fn get<'a>(d: &'a Value, key: &str) -> &'a Value {
    static NULL: Value = Value::Null;
    d.get(key).unwrap_or(&NULL)
}

/// An object member read as an object: null, missing, or a non-object all read as `{}`.
fn obj<'a>(d: &'a Value, key: &str) -> &'a Value {
    match d.get(key) {
        Some(v @ Value::Obj(_)) => v,
        _ => &EMPTY,
    }
}

const STATUSES: [&str; 6] =
    ["PASS", "FAIL", "REFUTED", "INSUFFICIENT_EVIDENCE", "NOT_VERIFIED", "UNKNOWN"];

pub fn decide(input: &Value) -> Decision {
    let mut defer: Vec<String> = Vec::new();
    let record = obj(input, "record");

    // 1
    if !truthy(record.get("input_digest")) {
        return refuse("evidence_invalid:missing_input_digest");
    }

    // 2
    let status: &str = match record.get("verification") {
        Some(v @ Value::Obj(_)) => match get(v, "status") {
            Value::Null => "NOT_VERIFIED",
            Value::Str(s) if STATUSES.contains(&s.as_str()) => STATUSES
                .iter()
                .find(|x| **x == s.as_str())
                .copied()
                .unwrap(),
            _ => "UNKNOWN",
        },
        // null, missing, or (CHOICE) any non-object verification
        _ => "NOT_VERIFIED",
    };
    match status {
        "FAIL" | "NOT_VERIFIED" | "UNKNOWN" => return refuse("verification_not_passed"),
        "REFUTED" => return refuse("verification_refuted"),
        "INSUFFICIENT_EVIDENCE" => defer.push("verification_insufficient_evidence".into()),
        "PASS" => {}
        _ => return refuse("verification_not_passed"),
    }

    // 3  (CHOICE: only null/missing is "missing"; `{}` falls through to rule 4)
    let cap_raw = get(input, "capability");
    if cap_raw.is_null() {
        return refuse("capability_missing");
    }
    // CHOICE: a non-object capability reads as `{}`.
    let cap: &Value = if matches!(cap_raw, Value::Obj(_)) { cap_raw } else { &EMPTY };

    // 4
    if !matches!(cap.get("authorized"), Some(Value::Bool(true))) {
        return refuse("capability_not_authorized");
    }

    // 5
    let parent = get(cap, "parent");
    if truthy(Some(parent)) {
        let registry = get(input, "capability_registry");
        if registry.is_null() {
            return refuse("capability_parent_requires_registry");
        }
        // CHOICE: a non-string parent never matches a registry key; a non-object registry
        // has no entries.
        let entry = match parent {
            Value::Str(p) => registry.get(p),
            _ => None,
        };
        let pname = py_str(parent);
        match entry {
            None | Some(Value::Null) => {
                return refuse(format!("capability_parent_missing:{pname}"));
            }
            Some(e) => {
                // CHOICE: a non-null, non-object entry is "not authorized".
                if !matches!(e.get("authorized"), Some(Value::Bool(true))) {
                    return refuse(format!("capability_parent_not_authorized:{pname}"));
                }
            }
        }
    }

    // 6
    let action = obj(record, "action");
    let act_cap = get(action, "capability");
    if truthy(Some(act_cap)) && !py_eq(act_cap, get(cap, "name")) {
        return refuse("action_capability_mismatch");
    }

    // 7, 8
    let runtime = get(input, "runtime");
    let fields: [(&str, &[&str], &[&str]); 3] = [
        ("thermal_status", &["normal", "cool"], &["warning", "high", "hot", "critical", "unsafe"]),
        ("compute_budget", &["available", "constrained", "low"], &["exhausted"]),
        ("power_status", &["stable"], &["unsafe"]),
    ];
    let mut degraded = false;
    for (name, healthy, bad) in fields.iter() {
        match runtime.get(name) {
            Some(Value::Str(s)) if healthy.contains(&s.as_str()) => {}
            Some(Value::Str(s)) if bad.contains(&s.as_str()) => degraded = true,
            _ => return refuse("runtime_state_unavailable"),
        }
    }
    if degraded {
        defer.push("runtime_not_healthy".into());
    }

    // 9
    let metadata = obj(record, "metadata");
    // CHOICE: Python iteration semantics for non-arrays (string -> characters, object -> keys);
    // null / missing / number / bool -> no requirements.
    let names: Vec<Value> = match get(cap, "required_evidence") {
        Value::Arr(a) => a.clone(),
        Value::Str(s) => s.chars().map(|c| Value::Str(c.to_string())).collect(),
        Value::Obj(m) => Value::dedup_members(m)
            .into_iter()
            .map(|(k, _)| Value::Str(k))
            .collect(),
        _ => Vec::new(),
    };
    for name in &names {
        let ok = match name {
            Value::Str(n) => matches!(metadata.get(n), Some(Value::Bool(true))),
            _ => false, // CHOICE: a non-string name never matches a metadata key
        };
        if !ok {
            defer.push(format!("missing_required_evidence:{}", py_str(name)));
        }
    }

    // 10
    let floor_v = get(cap, "min_evidence_quality");
    if !floor_v.is_null() {
        // CHOICE: a non-numeric floor (string/array/object) skips the rule; bool is 0/1.
        if let Some(floor) = as_num(floor_v).map(|n| num_to_f64(&n)) {
            let number = |v: &Value| -> f64 {
                match v {
                    Value::Int(i) => i.to_f64(),
                    Value::Float(f) => *f,
                    _ => 0.0,
                }
            };
            let rq = get(record, "evidence_quality");
            let q = if !rq.is_null() {
                number(rq)
            } else {
                number(get(metadata, "evidence_quality"))
            };
            if !q.is_finite() || q < 0.0 || q > 1.0 {
                defer.push(format!("evidence_quality_invalid:{}", repr_f64(q)));
            } else if q < floor {
                defer.push(format!(
                    "evidence_quality_below_threshold:{}<{}",
                    fixed4(q),
                    fixed4(floor)
                ));
            }
        }
    }

    // 11
    let max_v = get(cap, "max_steps");
    if !max_v.is_null() {
        if let Some(sc) = metadata.get("step_count").filter(|v| !v.is_null()) {
            match sc {
                Value::Int(i) if !i.neg && !i.is_zero() => {
                    // CHOICE: a non-numeric max_steps skips the comparison.
                    if let Some(m) = as_num(max_v) {
                        if num_cmp(&Num::I(i.clone()), &m) == Some(std::cmp::Ordering::Greater) {
                            return refuse(format!(
                                "capability_max_steps_exceeded:{}>{}",
                                i.to_decimal(),
                                py_str(max_v)
                            ));
                        }
                    }
                }
                _ => defer.push("invalid_step_count_metadata".into()),
            }
        }
    }

    // 12  (CHOICE: a non-object, non-null policy reads as `{}`)
    let policy = obj(input, "policy");
    let allow_only = get(policy, "allow_only");
    if !allow_only.is_null() && !matches!(allow_only, Value::Arr(_)) {
        return refuse("policy_invalid:allow_only_must_be_a_collection");
    }

    // 13
    let requested = get(action, "requested");
    if truthy(Some(requested)) {
        if let Value::Arr(list) = allow_only {
            if !list.iter().any(|e| py_eq(requested, e)) {
                return refuse("action_not_permitted_by_policy");
            }
        }
    }

    if defer.is_empty() {
        Decision { decision: "ALLOW", reasons: vec![] }
    } else {
        Decision { decision: "DEFER", reasons: defer }
    }
}
