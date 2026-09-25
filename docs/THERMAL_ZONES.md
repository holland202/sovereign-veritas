# Thermal zones on the S25 — what the readings are

Status: **EXPLORATORY** (one run, one device, no registered prediction). Not a finding.

## Why

The first inference run's thermal summary reported max ≈ 104.6 °C and mean ≈ 67 °C. The
harness took a max and a mean over every zone that read 1–150 °C, and recorded zones only as
`thermal_zoneN`. A later idle inspection found nothing near 104 °C, and the 104 °C was
labelled UNSUPPORTED. That compared idle readings to a post-load summary, so it settled nothing.

## Zone map (SM-S938U, Android 16, 68 zones, read 2026-09-25)

| Domain | Types |
|---|---|
| cpu_core | `cpu-0-0-0` … `cpu-0-5-1`, `cpu-1-0-0` … `cpu-1-1-1` |
| cpu_subsystem | `cpuss-0-0`, `cpuss-0-1`, `cpuss-1-0`, `cpuss-1-1` |
| gpu | `gpuss-0` … `gpuss-7` |
| npu | `nsphvx-0..2`, `nsphmx-0..3` |
| ddr / modem / camera / video | `ddr`, `mdmss-0..3`, `camera-0..1`, `video` |
| always_on | `aoss-0..3` |
| pmic | `pm8550*_tz`, `pmr735d_tz` |
| battery / board | `battery`, `sys-therm-0`, `sys-therm-5` |
| rf | `sdr0`, `sdr0_pa`, `mmw_ific0`, `mmw0..3` |
| bcl — **not a temperature** | `pm8550-bcl-lvl0..2` (battery current-limit levels; read 0) |
| unknown | `ac` |

At idle, `mmw0..3` and `sdr0_pa` read -273000: absolute zero, the block is powered down.

## Probe run — `tools/thermal_probe.py` (md5 bd4ed73014588a7cd3821b14450c9975)

8 busy-loop processes for 30 s, one consistent pass over all zones per sample. S25, Python
3.14.6. Line breaks restored from terminal wrap; values verbatim.

```
EXPLORATORY thermal_probe | aarch64 python 3.14.6 | 68 zones | 8 burners x 30s | 26 load samples
TOP 12 zones by max under load (millidegrees as read):
   104200 (idle   40300)  thermal_zone19  cpu-1-1-1          cpu_core
   103100 (idle   42000)  thermal_zone10  cpu-0-4-1          cpu_core
   102700 (idle   42000)  thermal_zone6   cpu-0-2-1          cpu_core
   102300 (idle   42400)  thermal_zone2   cpu-0-0-1          cpu_core
   101100 (idle   39900)  thermal_zone17  cpu-1-0-1          cpu_core
   100800 (idle   42000)  thermal_zone5   cpu-0-2-0          cpu_core
   100800 (idle   41700)  thermal_zone9   cpu-0-4-0          cpu_core
    99600 (idle   41700)  thermal_zone1   cpu-0-0-0          cpu_core
    96900 (idle   39900)  thermal_zone18  cpu-1-1-0          cpu_core
    96500 (idle   43200)  thermal_zone14  cpuss-0-1          cpu_subsystem
    96100 (idle   46300)  thermal_zone12  cpu-0-5-1          cpu_core
    96100 (idle   42800)  thermal_zone8   cpu-0-3-1          cpu_core
MAX by domain: cpu_core=104200, cpu_subsystem=96500, gpu=69200, video=68800, always_on=64900, ddr=64900, camera=63800, npu=62600, modem=61900, pmic=60049, rf=47000, unknown=46800, board=39709, battery=33300, NOT_TEMPERATURE_bcl=0
ZONES 15/45/57: thermal_zone15=aoss-1, thermal_zone45=nsphmx-3, thermal_zone57=pm8550_tz
>= 90 C under load: 19 zones
unknown types: ['ac']
raw  /data/data/com.termux/files/home/thermal_probe_1790370637.json  md5 bd466b64da371fdeff6b2f1fc4308086
rc=0
```

The raw JSON stays on the device, not in the repo.

## What this does and does not show

- CPU core sensors read up to 104.2 °C within 30 s of all-core busy load; 19 zones reached ≥ 90 °C.
  Battery peaked at 33.3 °C and board thermistors at 39.709 °C over the same run.
- So a ~104 °C CPU-core reading is reproducible under load. "The device reached 104 °C" is still
  the wrong sentence: the battery and board never passed 40 °C.
- NOT shown: that the original 104.6 °C came from a CPU core (the old harness recorded no zone
  types); that a busy-loop heats like LLM decode; that the sensors are calibrated.
- A single threshold over all zones is wrong in both directions: a junction limit fires never on
  the battery, a skin limit fires always on the CPU. Same defect class as quasar-v2 F13
  (governor taking the max over all 68 zones).

`sovereign_veritas/thermal.py` is the maintained version of the probe's inline domain map
(the probe labels BCL `NOT_TEMPERATURE_bcl`; the module calls it `bcl` with status
`not_temperature`). The harness now records every zone per snapshot and summarizes per domain,
with no mean and no device-wide max. Nothing is wired into `RuntimeState`; per-domain limits are
uncalibrated.
