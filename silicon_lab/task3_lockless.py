"""
Q3.2 - Lockless Thread-Local Accumulator (Map-Reduce Partitioning)

Design contract:
  1. CORRECTNESS  - result must deterministically equal TOTAL_OPS on every run.
  2. PERFORMANCE  - must be strictly faster than LockedCounter by >= 2.0x.

Architecture:
  MAP phase     - each of the NUM_THREADS workers accumulates into a PRIVATE
                  function-local variable. A local is a slot in the thread's own
                  frame object, reached by the LOAD_FAST / STORE_FAST bytecodes.
                  It is unreachable from any other thread, so there is no shared
                  mutable state, no lock, no atomic, and no cache-line traffic.
  HANDOFF       - each worker performs exactly ONE write, to its own reserved
                  index in a pre-sized results list. Distinct indices, one write
                  each, all writes strictly before join() returns -> no race.
                  Slots are padded 16 apart so the handoff writes cannot even
                  share a 64-byte cache line (see Task 2).
  REDUCE phase  - after join(), the main thread is the only live thread, so the
                  final sum() needs no synchronisation whatsoever.
"""

import threading
import time

TOTAL_OPS = 2_000_000
NUM_THREADS = 4
PAD_STRIDE = 16          # 16 * 8 bytes = 128 bytes > one 64-byte cache line


class LockedCounter:
    """Baseline carried over from task3_sync.py for an in-process comparison."""
    def __init__(self):
        self.val = 0
        self.lock = threading.Lock()
    def inc(self):
        with self.lock:
            self.val += 1


def bench_locked():
    c = LockedCounter()
    ops_per_thread = TOTAL_OPS // NUM_THREADS
    def work():
        for _ in range(ops_per_thread):
            c.inc()
    threads = [threading.Thread(target=work) for _ in range(NUM_THREADS)]
    start = time.perf_counter()
    for t in threads: t.start()
    for t in threads: t.join()
    return c.val, time.perf_counter() - start


def bench_lockless():
    ops_per_thread = TOTAL_OPS // NUM_THREADS
    remainder = TOTAL_OPS - ops_per_thread * NUM_THREADS   # exactness guard
    partials = [0] * (NUM_THREADS * PAD_STRIDE)

    def work(slot, quota):
        # ---- MAP: private accumulation, zero shared state ----
        local_acc = 0
        for _ in range(quota):
            local_acc += 1
        # ---- HANDOFF: one write, to an index owned by this thread alone ----
        partials[slot * PAD_STRIDE] = local_acc

    quotas = [ops_per_thread] * NUM_THREADS
    quotas[0] += remainder                                 # never lose an op

    threads = [threading.Thread(target=work, args=(i, quotas[i]))
               for i in range(NUM_THREADS)]
    start = time.perf_counter()
    for t in threads: t.start()
    for t in threads: t.join()
    # ---- REDUCE: single-threaded, no synchronisation required ----
    total = sum(partials)
    return total, time.perf_counter() - start


if __name__ == "__main__":
    val_locked, t_locked = bench_locked()
    val_free, t_free = bench_lockless()

    print(f"LockedCounter (mutex)      : Value = {val_locked:,} | Time: {t_locked:.4f}s")
    print(f"Lockless Map-Reduce        : Value = {val_free:,} | Time: {t_free:.4f}s")
    print(f"Speedup over LockedCounter : {t_locked / t_free:.2f}x")
    print(f"Correctness (== {TOTAL_OPS:,})   : {'PASS' if val_free == TOTAL_OPS else 'FAIL'}")
    print(f"Performance (>= 2.00x)     : {'PASS' if t_locked / t_free >= 2.0 else 'FAIL'}")

    # Determinism proof: 5 consecutive runs must all land on TOTAL_OPS exactly.
    print("\nDeterminism check (5 consecutive runs):")
    for r in range(1, 6):
        v, t = bench_lockless()
        print(f"  run {r}: value = {v:,} | time = {t:.4f}s | "
              f"{'exact' if v == TOTAL_OPS else 'MISMATCH'}")
