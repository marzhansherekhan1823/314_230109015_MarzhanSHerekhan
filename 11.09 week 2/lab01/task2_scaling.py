"""
TASK 2 - Multi-Thread Scaling Benchmark & Contention Wall
=========================================================
Workload  : prime counting by trial division (pure CPU, tiny memory footprint)
Runtime   : Python multiprocessing.Pool  (real OS processes -> real cores, no GIL)
Scaling   : STRONG scaling - total work is FIXED, only the number of workers changes.
            This is what Amdahl's law describes, so Task 4 depends on it.

Usage
-----
    python task2_scaling.py --calibrate      # find a good LIMIT for your machine
    python task2_scaling.py                  # run the full benchmark

Before you run the real thing:
    * plug the laptop into mains power
    * Windows Settings -> System -> Power -> Power mode = "Best performance"
    * close Chrome, Teams, Spotify, OneDrive sync...
    * open Task Manager -> Performance -> CPU, right-click graph ->
      "Change graph to" -> "Logical processors"   (this is your screenshot)
"""

import argparse
import csv
import multiprocessing as mp
import platform
import sys
import time

# ----------------------------------------------------------------------------
# TUNE THIS. Aim for an N=1 baseline of 8-20 seconds on your machine.
# Run with --calibrate first; the script will suggest a value.
# ----------------------------------------------------------------------------
LIMIT = 5_000_000

ITERATIONS = 3
THREAD_COUNTS = [1, 2, 4, 8, 16, 32]
CSV_PATH = "task2_results.csv"


def is_prime_odd(n: int) -> bool:
    """
    Trial division for an odd n >= 3. Deliberately naive: no sieve, no memory
    traffic, all ALU - so the benchmark measures core throughput rather than
    memory bandwidth.
    """
    f = 3
    while f * f <= n:
        if n % f == 0:
            return False
        f += 2
    return True


def count_stripe(args):
    """
    Count primes among the ODD candidates, striped across workers: worker k
    takes every stride-th odd number starting from 3 + 2k. Worker 0 also
    counts the prime 2, the only even one.

    Two decisions matter for load balance, and getting either wrong makes the
    benchmark measure the work split instead of the hardware:

    1. STRIPED, NOT BLOCKED. Testing a large n costs more than a small one
       (trial division runs to sqrt(n)), so giving worker 0 the block
       [2, limit/N) and worker N-1 the block [.., limit) would leave worker 0
       idle for most of the run.

    2. ODD CANDIDATES ONLY. Striping over *all* integers with stride N aliases
       against the workload's own structure: at N=2, worker 0 receives only
       even numbers, each rejected in a single modulo, so it finishes at once
       while worker 1 does the entire job alone - an apparent 1.0x speedup on
       two cores. Every even N loses half its workers this way. Enumerating
       only odd candidates removes the aliasing, and each worker's share then
       costs the same.
    """
    offset, stride, limit = args
    count = 1 if offset == 0 else 0          # the prime 2, counted once
    for n in range(3 + 2 * offset, limit, 2 * stride):
        if is_prime_odd(n):
            count += 1
    return count


def run_once(n_workers: int, limit: int):
    """One timed trial. Returns (t_total, t_compute, prime_count)."""
    tasks = [(k, n_workers, limit) for k in range(n_workers)]

    t_start = time.perf_counter()
    with mp.Pool(processes=n_workers) as pool:
        t_ready = time.perf_counter()          # workers now spawned
        partials = pool.map(count_stripe, tasks)
        t_done = time.perf_counter()           # compute finished
    t_end = time.perf_counter()                # pool joined / torn down

    return (t_end - t_start), (t_done - t_ready), sum(partials)


def calibrate():
    print("Calibrating on this machine (single worker)...\n")
    for limit in (200_000, 500_000, 1_000_000, 2_000_000, 3_500_000, 5_000_000):
        t_total, _, _ = run_once(1, limit)
        print(f"  LIMIT = {limit:>9,}  ->  {t_total:6.2f} s")
        if t_total >= 8.0:
            print(f"\nUse LIMIT = {limit:,}  (edit the LIMIT constant at the top).")
            return
    print("\nFast machine - keep the default LIMIT = 5_000_000.")


