// Command svgate is a port of the Sovereign Veritas Gate contract sv.gate/0 (CONTRACT.md) to Go,
// written from CONTRACT.md only, standard library only. Registered as C6 in docs/GATE_CONTRACT.md.
//
// It reads one case per line on stdin, {"id", "input"}, and writes one line per case,
// {"id", "decision", "reasons"}. Check it with:
//
//	(cd ports/go && go build -o ../../svgate .) && python tools/gate_contract.py --check-command ./svgate
package main

import (
	"bufio"
	"bytes"
	"encoding/json"
	"fmt"
	"math"
	"math/big"
	"os"
	"strconv"
	"strings"
)

type obj = map[string]interface{}

// ---- JSON values, read the way the contract says ----------------------------------------------

func isNum(v interface{}) bool { _, ok := v.(json.Number); return ok }

// isIntLiteral: "a JSON number written without a fraction or exponent".
func isIntLiteral(n json.Number) bool { return !strings.ContainsAny(string(n), ".eE") }

// toFloat: a JSON number as a double; an integer too large for a double is +/- infinity.
func toFloat(n json.Number) float64 {
	if isIntLiteral(n) {
		b, _ := new(big.Int).SetString(string(n), 10)
		f, _ := new(big.Float).SetInt(b).Float64()
		return f
	}
	f, err := strconv.ParseFloat(string(n), 64)
	if err != nil { // out of range: ParseFloat returns +/-Inf or 0 with an error; keep its value
		return f
	}
	return f
}

// present: "present and truthy in Python's sense".
func present(v interface{}) bool {
	switch x := v.(type) {
	case nil:
		return false
	case bool:
		return x
	case json.Number:
		if isIntLiteral(x) {
			b, _ := new(big.Int).SetString(string(x), 10)
			return b.Sign() != 0
		}
		return toFloat(x) != 0
	case string:
		return x != ""
	case []interface{}:
		return len(x) > 0
	case obj:
		return len(x) > 0
	}
	return true
}

// numeric value for Python equality: bool is 0/1, an integer literal is exact, a float literal is its double.
type pnum struct {
	rat *big.Rat // nil when inf
	inf int      // +1 / -1 when infinite
}

func asPNum(v interface{}) (pnum, bool) {
	switch x := v.(type) {
	case bool:
		if x {
			return pnum{rat: big.NewRat(1, 1)}, true
		}
		return pnum{rat: big.NewRat(0, 1)}, true
	case json.Number:
		if isIntLiteral(x) {
			b, _ := new(big.Int).SetString(string(x), 10)
			return pnum{rat: new(big.Rat).SetInt(b)}, true
		}
		f := toFloat(x)
		if math.IsInf(f, 0) {
			if f > 0 {
				return pnum{inf: 1}, true
			}
			return pnum{inf: -1}, true
		}
		r := new(big.Rat)
		r.SetFloat64(f)
		return pnum{rat: r}, true
	}
	return pnum{}, false
}

// pyEq: Python's == on JSON-decoded values (1 == 1.0 == True).
func pyEq(a, b interface{}) bool {
	if na, ok := asPNum(a); ok {
		nb, ok2 := asPNum(b)
		if !ok2 {
			return false
		}
		if na.rat == nil || nb.rat == nil {
			return na.rat == nil && nb.rat == nil && na.inf == nb.inf
		}
		return na.rat.Cmp(nb.rat) == 0
	}
	switch x := a.(type) {
	case nil:
		return b == nil
	case string:
		y, ok := b.(string)
		return ok && x == y
	case []interface{}:
		y, ok := b.([]interface{})
		if !ok || len(x) != len(y) {
			return false
		}
		for i := range x {
			if !pyEq(x[i], y[i]) {
				return false
			}
		}
		return true
	case obj:
		y, ok := b.(obj)
		if !ok || len(x) != len(y) {
			return false
		}
		for k, xv := range x {
			yv, ok := y[k]
			if !ok || !pyEq(xv, yv) {
				return false
			}
		}
		return true
	}
	return false
}

func asObj(v interface{}) obj {
	if o, ok := v.(obj); ok {
		return o
	}
	return obj{}
}

