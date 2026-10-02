#!/usr/bin/env python3
"""Recompute every published number from the raw logs and fail if any document disagrees.

    python verify_claims.py            # exit 0 = every checked claim matches code output
    python verify_claims.py --full     # also re-runs the H1 simulation (~10 s) to prove determinism

Three kinds of check:
  1. Generated blocks. Any `<!-- BEGIN:<label>:<block> --> ... <!-- END:... -->` in a document
     must equal analyze.py's output for that label byte for byte ("sim_h1" blocks equal
     sim_gate's table).
  2. Historical tables. RESULTS.md and RESULTS_A1_A2.md were pasted from score.py/score_a2.py
     output before this tool existed; their numbers are recomputed here from the raw rows
     (including the Monte Carlo p95s, via legacy_mc.py, with the file set that existed when
     each was published).
  3. Quoted prose numbers in STATS.md, recomputed.
This is the house rule "numbers in prose must match code output verbatim", made mechanical.
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze  # noqa: E402
import legacy_mc  # noqa: E402

LABEL_CASES = {"container": "cases.jsonl", "container_h1": "heldout/cases_h1.jsonl"}
DOCS = ["README.md", "STATS.md", "RESULTS.md", "RESULTS_A1_A2.md", "PREREG_H1.md", "RESULTS_H1.md"]
FAILS, PASSES = [], []


def check(ok, what):
    (PASSES if ok else FAILS).append(what)


def read(p):
    p = os.path.join(HERE, p)
    if not os.path.exists(p):
        return None
    with open(p) as fh:
        return fh.read()


def load_json(*p):
    with open(os.path.join(HERE, *p)) as fh:
        return json.load(fh)


_cache = {}


def blocks_for(label):
    if label not in _cache:
        _cache[label] = analyze.analyze(label, LABEL_CASES[label])[0]
    return _cache[label]


def check_blocks():
    import sim_gate
    for doc in DOCS:
        s = read(doc)
        if s is None:
            continue
        for m in re.finditer(r"<!-- BEGIN:([\w:]+) -->\n(.*?)\n<!-- END:\1 -->", s, re.S):
            key, body = m.group(1), m.group(2)
            if key == "sim_h1":
                sim = load_json("results", "sim_h1_predictions.json")
                want = sim_gate.markdown(sim["predictions"])
            else:
                label, block = key.split(":")
                want = analyze.BLOCKS[block](blocks_for(label))
            check(body == want, f"{doc}: block {key}")
            if body != want:
                import difflib
                print("\n".join(difflib.unified_diff(body.splitlines(), want.splitlines(), "doc", "code", lineterm="", n=0)))


def check_results_md():
    """v0 table: acc, unsafe, p95 (legacy MC, v0 file set), rep-identical, medians, RSS."""
    s = read("RESULTS.md")
    rows = {"qwen2.5-1.5b-instruct-q4_k_m": r"\| Qwen2.5-1.5B-Instruct \(control 0\)",
            "LFM2.5-1.2B-Instruct-Q4_K_M": r"\| LFM2.5-1.2B-Instruct",
            "Qwen_Qwen3.5-2B-Q4_K_M": r"\| Qwen3.5-2B \(bartowski quant\)"}
    p95 = legacy_mc.legacy_p95(legacy_mc.V0_SET)
    res = blocks_for("container")["runs"]
    for stem, pat in rows.items():
        m = re.search(pat + r" \| ([\d.]+) \| ([\d.]+) \| ([\d.]+) \| [^|]+\| ([\d.]+) \| ([\d.]+) \| ([\d.]+) \| (\d+) \|", s)
        check(bool(m), f"RESULTS.md: row for {stem} found")
        if not m:
            continue
        r = res[f"direct/{stem}"]
        raw = [json.loads(l) for l in read(os.path.join("results", "container", stem + ".jsonl")).splitlines()]
        r0 = [x for x in raw if x["rep"] == 0]
        med = lambda xs: sorted(xs)[len(xs) // 2]
        got = [float(g) for g in m.groups()]
        want = [round(r["acc"], 4), round(r["unsafe_k"] / r["unsafe_n"], 4), p95[stem], 1.0,
                round(med([x["prompt_tps"] for x in r0]), 1), round(med([x["gen_tps"] for x in r0]), 2),
                int(max(x["peak_rss_mb"] for x in raw))]
        check(got == want, f"RESULTS.md: {stem} acc/unsafe/p95/rep/prompt/gen/RSS {got} == {want}")


def check_results_a1a2():
    s = read("RESULTS_A1_A2.md")
    res = blocks_for("container")["runs"]
    names = {"Qwen2.5-1.5B": "qwen2.5-1.5b-instruct-q4_k_m", "LFM2.5-1.2B": "LFM2.5-1.2B-Instruct-Q4_K_M",
             "Qwen3.5-2B": "Qwen_Qwen3.5-2B-Q4_K_M", "Qwen3.5-4B": "Qwen_Qwen3.5-4B-Q4_K_M"}
    cases = analyze.load_cases(os.path.join(HERE, "cases.jsonl"))
    import gate
    dep = [c["id"] for c in cases if any(gate.admissible(it) for it in c["evidence"])]
    for short, stem in names.items():
        for arm, key in (("direct", "direct"), ("decomposed", "decomposed_a2")):
            m = re.search(rf"\| {re.escape(short)} \| {arm} \| ([\d.]+) \| ([\d.]+) \| \*?\*?([\d.]+)\*?\*? \| (\d+)/12 \| (\d+)/4 \|", s)
            check(bool(m), f"RESULTS_A1_A2.md: row {short}/{arm} found")
            if not m:
                continue
            r = res[f"{key}/{stem}"]
            runs, _ = analyze.load_runs("container", cases)
            rows = runs[(key, stem)]
            acc34 = round(sum(rows[i]["pred"] == next(c for c in cases if c["id"] == i)["expected"] for i in dep) / len(dep), 4)
            want = (f"{r['acc']:.4f}", f"{acc34:.4f}", f"{r['unsafe_k'] / r['unsafe_n']:.4f}", str(r["refuted_k"]), str(r["inj_follow_k"]))
            check(m.groups() == want, f"RESULTS_A1_A2.md: {short}/{arm} {m.groups()} == {want}")
    p95 = legacy_mc.legacy_p95(legacy_mc.A1_SET)
    check(f"vs p95 {p95['Qwen_Qwen3.5-4B-Q4_K_M']}" in s, "RESULTS_A1_A2.md: 4B shuffle p95 (legacy MC, A1 file set)")


def check_stats_prose():
    s = read("STATS.md")
    res = blocks_for("container")
    v = lambda stem: res["runs"][f"direct/{stem}"]["vs_always_ns"]
    for stem, short in (("Qwen_Qwen3.5-2B-Q4_K_M", "Qwen3.5-2B"), ("Qwen_Qwen3.5-4B-Q4_K_M", "Qwen3.5-4B")):
        x = v(stem)
        frag = f"{x['b']} cases better / {x['c']} worse\n   (p = {x['p']:.3f})" if short == "Qwen3.5-2B" else f"{x['b']} / {x['c']} (p = {x['p']:.3f})"
        check(frag in s, f"STATS.md prose: {short} vs always-NS '{frag}'")
    p = res["paired"]["decomposed_a2 vs direct / Qwen3.5-4B"]["unsafe"]
    check(f"{p['a_unsafe_b_safe']} cases one way and\n   {p['a_safe_b_unsafe']} the other, p = {p['p']:.3f}" in s, "STATS.md prose: 4B unsafe McNemar")
    q = res["paired"]["decomposed_a2 vs direct / Qwen3.5-2B"]["unsafe"]
    check(f"Qwen3.5-2B {q['a_safe_b_unsafe']} → {q['a_unsafe_b_safe']} discordant (p = {q['p']:.3f}, Holm {q['p_holm']:.3f})" in s,
          "STATS.md prose: Qwen3.5-2B unsafe McNemar + Holm")
    d = res["runs"]["decomposed_a2/Qwen_Qwen3.5-2B-Q4_K_M"]["vs_always_ns"]
    check(f"({d['b']} better / {d['c']} worse, p = {d['p']:.3f}" in s, "STATS.md prose: 2B decomposed vs always-NS")
    leg = legacy_mc.legacy_p95(legacy_mc.V0_SET)["qwen2.5-1.5b-instruct-q4_k_m"]
    leg4 = legacy_mc.legacy_p95(legacy_mc.A1_SET)["qwen2.5-1.5b-instruct-q4_k_m"]
    check(f"published 0.4359 to 0.4615" in s and (leg, leg4) == (0.4359, 0.4615), "STATS.md prose: legacy p95 drift reproduces")
    rep = load_json("results", "score_report.json")
    check(rep["models"]["container/qwen2.5-1.5b-instruct-q4_k_m"]["shuffled_gold_p95"] == leg4,
          "committed score_report.json carries the drifted value (as documented)")
    check_instrument_prose(s)


def flat(s):
    return re.sub(r"\s+", " ", s)


def check_instrument_prose(s):
    """STATS.md items on the gate defect and the test suite (whitespace-insensitive)."""
    import copy
    import gate_strict, label_audit
    f = flat(s)
    n = gate_strict.corruption_counts()
    check(f"{n['gate']['new_accept']} of {n['corruptions']} corruptions turn a non-acceptance into an acceptance, "
          f"and {n['gate']['new_refute']} turn a non-refutation into a refutation" in f, "STATS.md prose: gate corruption counts")
    check(f"NOT_SUPPORTED ({n['gate_strict']['new_accept']} of {n['corruptions']})" in f and n["gate_strict"]["new_refute"] == 0,
          "STATS.md prose: strict gate corruption count")
    imp = gate_strict.recorded_impact("container", "cases.jsonl")
    check(f"({imp['unreadable']} of {imp['admissible_answers']} v0/A1/A2 item answers)" in f and imp["verdicts_changed"] == 0,
          "STATS.md prose: recorded unreadable answers")
    v0 = [json.loads(l) for l in read("cases.jsonl").splitlines()]
    h1 = [json.loads(l) for l in read(os.path.join("heldout", "cases_h1.jsonl")).splitlines()]
    check(f"all {len(v0) + len(h1)} case labels" in f, "STATS.md prose: number of case labels")
    flips = caught = 0
    wrong = {"support": ("refute", "neutral"), "refute": ("support", "neutral"), "neutral": ("support", "refute")}
    for c in h1:
        for i, it in enumerate(c["evidence"]):
            for w in wrong[it["stance"]]:
                bad = copy.deepcopy(c)
                bad["evidence"][i]["stance"] = w
                flips += 1
                caught += any(b[1] == i for b in label_audit.audit([bad])[1])
    check(caught == flips and f"each of the {flips} single-label corruptions of the held-out set is caught" in f,
          "STATS.md prose: label-audit power")
    m = load_json("results", "mutation_report.json")
    check(f"{m['mutants']} mutants, {m['KILLED']} killed, {m['SURVIVED']} survived" in f and m["ERRORED"] == 0,
          "STATS.md prose: mutation summary")


def check_readme():
    """Numbers in the dataset card's prose (the table is a generated block, checked above)."""
    f = flat(read("README.md"))
    res = blocks_for("container")
    r4 = res["paired"]["decomposed_a2 vs direct / Qwen3.5-4B"]["unsafe"]
    d4, a4 = res["runs"]["direct/Qwen_Qwen3.5-4B-Q4_K_M"], res["runs"]["decomposed_a2/Qwen_Qwen3.5-4B-Q4_K_M"]
    check(f"from {d4['unsafe_k']} to {a4['unsafe_k']} of {a4['unsafe_n']}. That is {r4['a_unsafe_b_safe']} discordant cases one way and "
          f"{r4['a_safe_b_unsafe']} the other (exact McNemar p = {r4['p']:.3f})" in f, "README prose: 4B unsafe McNemar")
    d2, a2 = res["runs"]["direct/Qwen_Qwen3.5-2B-Q4_K_M"], res["runs"]["decomposed_a2/Qwen_Qwen3.5-2B-Q4_K_M"]
    check(f"wrongly accepted {a2['unsafe_k']} of {a2['unsafe_n']} claims it should have rejected, versus {d2['unsafe_k']} of "
          f"{d2['unsafe_n']} when the same model decided directly" in f, "README prose: 2B unsafe direct vs decomposed")
    sig = sum(res["paired"][k]["unsafe"]["p_holm"] < 0.05 and res["paired"][k]["unsafe"]["a_unsafe_b_safe"] < res["paired"][k]["unsafe"]["a_safe_b_unsafe"]
              for k in res["paired"] if k.startswith("decomposed_a2 vs direct /"))
    n_models = sum(1 for k in res["paired"] if k.startswith("decomposed_a2 vs direct /"))
    check(f"reduced wrong acceptances for **{sig} of {n_models} models**, significant after Holm correction" in f, "README prose: Holm-significant count")
    import gate_strict
    imp = gate_strict.recorded_impact("container", "cases.jsonl")
    check(f"{imp['unreadable']} of {imp['admissible_answers']} recorded answers were affected" in f, "README prose: unreadable answers")
    check("0 of 608 recorded outputs were affected" in f, "README prose: parser (608 pinned in tests/test_parsers.py)")


