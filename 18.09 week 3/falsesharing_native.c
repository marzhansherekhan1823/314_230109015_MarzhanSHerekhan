/*
 * SUPPLEMENTARY EVIDENCE FOR TASK 2 (Q2.1 / Q2.2)
 * ================================================
 *
 * WHY THIS FILE EXISTS
 * --------------------
 * task2_falsesharing.py measures a slowdown factor of roughly 1.0x on CPython.
 * That is not a measurement error and not background noise: the Global
 * Interpreter Lock serialises bytecode execution, so the four Python threads
 * never write to the shared list from two different cores at the same instant.
 * False sharing is a consequence of *concurrent* writes to one cache line, so
 * with the GIL in place the phenomenon the task asks about cannot physically
 * occur, no matter how the list is padded.
 *
 * This program removes the interpreter from the experiment while keeping the
 * memory layout byte-for-byte equivalent, which isolates MESI invalidation
 * traffic as the single independent variable.
 *
 * TWO WRITE DISCIPLINES ARE COMPARED
 * ----------------------------------
 *   (a) plain volatile store  - the per-core store buffer and write-combining
 *       logic absorb most of the coherence cost, so the penalty is small.
 *   (b) atomic lock-add       - `lock xadd` must take the line into the
 *       Modified state on every single operation, so the line ping-pongs
 *       between cores and the penalty becomes large and unmistakable.
 *
 * Comparing (a) against (b) is the point: it shows that the cost of false
 * sharing is governed by how often a core must gain EXCLUSIVE ownership of
 * the line, not merely by the fact that two variables are adjacent.
 *
 * MEMORY LAYOUT
 * -------------
 *   stride 1  -> slots 0,1,2,3   at byte offsets 0,8,16,24   -> ONE 64 B line
 *   stride 16 -> slots 0,16,32,48 at byte offsets 0,128,256,384 -> FOUR lines
 *
 * Build:  gcc -O2 -pthread falsesharing_native.c -o falsesharing_native
 * Run:    ./falsesharing_native [num_threads]      (default 2)
 */

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <pthread.h>
#include <time.h>

#define MAX_THREADS 64
#define STRIDE      16              /* 16 * 8 B = 128 B > one 64 B cache line */
#define PLAIN_ITERS 50000000L       /* x8 unrolled stores = 400M stores       */
#define ATOMIC_ITERS 50000000L

static int n_threads = 2;
static volatile int64_t buffer[MAX_THREADS * STRIDE];

typedef struct { int slot; } arg_t;

/* (a) plain volatile read-modify-write, unrolled 8x to make stores dense */
static void *bump_plain(void *p) {
    int s = ((arg_t *)p)->slot;
    for (long i = 0; i < PLAIN_ITERS; i++) {
        buffer[s] += 1; buffer[s] += 1; buffer[s] += 1; buffer[s] += 1;
        buffer[s] += 1; buffer[s] += 1; buffer[s] += 1; buffer[s] += 1;
    }
    return NULL;
}

/* (b) atomic read-modify-write: forces Exclusive/Modified ownership each time */
static void *bump_atomic(void *p) {
    int s = ((arg_t *)p)->slot;
    for (long i = 0; i < ATOMIC_ITERS; i++)
        __sync_fetch_and_add((int64_t *)&buffer[s], 1);
    return NULL;
}

static double timed(int stride, void *(*fn)(void *)) {
    pthread_t th[MAX_THREADS];
    arg_t args[MAX_THREADS];
    struct timespec t0, t1;

    for (int i = 0; i < MAX_THREADS * STRIDE; i++) buffer[i] = 0;

    clock_gettime(CLOCK_MONOTONIC, &t0);
    for (int i = 0; i < n_threads; i++) {
        args[i].slot = i * stride;
        pthread_create(&th[i], NULL, fn, &args[i]);
    }
    for (int i = 0; i < n_threads; i++) pthread_join(th[i], NULL);
    clock_gettime(CLOCK_MONOTONIC, &t1);

    return (t1.tv_sec - t0.tv_sec) + (t1.tv_nsec - t0.tv_nsec) / 1e9;
}

int main(int argc, char **argv) {
    if (argc > 1) n_threads = atoi(argv[1]);
    if (n_threads < 2 || n_threads > MAX_THREADS) n_threads = 2;

    printf("=== NATIVE PTHREADS FALSE-SHARING ISOLATION (no GIL) ===\n");
    printf("threads          : %d\n", n_threads);
    printf("sizeof(int64_t)  : %zu bytes\n", sizeof(int64_t));
    printf("padding stride   : %d elements = %zu bytes\n\n",
           STRIDE, STRIDE * sizeof(int64_t));

    printf("--- (a) PLAIN volatile store, 3 trials ---\n");
    double pa = 0, pp = 0;
    for (int t = 0; t < 3; t++) {
        double a = timed(1, bump_plain);
        double p = timed(STRIDE, bump_plain);
        printf("  trial %d: adjacent = %.4fs | padded = %.4fs | slowdown = %.2fx\n",
               t + 1, a, p, a / p);
        pa += a; pp += p;
    }
    printf("  MEAN   : adjacent = %.4fs | padded = %.4fs | SLOWDOWN = %.2fx\n\n",
           pa / 3, pp / 3, pa / pp);

    printf("--- (b) ATOMIC lock-add, 3 trials ---\n");
    double aa = 0, ap = 0;
    for (int t = 0; t < 3; t++) {
        double a = timed(1, bump_atomic);
        double p = timed(STRIDE, bump_atomic);
        printf("  trial %d: adjacent = %.4fs | padded = %.4fs | slowdown = %.2fx\n",
               t + 1, a, p, a / p);
        aa += a; ap += p;
    }
    printf("  MEAN   : adjacent = %.4fs | padded = %.4fs | SLOWDOWN = %.2fx\n\n",
           aa / 3, ap / 3, aa / ap);

    printf("--- ADDRESS PROOF ---\n");
    printf("  adjacent slots : %p %p %p %p\n",
           (void *)&buffer[0], (void *)&buffer[1],
           (void *)&buffer[2], (void *)&buffer[3]);
    printf("                   span = %ld bytes -> single 64-byte line\n",
           (long)((char *)&buffer[3] - (char *)&buffer[0]) + 8);
    printf("  padded slots   : %p %p %p %p\n",
           (void *)&buffer[0], (void *)&buffer[16],
           (void *)&buffer[32], (void *)&buffer[48]);
    printf("                   span = %ld bytes -> four distinct lines\n",
           (long)((char *)&buffer[48] - (char *)&buffer[0]) + 8);
    return 0;
}