// pyStr: how Python's f-string prints a JSON value embedded in a reason (used for names).
func pyStr(v interface{}) string {
	if s, ok := v.(string); ok {
		return s
	}
	b, _ := json.Marshal(v)
	return string(b)
}

// ---- number formatting (CONTRACT.md, "Formatting") -----------------------------------------------

// pyRepr: Python's repr of a double.
func pyRepr(f float64) string {
	switch {
	case math.IsNaN(f):
		return "nan"
	case math.IsInf(f, 1):
		return "inf"
	case math.IsInf(f, -1):
		return "-inf"
	}
	if f == 0 {
		if math.Signbit(f) {
			return "-0.0"
		}
		return "0.0"
	}
	e := strconv.FormatFloat(f, 'e', -1, 64) // shortest round-trip digits
	mant, expStr, _ := strings.Cut(e, "e")
	exp, _ := strconv.Atoi(expStr)
	if exp < -4 || exp >= 16 {
		return e
	}
	s := strconv.FormatFloat(f, 'f', -1, 64)
	_ = mant
	if !strings.Contains(s, ".") {
		s += ".0"
	}
	return s
}

// fixed4: four-place fixed point; an infinite value prints as "inf" or "-inf", as Python's
// format(x, ".4f") does (Go would print "+Inf"). docs/OVF1_GO_PREREG.md.
func fixed4(f float64) string {
	switch {
	case math.IsInf(f, 1):
		return "inf"
	case math.IsInf(f, -1):
		return "-inf"
	}
	return strconv.FormatFloat(f, 'f', 4, 64)
}

// ---- the Gate (CONTRACT.md, "Rules") --------------------------------------------------------------

var statuses = map[string]bool{"PASS": true, "FAIL": true, "REFUTED": true, "INSUFFICIENT_EVIDENCE": true,
	"NOT_VERIFIED": true, "UNKNOWN": true}

var vocab = map[string][2][]string{
	"thermal_status": {{"normal", "cool"}, {"warning", "high", "hot", "critical", "unsafe"}},
	"compute_budget": {{"available", "constrained", "low"}, {"exhausted"}},
	"power_status":   {{"stable"}, {"unsafe"}},
}

func in(s string, xs []string) bool {
	for _, x := range xs {
		if x == s {
			return true
		}
	}
	return false
}

func refuse(r string) (string, []string) { return "REFUSE", []string{r} }