def check_review_log():
    s = read("REVIEW_LOG.md")
    if s is None:
        return
    f = flat(s)
    import glob as _glob
    direct = sum(len(read(os.path.relpath(p, HERE)).splitlines())
                 for p in _glob.glob(os.path.join(HERE, "results", "container", "*.jsonl")))
    import gate_strict
    items = gate_strict.recorded_impact("container", "cases.jsonl")["admissible_answers"]
    check(f"every raw output ({direct} direct rows, {items} item answers)" in f, "REVIEW_LOG.md: raw output counts")
    runs = blocks_for("container")["runs"]
    best = max(runs[f"decomposed_a2/{st}"]["refuted_k"] for st in analyze.SHORT)
    who = sorted(analyze.SHORT[st] for st in analyze.SHORT if runs[f"decomposed_a2/{st}"]["refuted_k"] == best)
    check(f"REFUTED in up to {best} of 12 gold-REFUTED cases ({' and '.join(sorted(who, reverse=True))})" in f,
          "REVIEW_LOG.md: decomposed REFUTED recall")


def check_derived():
    """results/derived/predictions_<label>.jsonl (the viewer table) must be exactly what
    analyze.py emits from the raw rows."""
    import tempfile
    for label, cases_path in LABEL_CASES.items():
        rel = os.path.join("results", "derived", f"predictions_{label}.jsonl")
        committed = read(rel)
        if committed is None:
            continue
        _, runs, cases = analyze.analyze(label, cases_path)
        fd, tmp = tempfile.mkstemp(suffix=".jsonl")
        os.close(fd)
        try:
            analyze.emit_predictions(runs, cases, label, tmp)
            with open(tmp) as fh:
                check(fh.read() == committed, f"{rel} regenerates byte for byte")
        finally:
            os.remove(tmp)


def check_sim_determinism():
    import subprocess, tempfile
    tmp = os.path.join(tempfile.gettempdir(), "sim_h1_check.json")
    subprocess.check_call([sys.executable, os.path.join(HERE, "sim_gate.py"), "--out", tmp], stdout=subprocess.DEVNULL)
    with open(tmp) as fh:
        a = json.load(fh)["predictions"]
    b = load_json("results", "sim_h1_predictions.json")["predictions"]
    check(a == b, "sim_gate.py reproduces results/sim_h1_predictions.json exactly (seeded)")


def main():
    check_blocks()
    check_results_md()
    check_results_a1a2()
    check_stats_prose()
    check_readme()
    check_review_log()
    check_derived()
    if "--full" in sys.argv:
        check_sim_determinism()
    for f in FAILS:
        print("FAIL", f)
    print(f"verify_claims: {len(PASSES)} passed, {len(FAILS)} failed")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
