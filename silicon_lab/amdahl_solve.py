"""
Q1.2 / Q1.3 helper - derives the parallel fraction P and the asymptotic
speedup limit S_max from your measured timings, and prints the full algebraic
derivation with your numbers substituted in, so the working can be transcribed
straight onto the worksheet.

Usage:
    python3 amdahl_solve.py <T1> <Tp> [p]

    T1  measured single-process baseline time, seconds
    Tp  measured time at p workers, seconds
    p   worker count for Tp (default 4, which is what Q1.2 asks for)

Example:
    python3 amdahl_solve.py 1.6749 0.8822 4
"""

import sys


def solve(t1, tp, p):
    s = t1 / tp
    # S = 1 / [ (1-P) + P/p ]  =>  P = [p/(p-1)] * [(S-1)/S]
    P = (p / (p - 1)) * ((s - 1) / s)
    s_max = float("inf") if P >= 1.0 else 1.0 / (1.0 - P)
    return s, P, s_max


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    t1 = float(sys.argv[1])
    tp = float(sys.argv[2])
    p = int(sys.argv[3]) if len(sys.argv) > 3 else 4

    if p < 2:
        print("p must be at least 2 (P is undefined at p = 1).")
        sys.exit(1)

    s, P, s_max = solve(t1, tp, p)
    serial = 1.0 - P

    print("=" * 68)
    print(f"AMDAHL DERIVATION FROM MEASURED DATA  (p = {p})")
    print("=" * 68)
    print(f"  Measured T(1)  = {t1:.4f} s")
    print(f"  Measured T({p})  = {tp:.4f} s")
    print()
    print("STEP 1 - observed speedup")
    print(f"  S({p}) = T(1) / T({p}) = {t1:.4f} / {tp:.4f} = {s:.4f}")
    print()
    print("STEP 2 - substitute into Amdahl's Law and isolate P")
    print(f"  S({p}) = 1 / [ (1 - P) + P/{p} ]")
    print(f"  1 / S({p}) = 1 - P + P/{p}")
    print(f"  1 / S({p}) = 1 - P(1 - 1/{p}) = 1 - P({p - 1}/{p})")
    print(f"  P({p - 1}/{p}) = 1 - 1/S({p})")
    print(f"  P = [{p}/{p - 1}] * [1 - 1/S({p})]")
    print(f"  P = [{p / (p - 1):.6f}] * [1 - {1 / s:.6f}]")
    print(f"  P = [{p / (p - 1):.6f}] * [{1 - 1 / s:.6f}]")
    print(f"  P = {P:.6f}        ->  {100 * P:.2f}% parallelisable")
    print(f"  (1 - P) = {serial:.6f}  ->  {100 * serial:.2f}% irreducibly serial")
    print()
    print("STEP 3 - verification (substitute P back in)")
    check = 1.0 / (serial + P / p)
    print(f"  S({p}) = 1 / [ {serial:.6f} + {P:.6f}/{p} ]"
          f" = 1 / {serial + P / p:.6f} = {check:.4f}")
    print(f"  measured S({p}) = {s:.4f}   ->  "
          f"{'MATCH' if abs(check - s) < 1e-6 else 'MISMATCH'}")
    print()
    print("STEP 4 - asymptotic limit  S_max = lim(p->inf) S(p) = 1 / (1 - P)")
    if s_max == float("inf"):
        print("  P >= 1 - the measured speedup implies superlinear scaling,")
        print("  which means cache effects or a noisy baseline; re-measure T(1).")
    else:
        print(f"  S_max = 1 / (1 - {P:.6f}) = 1 / {serial:.6f} = {s_max:.4f}x")
    print()
    print("STEP 5 - the 128-core question (Q1.3)")
    if s_max != float("inf"):
        s128 = 1.0 / (serial + P / 128)
        print(f"  S(128) = 1 / [ {serial:.6f} + {P:.6f}/128 ] = {s128:.4f}x")
        print(f"  S_max  = {s_max:.4f}x  (the ceiling at infinite cores)")
        print(f"  S(128) reaches {100 * s128 / s_max:.2f}% of the ceiling.")
        print(f"  Efficiency at 128 cores = {100 * s128 / 128:.2f}% "
              f"({s128:.2f}x speedup for 128x the silicon)")
        print(f"  Cores needed to hit 90% of S_max: ", end="")
        target = 0.9 * s_max
        need = (P / (1 / target - serial)) if (1 / target - serial) > 0 else None
        print(f"{need:.0f}" if need and need > 0 else "unreachable")
        print()
        print("  Marginal value of the last core added:")
        for q in (16, 32, 64, 128):
            sq = 1.0 / (serial + P / q)
            print(f"    p = {q:>4}: S = {sq:6.3f}x   efficiency = "
                  f"{100 * sq / q:5.2f}%")
    print("=" * 68)


if __name__ == "__main__":
    main()
