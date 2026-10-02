import time, numpy as np, numba
from numba import njit, prange
print(f"Hardware Threads Detected: {numba.config.NUMBA_NUM_THREADS}")
@njit(parallel=True)
def monte_carlo_pi(n_samples):
    inside_circle = 0
    for i in prange(n_samples):
        x = np.random.uniform(0.0, 1.0)
        y = np.random.uniform(0.0, 1.0)
        if x*x + y*y <= 1.0:
            inside_circle += 1
    return (4.0 * inside_circle) / n_samples
_ = monte_carlo_pi(10_000)
SAMPLES = 120_000_000
thread_counts = sorted(set([t for t in [1,2,4,8,numba.config.NUMBA_NUM_THREADS] if t <= numba.config.NUMBA_NUM_THREADS]))
print(f"{'Threads':<10} | {'Time (s)':<12} | {'Speedup':<10} | {'Efficiency (%)':<15}")
print("-"*55)
for t in thread_counts:
    numba.set_num_threads(t)
    start = time.perf_counter(); pi_est = monte_carlo_pi(SAMPLES); elapsed = time.perf_counter()-start
    if t == 1: t1 = elapsed; sp=1.0; ef=100.0
    else: sp = t1/elapsed; ef = sp/t*100
    print(f"{t:<10} | {elapsed:<12.4f} | {sp:<10.2f}x | {ef:<15.1f}  pi={pi_est:.6f}")
