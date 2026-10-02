import time, numpy as np, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from numba import njit, prange
@njit(parallel=True)
def render_mandelbrot_rows(h, w, max_iter):
    img = np.zeros((h, w), dtype=np.int32)
    for r in prange(h):
        cy = -1.2 + (r / h) * 2.4
        for c in range(w):
            cx = -2.0 + (c / w) * 2.5
            zr, zi = 0.0, 0.0; it = 0
            while (zr*zr + zi*zi <= 4.0) and (it < max_iter):
                nr = zr*zr - zi*zi + cx; zi = 2.0*zr*zi + cy; zr = nr; it += 1
            img[r, c] = it
    return img
@njit(parallel=True)
def render_mandelbrot_cols(h, w, max_iter):
    img = np.zeros((h, w), dtype=np.int32)
    for c in prange(w):
        cx = -2.0 + (c / w) * 2.5
        for r in range(h):
            cy = -1.2 + (r / h) * 2.4
            zr, zi = 0.0, 0.0; it = 0
            while (zr*zr + zi*zi <= 4.0) and (it < max_iter):
                nr = zr*zr - zi*zi + cx; zi = 2.0*zr*zi + cy; zr = nr; it += 1
            img[r, c] = it
    return img
_ = render_mandelbrot_rows(100,100,50); _ = render_mandelbrot_cols(100,100,50)
H, W, MAX_IT = 2500, 2500, 1000
t0=time.perf_counter(); g=render_mandelbrot_rows(H,W,MAX_IT); t_rows=time.perf_counter()-t0
t1=time.perf_counter(); gc=render_mandelbrot_cols(H,W,MAX_IT); t_cols=time.perf_counter()-t1
print(f"Row-Parallel Render Time:    {t_rows:.3f} s"); print(f"Column-Parallel Render Time: {t_cols:.3f} s")
plt.figure(figsize=(8,8)); plt.imshow(g, cmap='magma', extent=[-2.0,0.5,-1.2,1.2])
plt.title(f"Mandelbrot {H}x{W} (Render: {t_rows:.2f}s)"); plt.axis('off')
plt.savefig('mandelbrot_output.png', dpi=300, bbox_inches='tight'); print("Saved image: mandelbrot_output.png")
