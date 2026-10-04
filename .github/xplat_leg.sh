#!/usr/bin/env bash
# One XPLAT leg (docs/XPLAT_PREREG.md). Writes one file per command into OUT; never stops early,
# so a failing command shows up as its output and exit code instead of as a missing file.
set -u
OUT="$1"; PY="${PY:-python}"
export PYTHONPATH=. PYTHONUTF8=1 PYTHONDONTWRITEBYTECODE=1
mkdir -p "$OUT"
$PY -c "import platform, sys; print(platform.platform(), platform.machine(), sys.byteorder, platform.python_version())" > "$OUT/platform.info"
run() { name="$1"; shift; "$@" > "$OUT/$name" 2>&1; echo "exit $?  $name" | tee -a "$OUT/exits.info"; }
run gate.txt              $PY tools/gate_constraint.py --target .
run contract_kernel.txt   $PY tools/gate_contract.py --check kernel
run contract_verifier.txt $PY tools/gate_contract.py --check verifier
: > "$OUT/packages.txt"
for p in evidence/sv_package_*.json; do
  echo "== $p" >> "$OUT/packages.txt"
  $PY tools/verify_package.py "$p" --signature "$p.sig" --allowed-signers keys/allowed_signers \
      --identity holland202 --witness-log witness/packages.log >> "$OUT/packages.txt" 2>&1
  echo "exit $?" >> "$OUT/packages.txt"
done
run attacks.txt           $PY tools/attack_harness.py --round2 --round3
run corridor.txt          $PY tools/corridor_challenge.py
run recovery.txt          $PY tools/recovery_admissibility.py
run xb1.txt               $PY tools/execution_boundary_probe.py --expect-fix
cat "$OUT/platform.info"
