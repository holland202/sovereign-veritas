#!/usr/bin/env python3
"""Draw EO-2's catch matrix from the committed run outputs (no re-run, no new numbers).

  python tools/eo2_figure.py      -> docs/figures/eo2_catch_matrix.png

Rows are the evidence a reviewer could rely on: the record (R0), the executor's receipt (R1), an independent
read-back without binding (R2u), with binding as registered (R2), and with Amendment 1's strict rule (R2s), plus the
paranoid checker that flags everything. Columns are the honest cases C1-C4 and the attacks A1-A8.

Scoring follows docs/EO2_RESULTS.md: on an attack, any verdict other than OK or UNOBSERVABLE is a catch. On an honest
case, OK is correct, UNOBSERVABLE on C4 is the expected honest abstention, and anything else is a false alarm.
Prints every count it draws. Requires matplotlib.
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN = os.path.join(ROOT, "results", "eo2", "run.txt")
AM1 = os.path.join(ROOT, "results", "eo2", "amendment1_run.txt")
OUT = os.path.join(ROOT, "docs", "figures", "eo2_catch_matrix.png")
ROWS = [("R0", "record (R0)"), ("R1", "executor receipt (R1)"), ("R2u", "read-back, unbound (R2u)"),
        ("R2", "read-back, bound (R2, as registered)"), ("R2s", "read-back, bound, strict (R2s, Amendment 1)"),
        ("PARANOID", "paranoid checker (flags everything)")]


def table(path):
    lines = [ln.rstrip("\n") for ln in open(path, encoding="utf-8")]
    head = next(i for i, ln in enumerate(lines) if ln.split() and ln.split()[0] == "C1")
    cols = lines[head].split()
    rows = {}
    for ln in lines[head + 1:]:
        parts = ln.split()
        if not parts or parts[0] not in {"R0", "R1", "R2", "R2u", "R2s", "PARANOID"}:
            break
        rows[parts[0]] = dict(zip(cols, parts[1:]))
    return cols, rows


def main():
    cols, rows = table(RUN)
    cols1, rows1 = table(AM1)
    rows["R2s"] = rows1["R2s"]
    rows["R2"]["A8"] = rows1["R2"]["A8"]
    cols = cols + [c for c in cols1 if c not in cols]
    green, red, amber, blue, grey = "#2ea043", "#da3633", "#d29922", "#388bfd", "#30363d"
    plt.rcParams.update({"figure.facecolor": "#0d1117", "axes.facecolor": "#0d1117", "text.color": "#c9d1d9",
                         "xtick.color": "#c9d1d9", "ytick.color": "#c9d1d9", "font.size": 10})
    fig, ax = plt.subplots(figsize=(14, 4.6))
    for y, (key, label) in enumerate(ROWS):
        caught = missed = alarms = 0
        for x, c in enumerate(cols):
            v = rows.get(key, {}).get(c)
            if v is None:
                color, text = grey, "not run"
            elif c.startswith("A"):
                if v in ("OK", "UNOBSERVABLE"):
                    color, text = red, "missed"
                    missed += 1
                else:
                    color, text = green, "caught"
                    caught += 1
            elif v == "OK" or (c == "C4" and v == "UNOBSERVABLE"):
                color, text = blue, "correct" if v == "OK" else "abstains"
            else:
                color, text = amber, "false alarm"
                alarms += 1
            ax.add_patch(plt.Rectangle((x, y), 0.94, 0.88, color=color))
            ax.text(x + 0.47, y + 0.44, text, ha="center", va="center", fontsize=8, color="white")
        attacks = sum(1 for c in cols if c.startswith("A") and rows.get(key, {}).get(c) is not None)
        print(f"{key}: caught {caught} of {attacks} attacks run; false alarms on honest cases {alarms}")
        ax.text(len(cols) + 0.15, y + 0.44, f"{caught}/{attacks} caught" + (f", {alarms} false alarms" if alarms else ""),
                va="center", fontsize=9)
    ax.set_xlim(0, len(cols) + 2.3)
    ax.set_ylim(len(ROWS), 0)
    ax.set_xticks([i + 0.47 for i in range(len(cols))], cols)
    ax.xaxis.tick_top()
    ax.set_yticks([i + 0.44 for i in range(len(ROWS))], [label for _, label in ROWS])
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0)
    ax.axvline(4 - 0.03, color="#8b949e", lw=1)
    ax.text(2, len(ROWS) + 0.35, "honest cases", ha="center", fontsize=9, color="#8b949e")
    ax.text(4 + (len(cols) - 4) / 2, len(ROWS) + 0.35, "attacks (A7 = a compromised observer; A8 = Amendment 1 only)",
            ha="center", fontsize=9, color="#8b949e")
    ax.legend(handles=[Patch(color=green, label="attack caught"), Patch(color=red, label="attack missed"),
                       Patch(color=blue, label="honest case handled correctly"), Patch(color=amber, label="false alarm"),
                       Patch(color=grey, label="not run")], loc="upper center", bbox_to_anchor=(0.45, -0.1), ncol=5,
              frameon=False, fontsize=9)
    fig.suptitle("EO-2: which evidence catches which attack on a file-backed valve stand-in "
                 "(container only, self-tested)", fontsize=12)
    fig.tight_layout(rect=[0, 0.02, 1, 0.94])
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    fig.savefig(OUT, dpi=150)
    print(f"wrote {os.path.relpath(OUT, ROOT)}")


if __name__ == "__main__":
    main()
