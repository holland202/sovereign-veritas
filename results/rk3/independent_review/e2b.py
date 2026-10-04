# Outside the repo. Prediction: some trials lose COMPLETED when complete() lands at lease expiry while another
# process's reserve() is writing the lease_expired transition. Separate processes, real FileReservations.
import os, sys, time, tempfile, subprocess, random
ROOT = sys.argv[1]; sys.path.insert(0, ROOT)
from sovereign_veritas.idempotency import FileReservations, ReservationRefused, COMPLETED, UNKNOWN
if sys.argv[2] == "hammer":
    d, K, until = sys.argv[3], sys.argv[4], float(sys.argv[5]); s = FileReservations(d)
    while time.time() < until:
        try: s.reserve(K)
        except ReservationRefused: pass
    sys.exit(0)
N = int(sys.argv[3]); lost = 0; completed_then_unknown = 0
tmp = tempfile.mkdtemp()
for i in range(N):
    d = os.path.join(tmp, f"t{i}"); K = f"K{i}"; a = FileReservations(d)
    lease = 0.15; a.reserve(K, lease_s=lease); t_exp = time.time() + lease
    hs = [subprocess.Popen([sys.executable, __file__, ROOT, "hammer", d, K, str(t_exp + 0.05)]) for _ in range(3)]
    while time.time() < t_exp + random.uniform(-0.0005, 0.0005): pass
    a.complete(K)
    for h in hs: h.wait()
    hist = [h["to"] for h in a.history(K)]
    if a.state(K) == UNKNOWN: completed_then_unknown += 1
    if COMPLETED not in hist: lost += 1
print(f"trials={N} final_state_UNKNOWN_after_complete={completed_then_unknown} COMPLETED_missing_from_history={lost}")
