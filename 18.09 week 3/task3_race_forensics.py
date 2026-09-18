"""
SUPPLEMENTARY EVIDENCE FOR TASK 3 (Q3.1)
========================================

WHY THIS FILE EXISTS
--------------------
task3_sync.py runs the prescribed UnsafeCounter and, on a standard CPython
build, frequently reports NO corruption at all: the value comes out at exactly
2,000,000. The worksheet asks for "your exact corrupted count", so the zero has
to be explained rather than wished away.

The explanation is located in the CPython evaluation loop, and this script
proves it empirically in four stages:

  STAGE 1  Disassemble UnsafeCounter.inc() and show that the read-modify-write
           is the straight-line sequence LOAD_ATTR -> BINARY_OP -> STORE_ATTR
           with no interruptible instruction between the load and the store.

  STAGE 2  Run the prescribed counter N times at the default 5 ms switch
           interval and record the defect count.

  STAGE 3  Re-run it with sys.setswitchinterval() driven to its floor, which
           makes the interpreter release the GIL as aggressively as it is able.
           The program logic is untouched; only the scheduler granularity of
           the host runtime changes.

  STAGE 4  Run an INSTRUMENTED variant in which the read and the write are
           separated by a Python-level function call. A call boundary is a
           point where CPython evaluates its eval_breaker and may therefore
           hand the GIL to another thread. This opens the lost-update window
           and the race becomes reproducible and severe.

Stage 4 is the control that proves stages 2 and 3 are not measuring a broken
experiment: the race condition is real and the hardware/runtime will exhibit
it the moment a preemption point exists inside the critical section.

On a free-threaded build (PEP 703, python3.13t+ with the GIL disabled) stage 2
is expected to corrupt heavily on its own, and the script reports that.
"""

import threading
import sys
import dis
import io

TOTAL_OPS = 2_000_000
NUM_THREADS = 4
TRIALS = 5


class UnsafeCounter:
    """Prescribed worksheet code, unmodified."""
    def __init__(self): self.val = 0
    def inc(self): self.val += 1


def _addend():
    """Returns 1. Exists purely to place a CALL between the load and the store."""
    return 1


class InstrumentedCounter:
    """
    Semantically identical to UnsafeCounter (adds one to self.val), but the
    read-modify-write is split by a function call, which is an interpreter
    preemption point. This exposes the lost-update window.
    """
    def __init__(self): self.val = 0
    def inc(self): self.val = self.val + _addend()


def run(counter_cls, total_ops=TOTAL_OPS, n_threads=NUM_THREADS):
    c = counter_cls()
    ops = total_ops // n_threads
    def work():
        for _ in range(ops):
            c.inc()
    threads = [threading.Thread(target=work) for _ in range(n_threads)]
    for t in threads: t.start()
    for t in threads: t.join()
    expected = ops * n_threads
    return c.val, expected


def report(label, counter_cls, trials=TRIALS):
    print(f"\n{label}")
    print("-" * len(label))
    losses = []
    for i in range(1, trials + 1):
        val, expected = run(counter_cls)
        lost = expected - val
        losses.append(lost)
        pct = 100.0 * lost / expected
        status = "NO DEFECT" if lost == 0 else f"{lost:,} LOST UPDATES"
        print(f"  trial {i}: value = {val:>9,} / {expected:,}  "
              f"defect = {pct:6.2f}%  -> {status}")
    worst = max(losses)
    print(f"  summary: {sum(1 for l in losses if l)} of {trials} trials corrupted, "
          f"worst-case defect count = {worst:,}")
    return losses


def gil_status():
    if hasattr(sys, "_is_gil_enabled"):
        return "DISABLED (free-threaded build)" if not sys._is_gil_enabled() \
               else "ENABLED"
    return "ENABLED (build predates PEP 703 runtime toggle)"