func gate(input obj) (string, []string) {
	rec := asObj(input["record"])
	reasons := []string{}

	// 1
	if !present(rec["input_digest"]) {
		return refuse("evidence_invalid:missing_input_digest")
	}
	// 2
	status := "NOT_VERIFIED"
	if ver, ok := rec["verification"].(obj); ok {
		if sv, has := ver["status"]; has && sv != nil {
			if s, isStr := sv.(string); isStr && statuses[s] {
				status = s
			} else {
				status = "UNKNOWN"
			}
		}
	}
	switch status {
	case "FAIL", "NOT_VERIFIED", "UNKNOWN":
		return refuse("verification_not_passed")
	case "REFUTED":
		return refuse("verification_refuted")
	case "INSUFFICIENT_EVIDENCE":
		reasons = append(reasons, "verification_insufficient_evidence")
	case "PASS":
	default:
		return refuse("verification_not_passed")
	}
	// 3
	capV := input["capability"]
	if capV == nil {
		return refuse("capability_missing")
	}
	cap := asObj(capV)
	// 4
	if b, ok := cap["authorized"].(bool); !ok || !b {
		return refuse("capability_not_authorized")
	}
	// 5
	if parent := cap["parent"]; present(parent) {
		regV := input["capability_registry"]
		if regV == nil {
			return refuse("capability_parent_requires_registry")
		}
		reg := asObj(regV)
		var entry interface{}
		if ps, ok := parent.(string); ok {
			entry = reg[ps]
		}
		if entry == nil {
			return refuse("capability_parent_missing:" + pyStr(parent))
		}
		if b, ok := asObj(entry)["authorized"].(bool); !ok || !b {
			return refuse("capability_parent_not_authorized:" + pyStr(parent))
		}
	}
	// 6
	action := asObj(rec["action"])
	if ac := action["capability"]; present(ac) && !pyEq(ac, cap["name"]) {
		return refuse("action_capability_mismatch")
	}
	// 7, 8
	rt := asObj(input["runtime"])
	degraded := false
	for _, f := range []string{"thermal_status", "compute_budget", "power_status"} {
		s, ok := rt[f].(string)
		v := vocab[f]
		if !ok || !(in(s, v[0]) || in(s, v[1])) {
			return refuse("runtime_state_unavailable")
		}
		if in(s, v[1]) {
			degraded = true
		}
	}
	if degraded {
		reasons = append(reasons, "runtime_not_healthy")
	}
	// 9
	meta := asObj(rec["metadata"])
	if req, ok := cap["required_evidence"].([]interface{}); ok {
		for _, n := range req {
			name := pyStr(n)
			if b, ok := meta[name].(bool); !ok || !b {
				reasons = append(reasons, "missing_required_evidence:"+name)
			}
		}
	}
	// 10
	if floorV := cap["min_evidence_quality"]; floorV != nil {
		q := 0.0
		if top := rec["evidence_quality"]; top != nil {
			if n, ok := top.(json.Number); ok {
				q = toFloat(n)
			}
		} else if n, ok := meta["evidence_quality"].(json.Number); ok {
			q = toFloat(n)
		}
		floor := 0.0
		if n, ok := floorV.(json.Number); ok {
			floor = toFloat(n)
		}
		if math.IsNaN(q) || math.IsInf(q, 0) || q < 0 || q > 1 {
			reasons = append(reasons, "evidence_quality_invalid:"+pyRepr(q))
		} else if q < floor {
			reasons = append(reasons, "evidence_quality_below_threshold:"+fixed4(q)+"<"+fixed4(floor))
		}
	}
	// 11
	if maxV := cap["max_steps"]; maxV != nil {
		if sc, has := meta["step_count"]; has && sc != nil {
			n, isN := sc.(json.Number)
			if !isN || !isIntLiteral(n) {
				reasons = append(reasons, "invalid_step_count_metadata")
			} else {
				b, _ := new(big.Int).SetString(string(n), 10)
				if b.Cmp(big.NewInt(1)) < 0 {
					reasons = append(reasons, "invalid_step_count_metadata")
				} else if mn, ok := maxV.(json.Number); ok && isIntLiteral(mn) {
					m, _ := new(big.Int).SetString(string(mn), 10)
					if b.Cmp(m) > 0 {
						return refuse(fmt.Sprintf("capability_max_steps_exceeded:%s>%s", b.String(), m.String()))
					}
				}
			}
		}
	}
	// 12
	policy := asObj(input["policy"])
	allow, hasAllow := policy["allow_only"]
	if hasAllow && allow != nil {
		if _, isArr := allow.([]interface{}); !isArr {
			return refuse("policy_invalid:allow_only_must_be_a_collection")
		}
	}
	// 13
	if requested := action["requested"]; present(requested) && hasAllow && allow != nil {
		found := false
		for _, x := range allow.([]interface{}) {
			if pyEq(requested, x) {
				found = true
				break
			}
		}
		if !found {
			return refuse("action_not_permitted_by_policy")
		}
	}
	if len(reasons) > 0 {
		return "DEFER", reasons
	}
	return "ALLOW", []string{}
}

func main() {
	sc := bufio.NewScanner(os.Stdin)
	sc.Buffer(make([]byte, 1<<20), 1<<26)
	out := bufio.NewWriter(os.Stdout)
	defer out.Flush()
	enc := json.NewEncoder(out)
	enc.SetEscapeHTML(false)
	for sc.Scan() {
		line := sc.Bytes()
		if len(bytes.TrimSpace(line)) == 0 {
			continue
		}
		d := json.NewDecoder(bytes.NewReader(line))
		d.UseNumber()
		var c obj
		if err := d.Decode(&c); err != nil {
			fmt.Fprintln(os.Stderr, "bad input line:", err)
			os.Exit(2)
		}
		dec, reasons := gate(asObj(c["input"]))
		if err := enc.Encode(map[string]interface{}{"id": c["id"], "decision": dec, "reasons": reasons}); err != nil {
			os.Exit(2)
		}
	}
}
