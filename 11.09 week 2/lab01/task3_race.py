"""
TASK 3 - The Unsynchronized Shared Counter & Race Condition Trap
================================================================
10 parallel workers, each incrementing ONE shared integer 1,000,000 times
with no atomics and no locks. Theoretical total: 10 x 1,000,000 = 10,000,000.

Usage
-----
    python task3_race.py

Why this script runs the experiment TWICE
-----------------------------------------
PART A uses threading, exactly as the lab sheet words it. In CPython it will
return 10,000,000 every single time - no corruption at all. That is not the
race being absent, it is CPython's Global Interpreter Lock hiding it: the
interpreter only polls for a thread switch at loop back-edges and function
calls, never between the LOAD_GLOBAL / BINARY_OP / STORE_GLOBAL triple that
makes up `counter += 1`. So the read-modify-write completes before any other
thread can be scheduled, and the increment is atomic by accident of the
implementation.

PART B removes the GIL from the picture: 10 separate OS processes incrementing
one 32-bit integer in shared memory (multiprocessing.Value(..., lock=False)).
Now two real cores issue Load / Add / Store against the same cache line with
no coordination, updates are genuinely lost, and you get the corruption the
task is about - at the actual machine level Q3.1 asks you to reason about.

Report BOTH in your write-up. Part A is the honest reason the naive version
looks safe; Part B is the measurement. Fill the lab's Run #1-#10 table from
Part B, and cite Part A in your Q3.1 answer.
"""

import multiprocessing as mp
import threading
import time

WORKERS = 10
INCREMENTS = 1_000_000
RUNS = 10
EXPECTED = WORKERS * INCREMENTS

# --------------------------------------------------------------------------
# PART A - threads under the GIL
# --------------------------------------------------------------------------
counter = 0


def thread_worker():
    global counter
    for _ in range(INCREMENTS):
        counter += 1          # LOAD -> ADD -> STORE, uninterruptible in CPython


def run_threads():
    global counter
    counter = 0
    threads = [threading.Thread(target=thread_worker) for _ in range(WORKERS)]
    t0 = time.perf_counter()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return counter, (time.perf_counter() - t0) * 1000.0


# --------------------------------------------------------------------------
# PART B - processes on genuinely shared memory, no lock
# --------------------------------------------------------------------------
def proc_worker_unsafe(shared):
    for _ in range(INCREMENTS):
        shared.value += 1     # read cache line -> add -> write back. Racy.


def proc_worker_locked(shared):
    for _ in range(INCREMENTS):
        with shared.get_lock():
            shared.value += 1


def run_processes(locked: bool):
    if locked:
        shared = mp.Value("i", 0)            # carries its own mutex
        target = proc_worker_locked
    else:
        shared = mp.Value("i", 0, lock=False)  # raw shared int, no protection
        target = proc_worker_unsafe

    procs = [mp.Process(target=target, args=(shared,)) for _ in range(WORKERS)]
    t0 = time.perf_counter()
    for p in procs:
        p.start()
    for p in procs:
        p.join()
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    return (shared.value if locked else shared.value), elapsed_ms


def table(header, runner):
    print("\n" + "=" * 72)
    print(header)
    print("=" * 72)
    print(f"{'Run':>4} {'Measured Output':>18} {'Error (10^7-Act)':>18} "
          f"{'Lost %':>9} {'Time ms':>9}")
    print("-" * 72)
    times = []
    for i in range(1, RUNS + 1):
        value, ms = runner()
        times.append(ms)
        err = EXPECTED - value
        print(f"{'#' + str(i):>4} {value:>18,} {err:>18,} "
              f"{err / EXPECTED * 100:>8.2f}% {ms:>9.1f}")
    avg = sum(times) / len(times)
    print(f"{'avg':>4} {'':>18} {'':>18} {'':>9} {avg:>9.1f}")
    return avg


def main():
    print("=" * 72)
    print("TASK 3 - UNSYNCHRONIZED SHARED COUNTER")
    print("=" * 72)
    print(f"{WORKERS} workers x {INCREMENTS:,} increments")
    print(f"Theoretical expected total: {EXPECTED:,}")

    table("PART A - 10 THREADS (GIL-serialised - expect NO corruption)",
          run_threads)

    avg_unsafe = table(
        "PART B - 10 PROCESSES ON SHARED MEMORY, NO LOCK  <-- use this table",
        lambda: run_processes(locked=False))

    print("\n" + "=" * 72)
    print("Q3.2 - THE SYNCHRONIZATION PENALTY (same 10 processes, mutex added)")
    print("=" * 72)
    locked_value, locked_ms = run_processes(locked=True)
    print(f"  Unlocked = {avg_unsafe:9.1f} ms   result CORRUPTED")
    print(f"  Locked   = {locked_ms:9.1f} ms   result = {locked_value:,} "
          f"({'CORRECT' if locked_value == EXPECTED else 'WRONG'})")
    print(f"  Penalty  = {locked_ms / avg_unsafe:9.2f}x slower, "
          f"and now the answer is right.")
    print()


if __name__ == "__main__":       # REQUIRED on Windows - do not remove.
    mp.freeze_support()
    main()