def main():
    print("=" * 72)
    print("TASK 3 / Q3.1 - RACE CONDITION FORENSICS")
    print("=" * 72)
    print(f"Python          : {sys.version.split()[0]} ({sys.implementation.name})")
    print(f"GIL             : {gil_status()}")
    print(f"Switch interval : {sys.getswitchinterval()} s (default)")
    print(f"Threads         : {NUM_THREADS}   Target sum: {TOTAL_OPS:,}")

    # ---------------- STAGE 1: bytecode evidence ----------------
    print("\n" + "=" * 72)
    print("STAGE 1 - BYTECODE OF THE UNPROTECTED CRITICAL SECTION")
    print("=" * 72)
    buf = io.StringIO()
    dis.dis(UnsafeCounter.inc, file=buf)
    listing = buf.getvalue()
    print(listing)
    print("Read the sequence: the value is loaded by LOAD_ATTR, incremented by")
    print("BINARY_OP, and written back by STORE_ATTR. Between the load and the")
    print("store there is no CALL, no backward jump and no RESUME - and those")
    print("are precisely the instructions at which CPython tests its eval_breaker")
    print("and may release the GIL. The window in which another thread could")
    print("read a stale value is therefore never opened by this code.")

    print("\nContrast - the instrumented variant:")
    buf2 = io.StringIO()
    dis.dis(InstrumentedCounter.inc, file=buf2)
    print(buf2.getvalue())
    print("Here a CALL (and the callee's RESUME) sits between the load of")
    print("self.val and the STORE_ATTR that writes it back. That is a legal")
    print("GIL hand-off point inside the read-modify-write sequence.")

    # ---------------- STAGE 2: default interval ----------------
    print("\n" + "=" * 72)
    print("STAGE 2 - PRESCRIBED CODE, DEFAULT 5 ms SWITCH INTERVAL")
    print("=" * 72)
    default_losses = report("UnsafeCounter as written", UnsafeCounter)

    # ---------------- STAGE 3: forced preemption ----------------
    print("\n" + "=" * 72)
    print("STAGE 3 - PRESCRIBED CODE, SWITCH INTERVAL DRIVEN TO ITS FLOOR")
    print("=" * 72)
    original = sys.getswitchinterval()
    sys.setswitchinterval(1e-9)
    print(f"sys.setswitchinterval(1e-9) -> effective {sys.getswitchinterval()} s")
    print("Program logic is unchanged; only the runtime's scheduling granularity")
    print("has been made as fine as the interpreter permits.")
    forced_losses = report("UnsafeCounter under maximal preemption pressure",
                           UnsafeCounter)
    sys.setswitchinterval(original)

    # ---------------- STAGE 4: instrumented control ----------------
    print("\n" + "=" * 72)
    print("STAGE 4 - CONTROL: PREEMPTION POINT INSIDE THE CRITICAL SECTION")
    print("=" * 72)
    sys.setswitchinterval(1e-9)
    instrumented_losses = report(
        "InstrumentedCounter (load and store split by a CALL)",
        InstrumentedCounter)
    sys.setswitchinterval(original)

    # ---------------- verdict ----------------
    print("\n" + "=" * 72)
    print("VERDICT")
    print("=" * 72)
    d_max = max(default_losses)
    f_max = max(forced_losses)
    i_max = max(instrumented_losses)
    print(f"  Stage 2 (as written, 5 ms)      worst defect count = {d_max:,}")
    print(f"  Stage 3 (as written, forced)    worst defect count = {f_max:,}")
    print(f"  Stage 4 (instrumented, forced)  worst defect count = {i_max:,}")
    print()
    if d_max == 0 and f_max == 0 and i_max > 0:
        print("  CONCLUSION: on this runtime the prescribed `self.val += 1` is")
        print("  not interruptible between its load and its store, so it loses")
        print("  no updates. The race condition is nevertheless real: inserting")
        print("  a single preemption point into the same logical operation")
        print(f"  destroys {100.0 * i_max / TOTAL_OPS:.1f}% of the increments.")
        print("  The unprotected counter is therefore unsafe by construction and")
        print("  safe only by accident of the current interpreter's instruction")
        print("  dispatch - which is exactly why the lock is not optional.")
    elif d_max > 0 or f_max > 0:
        print("  CONCLUSION: the prescribed counter corrupts directly on this")
        print("  runtime. Quote the worst-case defect count above as the answer")
        print("  to Q3.1 and cite the LOAD/ADD/STORE interleaving as the cause.")
    else:
        print("  CONCLUSION: no stage corrupted. Re-run with more threads or")
        print("  report the null result together with the Stage 1 bytecode")
        print("  evidence, which explains it.")


if __name__ == "__main__":
    main()
