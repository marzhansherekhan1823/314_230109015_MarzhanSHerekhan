"""
TASK 4 - Empirical Amdahl Verification vs Gustafson Scaling Horizon
===================================================================
Feed it the T1 and T2 that task2_scaling.py printed. It does the four boxes
on the lab sheet and shows the arithmetic so you can hand-check it.

Usage
-----
    python task4_amdahl.py 12.41 6.58
    python task4_amdahl.py            # then type the values when prompted
"""

import sys


def main():
    if len(sys.argv) == 3:
        t1, t2 = float(sys.argv[1]), float(sys.argv[2])
    else:
        t1 = float(input("T1 (avg 1-worker time, seconds)  : "))
        t2 = float(input("T2 (avg 2-worker time, seconds)  : "))

    print("\n" + "=" * 62)
    print("BOX 1 - PARALLEL FRACTION DERIVATION")
    print("=" * 62)
    print(f"  T1 = {t1:.3f} s      T2 = {t2:.3f} s")
    p = 2.0 * (t1 - t2) / t1
    print(f"  p  = 2 x (T1 - T2) / T1")
    print(f"     = 2 x ({t1:.3f} - {t2:.3f}) / {t1:.3f}")
    print(f"     = 2 x {t1 - t2:.3f} / {t1:.3f}")
    print(f"     = {p:.4f}")

    if p > 1.0:
        print("\n  !! p > 1.0, which is physically impossible.")
        print("     T2 came out less than half of T1 - superlinear speedup.")
        print("     Usual cause: the 2-worker run got more cache per worker,")
        print("     or the N=1 run was measured while the CPU was still cold /")
        print("     another process was competing. Re-run task2_scaling.py with")
        print("     everything else closed. If it persists, clamp p to 1.0 and")
        print("     say in Q4.1 why your measurement exceeded the model.")
        p = min(p, 1.0)
    if p < 0.0:
        print("\n  !! p < 0.0: T2 was SLOWER than T1. Parallel overhead exceeded")
        print("     the benefit - either the workload is too small (raise LIMIT)")
        print("     or spawn cost dominated. Re-run with a bigger LIMIT.")
        return

    serial = 1.0 - p
    print(f"\n  Sequential fraction (1 - p) = {serial:.4f}  "
          f"({serial * 100:.2f}% of the runtime cannot be parallelised)")

    print("\n" + "=" * 62)
    print("BOX 2 - AMDAHL THEORETICAL SPEEDUP CEILING")
    print("=" * 62)
    if serial <= 0:
        print("  S_max = 1 / (1 - p) = 1 / 0 -> unbounded (p measured as 1.0)")
        smax = float("inf")
    else:
        smax = 1.0 / serial
        print(f"  S_max = 1 / (1 - p) = 1 / {serial:.4f} = {smax:.3f}x")
        print(f"  Infinite cores buy you at most {smax:.2f}x. Ever.")

    print("\n" + "=" * 62)
    print("BOX 3 - AMDAHL 64-CORE PROJECTION (strong scaling)")
    print("=" * 62)
    denom = serial + p / 64.0
    s64 = 1.0 / denom
    print(f"  S_64 = 1 / [(1 - p) + (p / 64)]")
    print(f"       = 1 / [{serial:.4f} + {p / 64.0:.6f}]")
    print(f"       = 1 / {denom:.6f}")
    print(f"       = {s64:.3f}x")
    if smax != float("inf"):
        print(f"  That is {s64 / smax * 100:.1f}% of the theoretical ceiling, "
              f"on 64x the hardware.")

    print("\n" + "=" * 62)
    print("BOX 4 - GUSTAFSON SCALED SPEEDUP (weak scaling)")
    print("=" * 62)
    sg = serial + p * 64.0
    print(f"  S_gustafson = (1 - p) + (p x 64)")
    print(f"              = {serial:.4f} + {p * 64.0:.4f}")
    print(f"              = {sg:.3f}x")

    print("\n" + "=" * 62)
    print("NUMBERS FOR THE Q4.1 PARAGRAPH")
    print("=" * 62)
    print(f"  p                    = {p:.4f}")
    print(f"  1 - p                = {serial:.4f}")
    print(f"  Amdahl S_max         = {smax:.2f}x")
    print(f"  Amdahl S_64          = {s64:.2f}x")
    print(f"  Gustafson S_64       = {sg:.2f}x")
    print(f"  Gap between models   = {sg / s64:.1f}x")
    print("\n  The two models disagree because they hold different things")
    print("  fixed: Amdahl fixes the PROBLEM SIZE and asks how fast 64 cores")
    print("  finish it, so the serial region becomes a larger and larger share")
    print("  of the runtime until it is all that is left. Gustafson fixes the")
    print("  TIME BUDGET and lets the problem grow 64x, so the serial region")
    print("  stays a constant number of seconds while the parallel work grows")
    print("  around it. Same algorithm, same p - opposite conclusions.\n")


if __name__ == "__main__":
    main()