def main():
    print("=" * 74)
    print("TASK 2 - STRONG SCALING BENCHMARK")
    print("=" * 74)
    print(f"Host              : {platform.processor() or platform.machine()}")
    print(f"Python            : {sys.version.split()[0]}  ({platform.system()})")
    print(f"Logical CPUs seen : {mp.cpu_count()}")
    print(f"Workload          : count primes below {LIMIT:,} (trial division)")
    print(f"Runtime           : Python multiprocessing.Pool")
    print(f"Iterations per N  : {ITERATIONS}")
    print()

    rows = []
    baseline_avg = None
    reference_count = None

    for n in THREAD_COUNTS:
        runs, computes = [], []
        for i in range(ITERATIONS):
            t_total, t_compute, primes = run_once(n, LIMIT)
            runs.append(t_total)
            computes.append(t_compute)

            # Correctness guard: the answer must not depend on worker count.
            if reference_count is None:
                reference_count = primes
            elif primes != reference_count:
                sys.exit(f"FATAL: N={n} produced {primes} primes, "
                         f"expected {reference_count}. Work split is wrong.")

            print(f"  N={n:<3} run {i + 1}: {t_total:7.3f} s total "
                  f"({t_compute:7.3f} s compute)")

        avg = sum(runs) / len(runs)
        avg_compute = sum(computes) / len(computes)
        if baseline_avg is None:
            baseline_avg = avg

        speedup = baseline_avg / avg
        efficiency = speedup / n * 100.0
        rows.append({
            "Threads_N": n,
            "Run1_s": round(runs[0], 3),
            "Run2_s": round(runs[1], 3) if len(runs) > 1 else "",
            "Run3_s": round(runs[2], 3) if len(runs) > 2 else "",
            "AvgTime_TN_s": round(avg, 3),
            "AvgCompute_s": round(avg_compute, 3),
            "Speedup_SN": round(speedup, 3),
            "Efficiency_EN_pct": round(efficiency, 1),
        })
        print(f"  -> avg {avg:.3f} s | speedup {speedup:.2f}x | "
              f"efficiency {efficiency:.1f}%\n")

    # ---- the table you copy into the lab sheet --------------------------------
    print("=" * 74)
    print(f"{'N':>4} {'Run1':>8} {'Run2':>8} {'Run3':>8} {'AvgTN':>8} "
          f"{'S_N':>7} {'E_N':>8}")
    print("-" * 74)
    for r in rows:
        print(f"{r['Threads_N']:>4} {r['Run1_s']:>8} {r['Run2_s']:>8} "
              f"{r['Run3_s']:>8} {r['AvgTime_TN_s']:>8} "
              f"{r['Speedup_SN']:>6.2f}x {r['Efficiency_EN_pct']:>7.1f}%")
    print("=" * 74)

    with open(CSV_PATH, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nSaved -> {CSV_PATH}")
    print(f"Primes found (identical for every N): {reference_count:,}")

    t1 = rows[0]["AvgTime_TN_s"]
    t2 = next(r["AvgTime_TN_s"] for r in rows if r["Threads_N"] == 2)
    print(f"\nCarry into TASK 4:   T1 = {t1} s    T2 = {t2} s")

    best = max(rows, key=lambda r: r["Speedup_SN"])
    print(f"Peak speedup: {best['Speedup_SN']:.2f}x at N={best['Threads_N']} "
          f"-> this is your contention wall (Q2.1).")


if __name__ == "__main__":          # REQUIRED on Windows - do not remove.
    mp.freeze_support()
    ap = argparse.ArgumentParser()
    ap.add_argument("--calibrate", action="store_true",
                    help="suggest a LIMIT that gives an 8-20 s baseline")
    args = ap.parse_args()
    calibrate() if args.calibrate else main()
