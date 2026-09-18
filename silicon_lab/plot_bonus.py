"""
Bonus deliverable 1 - The Empirical Curve.

Reads bonus_curve.csv (written by bonus_gil.py) and plots worker count T on the
X-axis against execution time on the Y-axis for both threading.Thread and
multiprocessing.Pool, annotating the inflection cliff.

Usage:  python3 plot_bonus.py
Output: bonus_curve.png  (300 dpi, ready to paste into the worksheet)
"""

import csv
import sys

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except ImportError:
    print("matplotlib is required:  python3 -m pip install matplotlib")
    sys.exit(1)

try:
    with open("bonus_curve.csv") as fh:
        rows = list(csv.DictReader(fh))
except FileNotFoundError:
    print("bonus_curve.csv not found - run 'python3 bonus_gil.py' first.")
    sys.exit(1)

workers = [int(r["workers"]) for r in rows]
thread_t = [float(r["threading_seconds"]) for r in rows]
proc_t = [float(r["multiprocessing_seconds"]) for r in rows]

# Inflection cliff = first worker count after the minimum where time rises again
proc_min_idx = proc_t.index(min(proc_t))
cliff_idx = None
for i in range(proc_min_idx + 1, len(proc_t)):
    if proc_t[i] > proc_t[proc_min_idx]:
        cliff_idx = i
        break

fig, ax = plt.subplots(figsize=(9, 5.5))

ax.plot(workers, thread_t, marker="o", linewidth=2.2, markersize=7,
        color="#c0392b", label="threading.Thread (GIL-bound)")
ax.plot(workers, proc_t, marker="s", linewidth=2.2, markersize=7,
        color="#1f6feb", label="multiprocessing.Pool (true parallelism)")

ax.set_xscale("log", base=2)
ax.set_xticks(workers)
ax.set_xticklabels([str(w) for w in workers])
ax.set_xlabel("Worker count T (threads or processes)", fontsize=11)
ax.set_ylabel("Execution time [s]", fontsize=11)
ax.set_title("Empirical scaling curve: fixed 50,000,000-iteration CPU workload\n"
             "split across T workers", fontsize=12.5, pad=14)
ax.grid(True, which="both", alpha=0.25, linestyle="--")
ax.set_ylim(bottom=0)

# Annotate the multiprocessing minimum
ax.annotate(f"minimum\nT = {workers[proc_min_idx]}",
            xy=(workers[proc_min_idx], proc_t[proc_min_idx]),
            xytext=(workers[proc_min_idx], proc_t[proc_min_idx] + max(proc_t) * 0.22),
            ha="center", fontsize=9, color="#1f6feb",
            arrowprops=dict(arrowstyle="->", color="#1f6feb", lw=1.3))

if cliff_idx is not None:
    ax.axvline(workers[cliff_idx], color="#7f8c8d", linestyle=":", linewidth=1.6)
    ax.annotate(f"inflection cliff\nT = {workers[cliff_idx]}\n"
                f"(oversubscription)",
                xy=(workers[cliff_idx], proc_t[cliff_idx]),
                xytext=(workers[cliff_idx] * 0.42,
                        proc_t[cliff_idx] + max(proc_t) * 0.30),
                ha="center", fontsize=9, color="#7f8c8d",
                arrowprops=dict(arrowstyle="->", color="#7f8c8d", lw=1.3))

ax.legend(frameon=False, fontsize=10, loc="lower left")
fig.tight_layout()
fig.savefig("bonus_curve.png", dpi=300)
print("Wrote bonus_curve.png")
if cliff_idx is not None:
    print(f"Inflection cliff identified at T = {workers[cliff_idx]} "
          f"({proc_t[cliff_idx]:.4f}s vs minimum {proc_t[proc_min_idx]:.4f}s "
          f"at T = {workers[proc_min_idx]})")
else:
    print(f"No cliff within tested range; minimum at T = {workers[proc_min_idx]}. "
          f"Extend THREAD_COUNTS in bonus_gil.py to find it.")
