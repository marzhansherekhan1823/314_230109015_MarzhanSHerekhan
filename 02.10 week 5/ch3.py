import time, sys, numpy as np
from numba import njit, prange
DT = np.float32 if (len(sys.argv)>1 and sys.argv[1]=="32") else np.float64
@njit(parallel=True)
def heat_step(u, u_next, alpha=0.20):
    rows, cols = u.shape
    for i in prange(1, rows-1):
        for j in range(1, cols-1):
            u_next[i,j] = u[i,j] + alpha*(u[i+1,j]+u[i-1,j]+u[i,j+1]+u[i,j-1]-4.0*u[i,j])
G, STEPS = 1500, 300
u = np.zeros((G,G), dtype=DT); un = np.zeros_like(u)
u[0,:]=100.0; u[:,0]=100.0; un[0,:]=100.0; un[:,0]=100.0
heat_step(u, un)
s=time.perf_counter()
for _ in range(STEPS):
    heat_step(u, un); u, un = un, u
e=time.perf_counter()-s
print(f"dtype={DT.__name__}  Heat Diffusion Complete: {e:.3f} s  Throughput: {G*G*STEPS/e/1e6:.2f} Megacells/sec")
