"""
Deliverable 4 - Scalability Graph (speedup_plot.png)

Reads results.csv (written by ./collatz) and plots thread count k against:
    - Linear ideal          S(k) = k
    - Theoretical Amdahl    S_theo(k) = 1 / [(1-p) + p/k]
    - Measured empirical    S_emp(k) = T_seq / T_k

A second panel shows the Reality Gap, Delta(k) = S_theo(k) - S_emp(k),
which is the quantity the worksheet asks you to map.

Usage:  python plot_speedup.py
Output: speedup_plot.png  (200 dpi)
"""

import csv
import sys

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except ImportError:
    print("matplotlib is required:  python -m pip install matplotlib")
    sys.exit(1)

INK, GRID = "#1a1a1a", "#d8dbe0"
BLUE, RED, GREY, GREEN = "#1f6feb", "#c0392b", "#7f8c8d", "#1e8e5a"

plt.rcParams.update({
    "font.size": 10, "axes.edgecolor": "#b9bec6", "axes.labelcolor": INK,
    "text.color": INK, "xtick.color": INK, "ytick.color": INK,
    "axes.spines.top": False, "axes.spines.right": False,
})

# ------------------------------------------------------------------ load
try:
    with open("results.csv", newline="") as fh:
        rows = list(csv.DictReader(fh))
except FileNotFoundError:
    print("results.csv not found - run ./collatz first.")
    sys.exit(1)

scaling = [r for r in rows
           if r["table"] == "1_scaling" and r["configuration"].startswith("parallel_k")]
if not scaling:
    print("No scaling rows found in results.csv.")
    sys.exit(1)

seq = next((r for r in rows if r["configuration"] == "sequential_baseline"), None)
T_seq = float(seq["avg_time_s"]) if seq else None

k      = [int(r["threads"])     for r in scaling]
s_emp  = [float(r["s_emp"])     for r in scaling]
s_theo = [float(r["s_theo"])    for r in scaling]
delta  = [float(r["delta"])     for r in scaling]
t_k    = [float(r["avg_time_s"]) for r in scaling]

# Recover p from the k = 2 measurement, exactly as the worksheet derives it
s2 = next(s for kk, s in zip(k, s_emp) if kk == 2)
p = 2.0 * (1.0 - 1.0 / s2)
s_max = 1.0 / (1.0 - p) if p < 1.0 else float("inf")

# ------------------------------------------------------------------ plot
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

ax1.plot(k, k, ls="--", lw=1.7, color=GREY, marker="^", ms=6,
         label="Linear ideal  S(k) = k")
ax1.plot(k, s_theo, ls="-.", lw=2.0, color=GREEN, marker="s", ms=6,
         label=f"Amdahl theoretical  (p = {p:.4f})")
ax1.plot(k, s_emp, lw=2.4, color=BLUE, marker="o", ms=7,
         label="Empirical  S_emp(k)")

if s_max != float("inf"):
    ax1.axhline(s_max, color=GREEN, ls=":", lw=1.3)
    ax1.text(max(k), s_max * 1.02, f"$S_{{max}}$ = {s_max:.2f}×",
             ha="right", va="bottom", fontsize=9, color=GREEN)

# shade the reality gap
ax1.fill_between(k, s_emp, s_theo, color=RED, alpha=0.10)
worst = max(range(len(k)), key=lambda i: delta[i])
ax1.annotate(f"Reality Gap\nΔ({k[worst]}) = {delta[worst]:.2f}",
             xy=(k[worst], (s_emp[worst] + s_theo[worst]) / 2),
             xytext=(k[worst] * 0.42, s_theo[worst] * 0.92),
             fontsize=9, color=RED,
             arrowprops=dict(arrowstyle="->", color=RED, lw=1.3))

ax1.set_xscale("log", base=2)
ax1.set_xticks(k)
ax1.set_xticklabels([str(x) for x in k])
ax1.set_xlabel("Thread count k")
ax1.set_ylabel("Speedup S(k)")
ax1.set_title("Amdahl scaling: ideal, theoretical and measured", fontsize=11.5)
ax1.grid(alpha=0.3, ls="--", color=GRID)
ax1.legend(frameon=False, fontsize=9, loc="upper left")
ax1.set_ylim(0, max(k) * 1.05)

bars = ax2.bar([str(x) for x in k], delta,
               color=[GREEN if d < 0.5 else (BLUE if d < 2 else RED) for d in delta],
               width=0.6)
for b, d in zip(bars, delta):
    ax2.text(b.get_x() + b.get_width() / 2,
             d + (0.02 * max(delta) if d >= 0 else -0.06 * max(delta)),
             f"{d:+.2f}", ha="center", fontsize=9)
ax2.axhline(0, color=GREY, lw=1.2)
ax2.set_xlabel("Thread count k")
ax2.set_ylabel("Δ(k) = S_theo(k) − S_emp(k)")
ax2.set_title("The Amdahl Reality Gap", fontsize=11.5)
ax2.grid(alpha=0.3, ls="--", axis="y", color=GRID)

sub = f"Collatz stopping time, N = 19,015,000"
if T_seq:
    sub += f"   ·   T_seq = {T_seq:.4f} s"
fig.subplots_adjust(left=0.07, right=0.985, top=0.92, bottom=0.17, wspace=0.24)
fig.text(0.5, 0.035, sub, ha="center", fontsize=9.5, color=GREY)
fig.savefig("speedup_plot.png", dpi=200)
print("Wrote speedup_plot.png")
print(f"  derived p = {p:.6f}   S_max = {s_max:.4f}x")
print(f"  worst reality gap: Delta({k[worst]}) = {delta[worst]:+.3f}")
for kk, te, tt, dd, tk in zip(k, s_emp, s_theo, delta, t_k):
    print(f"    k={kk:>2}: T_k={tk:8.4f}s  S_emp={te:6.3f}x  S_theo={tt:6.3f}x  delta={dd:+6.3f}")
