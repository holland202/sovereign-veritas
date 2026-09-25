import hashlib
import json
import platform
import subprocess
import time
import urllib.request
import urllib.error
from pathlib import Path


BASE = "http://127.0.0.1:8080"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def digest(obj):
    return sha256(
        json.dumps(
            obj,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    )


def get_json(url, timeout=10):
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def post_json(url, payload, timeout=120):
    body = json.dumps(payload).encode()

    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )

    start = time.perf_counter()

    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()

    elapsed = time.perf_counter() - start

    return json.loads(raw.decode()), elapsed


def device_info():
    info = {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": platform.python_version(),
    }

    for key, prop in [
        ("android", "ro.build.version.release"),
        ("device", "ro.product.model"),
        ("soc", "ro.soc.model"),
    ]:
        try:
            info[key] = subprocess.check_output(
                ["getprop", prop],
                text=True,
            ).strip()
        except Exception:
            info[key] = "unavailable"

    return info


def memory_info():
    out = {}

    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            key, value = line.split(":", 1)

            if key in {
                "MemTotal",
                "MemAvailable",
                "MemFree",
            }:
                out[key] = value.strip()
    except Exception:
        pass

    return out


def thermal_raw():
    values = []

    root = Path("/sys/class/thermal")

    if not root.exists():
        return values

    for p in sorted(root.glob("thermal_zone*/temp")):
        try:
            raw = int(p.read_text().strip())

            # Reject obvious invalid/unavailable readings.
            if raw <= 0:
                valid = False
            elif raw < 1000:
                valid = False
            elif raw > 150000:
                valid = False
            else:
                valid = True

            values.append({
                "sensor": p.parent.name,
                "raw": raw,
                "celsius": raw / 1000.0,
                "valid": valid,
            })

        except Exception:
            pass

    return values


def thermal_summary():
    sensors = thermal_raw()

    valid = [
        x for x in sensors
        if x["valid"]
    ]

    if not valid:
        return {
            "sensor_count": len(sensors),
            "valid_count": 0,
            "min_c": None,
            "max_c": None,
            "mean_c": None,
        }

    temps = [
        x["celsius"]
        for x in valid
    ]

    return {
        "sensor_count": len(sensors),
        "valid_count": len(valid),
        "min_c": round(min(temps), 3),
        "max_c": round(max(temps), 3),
        "mean_c": round(sum(temps) / len(temps), 3),
    }


def model_info():
    data = get_json(BASE + "/v1/models")

    models = data.get("data", [])

    if not models:
        raise RuntimeError(
            "llama-server returned no models"
        )

    return models[0]


def run_inference(model, name, prompt, max_tokens):
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Answer concisely. "
                    "Do not add unnecessary explanation."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        "max_tokens": max_tokens,
        "temperature": 0,
        "stream": False,
    }

    request_digest = digest(payload)

    memory_before = memory_info()
    thermal_before = thermal_summary()

    response, elapsed = post_json(
        BASE + "/v1/chat/completions",
        payload,
    )

    memory_after = memory_info()
    thermal_after = thermal_summary()

    choices = response.get("choices", [])

    if not choices:
        raise RuntimeError(
            "No choices returned by llama-server"
        )

    message = choices[0].get("message", {})
    output = message.get("content", "")

    usage = response.get("usage", {})

    output_bytes = output.encode()

    result = {
        "test": name,
        "request_digest": request_digest,
        "output_digest": sha256(output_bytes),
        "elapsed_ms": round(elapsed * 1000, 3),
        "output_chars": len(output),
        "output_preview": output[:160],
        "usage": usage,
        "memory_before": memory_before,
        "memory_after": memory_after,
        "thermal_before": thermal_before,
        "thermal_after": thermal_after,
        "temperature": 0,
        "max_tokens": max_tokens,
    }

    return result


def main():
    print("=" * 76)
    print("SOVEREIGN VERITAS — REAL LOCAL INFERENCE TEST")
    print("=" * 76)

    print("\nENVIRONMENT")
    print("-" * 76)

    for k, v in device_info().items():
        print(f"{k:<18}: {v}")

    print("\nLLAMA SERVER")
    print("-" * 76)

    try:
        models = get_json(BASE + "/v1/models")
    except Exception as e:
        print("ERROR: Could not contact llama-server.")
        print(f"       {e}")
        print()
        print("Expected endpoint:")
        print("       http://127.0.0.1:8080/v1/models")
        return 2

    model = model_info()

    model_id = model.get("id")

    print(f"endpoint           : {BASE}")
    print(f"model              : {model_id}")

    prompt = (
        "Explain in one short paragraph why provenance integrity "
        "and artifact identity are not the same thing."
    )

    print("\nTEST CONFIGURATION")
    print("-" * 76)
    print("temperature        : 0")
    print("prompt             :", prompt)

    tests = [
        ("baseline", prompt, 128),
        (
            "reduced_context",
            "Explain briefly why provenance and artifact identity differ.",
            128,
        ),
        (
            "output_capped",
            prompt,
            32,
        ),
    ]

    results = []

    for name, test_prompt, max_tokens in tests:
        print(f"\nRUNNING: {name}")
        print("-" * 76)

        try:
            result = run_inference(
                model_id,
                name,
                test_prompt,
                max_tokens,
            )

            results.append(result)

            print(
                f"latency            : "
                f"{result['elapsed_ms']} ms"
            )

            print(
                f"output chars       : "
                f"{result['output_chars']}"
            )

            print(
                f"output digest      : "
                f"{result['output_digest'][:20]}"
            )

            print(
                f"usage              : "
                f"{json.dumps(result['usage'], sort_keys=True)}"
            )

            print(
                f"thermal before     : "
                f"{result['thermal_before']}"
            )

            print(
                f"thermal after      : "
                f"{result['thermal_after']}"
            )

            print(
                f"output             : "
                f"{result['output_preview']!r}"
            )

        except Exception as e:
            print(f"ERROR: {type(e).__name__}: {e}")

    print("\nCOMPARISON")
    print("-" * 76)

    if len(results) >= 2:
        baseline = results[0]

        for r in results:
            delta = (
                r["elapsed_ms"] -
                baseline["elapsed_ms"]
            )

            print(
                f"{r['test']:<20} "
                f"{r['elapsed_ms']:>9.3f} ms   "
                f"delta={delta:+.3f} ms   "
                f"tokens={r['usage'].get('completion_tokens', '?')}"
            )

    print("\nEVIDENCE")
    print("-" * 76)

    evidence = {
        "environment": device_info(),
        "server": BASE,
        "model": model,
        "tests": results,
        "test_digest": digest(results),
    }

    out = Path("sv_real_inference_results.json")

    out.write_text(
        json.dumps(
            evidence,
            indent=2,
            sort_keys=True,
        )
    )

    print(f"result file        : {out}")
    print(f"evidence digest    : {evidence['test_digest']}")

    print("\nINTERPRETATION")
    print("-" * 76)
    print("This is a measurement, not a claim of optimization.")
    print("Different latency does not by itself establish improvement.")
    print("Output, token usage, thermal state, and evidence completeness")
    print("must be considered together.")

    print("=" * 76)


if __name__ == "__main__":
    raise SystemExit(main())
