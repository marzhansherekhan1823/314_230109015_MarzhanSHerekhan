"""
Master runner - executes the full lab suite and produces the required
terminal logfile 'results_<student_id>.txt' while echoing to your console.

Usage:
    python3 run_all.py <student_id>

Example:
    python3 run_all.py 210345

Notes:
  * Task 2 is invoked THREE separate times, as the execution protocol requires
    ("Run the benchmark 3 separate times to eliminate background OS scheduling
    noise"). Each invocation is a fresh process, which is what 'separate' means.
  * Task 4's memory suite allocates ~800 MB per worker at peak (a 400 MB array
    plus a 400 MB temporary). With 4 workers that is ~3.2 GB. Close other
    applications first. If your machine has 8 GB or less, the script warns you.
  * Total expected runtime: roughly 8-20 minutes depending on your silicon.
"""

import subprocess
import sys
import os
import time
import platform
from datetime import datetime

SCRIPTS = [
    ("HARDWARE TOPOLOGY DECLARATION", "collect_hardware.py", 1),
    ("TASK 1 - AMDAHL'S LAW & PHYSICAL SILICON SATURATION", "task1_amdahl.py", 1),
    ("TASK 2 - CACHE COHERENCE & FALSE SHARING", "task2_falsesharing.py", 3),
    ("TASK 3 - SYNCHRONIZATION TAX (unsafe vs locked)", "task3_sync.py", 1),
    ("TASK 3 - Q3.1 RACE CONDITION FORENSICS", "task3_race_forensics.py", 1),
    ("TASK 3 - Q3.2 LOCKLESS MAP-REDUCE REDESIGN", "task3_lockless.py", 1),
    ("TASK 4 - ROOFLINE: COMPUTE VS MEMORY WALL", "task4_roofline.py", 1),
    ("BONUS TASK - GIL AUTOPSY (T = 1..32)", "bonus_gil.py", 1),
]


class Tee:
    """Write to both the logfile and the live console."""
    def __init__(self, fh):
        self.fh = fh
    def write(self, text):
        self.fh.write(text)
        self.fh.flush()
        sys.__stdout__.write(text)
        sys.__stdout__.flush()


def check_memory():
    try:
        if platform.system() == "Linux":
            with open("/proc/meminfo") as fh:
                kb = int(fh.readline().split()[1])
            return kb / (1024 ** 2)
        if platform.system() == "Darwin":
            out = subprocess.run(["sysctl", "-n", "hw.memsize"],
                                 capture_output=True, text=True)
            return int(out.stdout.strip()) / (1024 ** 3)
    except Exception:
        pass
    return None


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 run_all.py <student_id>")
        sys.exit(1)

    student_id = sys.argv[1]
    logname = f"results_{student_id}.txt"

    assume_yes = "--yes" in sys.argv or not sys.stdin.isatty()

    gb = check_memory()
    if gb and gb < 9:
        print(f"WARNING: detected only {gb:.1f} GB RAM. Task 4's memory-bound "
              f"suite peaks near 3.2 GB with 4 workers.")
        print("Close other applications before continuing.")
        if not assume_yes:
            print("Press Enter to proceed, Ctrl-C to abort.")
            try:
                input()
            except (KeyboardInterrupt, EOFError):
                sys.exit(1)
        else:
            print("(--yes / non-interactive: proceeding automatically)")

    # Verify numpy is present for Task 4 before burning 15 minutes.
    try:
        import numpy  # noqa: F401
    except ImportError:
        print("ERROR: Task 4 needs numpy. Install it first:")
        print("   python3 -m pip install numpy")
        sys.exit(1)

    suite_start = time.perf_counter()

    with open(logname, "w", encoding="utf-8") as fh:
        tee = Tee(fh)
        hdr = [
            "=" * 72,
            "ADVANCED PARALLEL PROGRAMMING & ARCHITECTURE",
            "Laboratory Examination - Empirical Microarchitectural Bottlenecks",
            "=" * 72,
            f"Student ID      : {student_id}",
            f"Timestamp       : {datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')}",
            f"Host            : {platform.platform()}",
            f"Python          : {platform.python_implementation()} "
            f"{platform.python_version()}",
            f"Logical cores   : {os.cpu_count()}",
            "=" * 72,
            "",
        ]
        tee.write("\n".join(hdr))

        for title, script, repeats in SCRIPTS:
            if not os.path.exists(script):
                tee.write(f"\n!! MISSING SCRIPT: {script} - skipped\n")
                continue

            for run_idx in range(1, repeats + 1):
                label = title if repeats == 1 else f"{title}  [TRIAL {run_idx} of {repeats}]"
                tee.write("\n\n" + "#" * 72 + "\n")
                tee.write(f"# {label}\n")
                tee.write(f"# command: python3 {script}\n")
                tee.write(f"# started: {datetime.now().strftime('%H:%M:%S')}\n")
                tee.write("#" * 72 + "\n\n")

                t0 = time.perf_counter()
                proc = subprocess.run([sys.executable, script],
                                      capture_output=True, text=True)
                elapsed = time.perf_counter() - t0

                tee.write(proc.stdout)
                if proc.stderr.strip():
                    tee.write("\n--- stderr ---\n" + proc.stderr)
                tee.write(f"\n[wall clock for this invocation: {elapsed:.2f}s]\n")

        total = time.perf_counter() - suite_start
        tee.write("\n\n" + "=" * 72 + "\n")
        tee.write(f"SUITE COMPLETE - total wall clock {total / 60:.1f} minutes\n")
        tee.write(f"Logfile written: {logname}\n")
        tee.write("=" * 72 + "\n")

    print(f"\n\nDone. Submit this file: {os.path.abspath(logname)}")


if __name__ == "__main__":
    main()
