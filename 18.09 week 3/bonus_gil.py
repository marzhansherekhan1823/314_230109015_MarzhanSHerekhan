"""
BONUS TASK - The GIL Autopsy.
The cpu_work() logic below is copy-pasted verbatim and is NOT modified.
Harness runs total_work = 50,000,000 split across T workers, T in [1,2,4,8,16,32],
for BOTH threading.Thread and multiprocessing.Pool, and emits a CSV for plotting.
"""

import time
from multiprocessing import Pool
import threading
import os
import csv
import sys


def cpu_work(n):
    # Pure CPU crunch
    count = 0
    for i in range(n):
        count += i * i
    return count


# Run both experiments with total_work = 50_000_000 split across T workers
# Test T in [1, 2, 4, 8, 16, 32]
TOTAL_WORK = 50_000_000
THREAD_COUNTS = [1, 2, 4, 8, 16, 32]


def run_threading(t_count):
    chunk = TOTAL_WORK // t_count
    threads = [threading.Thread(target=cpu_work, args=(chunk,)) for _ in range(t_count)]
    start = time.perf_counter()
    for t in threads: t.start()
    for t in threads: t.join()
    return time.perf_counter() - start


def run_multiprocessing(p_count):
    chunk = TOTAL_WORK // p_count
    start = time.perf_counter()
    with Pool(processes=p_count) as pool:
        pool.map(cpu_work, [chunk] * p_count)
    return time.perf_counter() - start


if __name__ == "__main__":
    print(f"OS Reported Logical Cores: {os.cpu_count()}")
    print(f"Python Runtime: {sys.version.split()[0]} ({sys.implementation.name})")
    print(f"Fixed Total Work: {TOTAL_WORK:,} iterations (strong scaling)\n")

    print(f"{'T':>4} | {'threading.Thread [s]':>20} | {'multiprocessing.Pool [s]':>24} | "
          f"{'Thread Speedup':>14} | {'Process Speedup':>15}")
    print("-" * 92)

    rows = []
    base_thread = None
    base_proc = None

    for t_count in THREAD_COUNTS:
        t_thread = run_threading(t_count)
        t_proc = run_multiprocessing(t_count)
        if base_thread is None:
            base_thread, base_proc = t_thread, t_proc
        s_thread = base_thread / t_thread
        s_proc = base_proc / t_proc
        print(f"{t_count:>4} | {t_thread:>20.4f} | {t_proc:>24.4f} | "
              f"{s_thread:>13.2f}x | {s_proc:>14.2f}x")
        rows.append({
            "workers": t_count,
            "threading_seconds": round(t_thread, 4),
            "multiprocessing_seconds": round(t_proc, 4),
            "threading_speedup": round(s_thread, 3),
            "multiprocessing_speedup": round(s_proc, 3),
        })

    with open("bonus_curve.csv", "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    fastest = min(rows, key=lambda r: r["multiprocessing_seconds"])
    print(f"\nMultiprocessing wall-clock minimum at T = {fastest['workers']} "
          f"({fastest['multiprocessing_seconds']:.4f}s)")
    print("-> Inflection cliff = the first T after this where time increases.")
    print("Wrote bonus_curve.csv for the empirical curve plot.")
