# HV-1 raw results (`docs/HV1_PREREG.md`, `docs/HV1_RESULTS.md`)

| File | Command | Exit | Note |
|---|---|---|---|
| `hv1_registered.txt` | `python tools/hv1_sim.py` | 1 | the registered run: `VERDICT  2 of 6 as registered (H7 is the --sabotage run)` |
| `hv1_sabotage.txt` | `python tools/hv1_sim.py --sabotage` | 0 | margin 0: `VERDICT  H7 HELD` |
| `hv1-20261007-2000-registered/`, `hv1-20261007-2000-sabotage/` | written by the two runs | — | sv-lab-vk2 substrate: `run.json` (semantics), `events.jsonl` (one event per cell, with a digest of every trial's decision and reasons), `artifact_manifest.json` (sha256 of the simulator, the Gate and the registration as run) |
| `hv1_trace_v1.txt` | first version of `python tools/hv1_trace.py` | 0 | written after the run. That version had no attorney section, and its source was not kept. `diff` with `hv1_trace.txt` shows only the added section and the timings |
| `hv1_trace.txt` | `python tools/hv1_trace.py` (as committed) | 0 | `registered run re-observed: 128 of 128 cells have the registered digest` |

The simulator ran uncommitted at `378332a`. Its sha256 in both manifests equals that of the committed
`tools/hv1_sim.py`.
