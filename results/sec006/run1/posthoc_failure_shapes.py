import collections, importlib.util, sys, tempfile, json
from pathlib import Path
sys.path.insert(0, "/home/claude/sovereign-veritas")
spec = importlib.util.spec_from_file_location("p", "/home/claude/sovereign-veritas/tools/sec006_stress_probe.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
from sovereign_veritas.idempotency import FileReservations
for arm in ("lock", "nolock"):
    lost_trials = dup_trials = lost_total = notok_trials = 0
    for seed in m.REGISTERED_SEEDS:
        with tempfile.TemporaryDirectory() as t:
            d = Path(t); m.run_trial(seed, arm, d)
            g = collections.defaultdict(collections.Counter)
            for i in range(m.P_WORKERS):
                for k, v in json.loads((d / f"worker{i}.json").read_text())["granted"].items(): g[k].update(v)
            st = FileReservations(d); lost = dup = notok = 0
            for key in [f"K{i}" for i in range(m.K_KEYS)]:
                a = st._path(key); files = ([a] if a.exists() else []) + sorted(a.parent.glob(a.stem + ".released-*.json"))
                found = collections.Counter(json.loads(f.read_text()).get("token", "<no token>") for f in files)
                lost += sum((g[key] - found).values()); dup += sum((found - g[key]).values()); notok += found["<no token>"]
            lost_trials += lost > 0; dup_trials += dup > 0; lost_total += lost; notok_trials += notok > 0
    print(f"{arm:6s} trials with a lost reservation: {lost_trials}/20 (lost tokens total {lost_total}); trials with duplicated entries: {dup_trials}/20; trials with a file missing its token: {notok_trials}/20")
