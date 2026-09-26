#!/usr/bin/env python3
"""make_package.py - run one gated measurement on this device and write an sv.package/0.

Measurement: sha256 chained --rounds times over a seeded artifact (deterministic, so the
independent verifier can recompute it). Runs the real EvidenceWorkflow: a recompute verifier
registered and probed both ways (a correct and a corrupted prediction), the fixed Gate, an
in-memory hash-chained Ledger, and thermal zones read once before and once after.

Runtime state: --thermal-status defaults to 'unknown', which the Gate treats as unavailable and
REFUSEs. A value such as 'normal' is DECLARED and the package says so. '--thermal-status measured'
DERIVES it from the zones read before the run under policy s25-uncalibrated-v0
(sovereign_veritas/thermal_policy.py); the verifier recomputes it. No zones -> unknown -> REFUSE.

--preload-seconds N (anti-vacuity, device only): run one busy loop per core for N seconds and read
the before-snapshot while they still run, so a measured status can come back 'hot'. The package
records preload_seconds in its measurement.

  python tools/make_package.py [--rounds 200000] [--thermal-status normal|measured]
                               [--preload-seconds 30] [--thermal-root /sys/class/thermal]
"""
import argparse, hashlib, json, os, platform, subprocess, sys, time

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sovereign_veritas.capability import Capability  # noqa: E402
from sovereign_veritas.evidence import EvidenceRecord, Ledger, LedgerSink, canonical_json  # noqa: E402
from sovereign_veritas.interfaces.contracts import ActionProposal, Prediction  # noqa: E402
from sovereign_veritas.package import build_package, sha256_hex, write_package  # noqa: E402
from sovereign_veritas.runtime import RuntimeState  # noqa: E402
from sovereign_veritas.thermal import read_zones  # noqa: E402
from sovereign_veritas.thermal_policy import POLICY_ID, POLICIES, derive_thermal_status  # noqa: E402
from sovereign_veritas.verifier_registry import VerifierRegistry  # noqa: E402
from sovereign_veritas.workflow import EvidenceWorkflow  # noqa: E402

VERIFIER_ID = "sha256-chain-recompute-v0"


def chain_hex(data: bytes, rounds: int) -> str:
    h = data
    for _ in range(rounds):
        h = hashlib.sha256(h).digest()
    return h.hex()


class Artifact:
    def __init__(self, data):
        self.data = data

    def observe(self):
        return self.data


class Measure:
    def __init__(self, rounds):
        self.rounds, self.elapsed_ms = rounds, None

    def predict(self, observation):
        t0 = time.perf_counter()
        out = chain_hex(observation, self.rounds)
        self.elapsed_ms = round((time.perf_counter() - t0) * 1000, 3)
        return Prediction(value={"output_sha256": out}, uncertainty=None, model_id="sha256_chain")


class Recompute:
    """Independent recompute: PASS only if the prediction equals a fresh computation."""
    def __init__(self, rounds):
        self.rounds = rounds

    def verify(self, observation, prediction):
        ok = prediction.value.get("output_sha256") == chain_hex(observation, self.rounds)
        return {"status": "PASS" if ok else "FAIL"}


def read_zones_under_load(seconds, root):
    """Busy-loop every core for `seconds`, read the zones while the loops still run, then kill them."""
    burners = []
    try:
        burners = [subprocess.Popen([sys.executable, "-c", "while True: pass"])
                   for _ in range(os.cpu_count() or 1)]
        time.sleep(seconds)
        return read_zones(root)
    finally:
        for b in burners:
            b.kill()
        for b in burners:
            b.wait()


class NoSideEffect:
    def execute(self, action):
        return {"recorded": action.requested}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=200000)
    ap.add_argument("--seed", default="sv-package-v0")
    ap.add_argument("--thermal-status", default="unknown")
    ap.add_argument("--preload-seconds", type=int, default=0)
    ap.add_argument("--thermal-root", default="/sys/class/thermal",
                    help="where to read zones (tests point this at a fake tree)")
    a = ap.parse_args()
    thermal_before = (read_zones_under_load(a.preload_seconds, a.thermal_root) if a.preload_seconds > 0
                      else read_zones(a.thermal_root))
    if a.thermal_status == "measured":
        thermal_status, why = derive_thermal_status([z.to_dict() for z in thermal_before],
                                                    POLICIES[POLICY_ID])
        runtime_meta = {"thermal_status_source": "measured", "thermal_policy": POLICY_ID}
        print(f"thermal {thermal_status} ({why})  policy {POLICY_ID}  zones {len(thermal_before)}")
    else:
        thermal_status, runtime_meta = a.thermal_status, {"thermal_status_source": "declared"}

    artifact = hashlib.sha256(a.seed.encode()).digest() * 32  # 1 KiB, deterministic
    verifier = Recompute(a.rounds)
    registry = VerifierRegistry(min_coverage=0.5)
    registry.register(VERIFIER_ID, verifier)
    good = Prediction(value={"output_sha256": chain_hex(b"probe", a.rounds)})
    bad = Prediction(value={"output_sha256": "0" * 64})
    registry.record_probe(VERIFIER_ID, passed=verifier.verify(b"probe", good)["status"] == "PASS")
    registry.record_probe(VERIFIER_ID, passed=verifier.verify(b"probe", bad)["status"] == "FAIL")

    ledger = Ledger()
    ledger.append(EvidenceRecord(record_id="session-start", input_digest=sha256_hex(b"session"),
                                 metadata={"device": platform.machine(),
                                           "python": platform.python_version()}))
    measure = Measure(a.rounds)
    capability = Capability("measure", authorized=True, required_evidence=("verifier_probed",))
    runtime = RuntimeState(platform=platform.platform(), python_version=platform.python_version(),
                           thermal_status=thermal_status, metadata=runtime_meta)
    policy = {"allow_only": ["record_result"]}
    wf = EvidenceWorkflow(sensor=Artifact(artifact), predictor=measure, verifier=verifier,
                          executor=NoSideEffect(), evidence_sink=LedgerSink(ledger),
                          verifier_registry=registry)
    result = wf.run(record_id="run-1", input_digest=sha256_hex(artifact), capability=capability,
                    runtime=runtime, action=ActionProposal("measure", "record_result", {}),
                    policy=policy, metadata={"verifier_probed": True}, verifier_id=VERIFIER_ID)
    thermal_after = read_zones(a.thermal_root)

    measurement = {"kind": "sha256_chain", "rounds": a.rounds, "artifact_sha256": sha256_hex(artifact),
                   "output_sha256": result.prediction.value["output_sha256"],
                   "elapsed_ms": measure.elapsed_ms,
                   "thermal_before": [z.to_dict() for z in thermal_before]}
    if a.preload_seconds > 0:
        measurement["preload_seconds"] = a.preload_seconds
    pkg = build_package(artifact=artifact, artifact_name=f"seed:{a.seed}", measurement=measurement,
                        chain=ledger.all(), capability=capability, runtime=runtime, policy=policy,
                        verifier_id=VERIFIER_ID, validation=registry.validation(VERIFIER_ID),
                        thermal=thermal_after)
    path = write_package(pkg, os.path.expanduser("~"))
    md5 = hashlib.md5(canonical_json(pkg).encode("utf-8")).hexdigest()
    print(f"decision {pkg['decision']['decision']} {pkg['decision']['reasons']}")
    print(f"elapsed_ms {measure.elapsed_ms}  zones {len(thermal_after)}  freshness NOT_PROVEN")
    print(f"package {path}  md5 {md5}")


if __name__ == "__main__":
    main()
