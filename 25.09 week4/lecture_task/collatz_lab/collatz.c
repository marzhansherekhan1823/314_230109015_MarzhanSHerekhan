/* =====================================================================
 * PRACTICUM: THE AMDAHL REALITY GAP
 * Collatz Stopping-Time Benchmark with OpenMP
 * ---------------------------------------------------------------------
 * Student : Marzhan Sherekhan
 * ID      : 230109015
 * Workload: N = 10,000,000 + (9015 * 1,000) = 19,015,000
 *
 * COMPILATION (as specified by the worksheet):
 *     gcc -O2 -fopenmp collatz.c -o collatz
 *
 * EXECUTION:
 *     ./collatz                  run every phase, write results.csv
 *     ./collatz <threads>        override the thread count used for the
 *                                Phase 4 experiments (default: the value
 *                                reported by omp_get_max_threads())
 *
 * WHAT THIS PROGRAM DOES
 *   Phase 2  Sequential baseline. No OpenMP pragma at all, so T_seq is a
 *            true serial reference rather than a one-thread parallel run.
 *   Phase 3  OpenMP scaling sweep over k = 1, 2, 4, 8, 16 threads.
 *   Phase 4A False-sharing experiment: a naive per-thread counter array
 *            against an OpenMP reduction.
 *   Phase 4B Loop-scheduling comparison across five schedule clauses.
 *
 * BENCHMARKING PROTOCOL (Step 2.2)
 *   Every configuration is executed three times. Run 1 is discarded as a
 *   cold-cache / page-allocation warm-up; the reported time is the mean
 *   of runs 2 and 3. All timing uses omp_get_wtime() for sub-microsecond
 *   wall-clock precision -- clock() is deliberately NOT used, since it
 *   measures aggregate CPU time across threads and would make a parallel
 *   run appear slower the more cores it used.
 *
 * ANTI-CHEAT CHECKSUM
 *   The sum of every stopping time in [1, N], taken modulo 1,000,000,007.
 *   Addition is commutative and associative, so this value is invariant
 *   under thread count and scheduling policy: every configuration below
 *   must produce an identical checksum, which is what proves the parallel
 *   versions are actually computing the same thing as the serial one.
 * ===================================================================== */

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <inttypes.h>
#include <string.h>
#include <omp.h>

/* ---------------------------------------------------------- constants */

#define STUDENT_ID   230109015ULL
#define LAST4        (STUDENT_ID % 10000ULL)          /* 9015            */
#define WORKLOAD_N   (10000000ULL + LAST4 * 1000ULL)  /* 19,015,000      */
#define MODULUS      1000000007ULL
#define MAX_THREADS  256
#define TOTAL_RUNS   3          /* run 1 discarded, runs 2 and 3 averaged */
#define HIT_THRESHOLD 100       /* Experiment A: steps > 100              */

static const int THREAD_COUNTS[] = { 1, 2, 4, 8, 16 };
#define N_THREAD_COUNTS ((int)(sizeof(THREAD_COUNTS) / sizeof(THREAD_COUNTS[0])))

/* ------------------------------------------------- computational kernel */

/* Collatz stopping time: number of 3x+1 steps required for n to reach 1.
   Uses (n & 1) for the parity test and n >>= 1 for the halving, so the
   inner loop compiles to a branch plus shift/lea rather than an integer
   division. */
static inline uint32_t collatz_steps(uint64_t n) {
    uint32_t steps = 0;
    while (n > 1) {
        if ((n & 1) == 0) n >>= 1;
        else n = 3 * n + 1;
        steps++;
    }
    return steps;
}

/* ------------------------------------------------------- result record */

typedef struct {
    uint32_t max_steps;      /* longest stopping time found in [1, N]     */
    uint64_t checksum;       /* sum of all stopping times mod 1e9+7       */
    uint64_t hits;           /* count of i whose stopping time > 100      */
} Result;

static int results_equal(Result a, Result b) {
    return a.max_steps == b.max_steps
        && a.checksum  == b.checksum
        && a.hits      == b.hits;
}

/* ============================ PHASE 2: SEQUENTIAL BASELINE ============ */

static Result run_sequential(void) {
    uint32_t max_steps = 0;
    uint64_t sum = 0, hits = 0;

    for (uint64_t i = 1; i <= WORKLOAD_N; i++) {
        uint32_t s = collatz_steps(i);
        if (s > max_steps) max_steps = s;
        sum += s;
        if (s > HIT_THRESHOLD) hits++;
    }
    Result r = { max_steps, sum % MODULUS, hits };
    return r;
}

/* ============================ PHASE 3: OPENMP SCALING ================= */

static Result run_parallel(int threads) {
    uint32_t max_steps = 0;
    uint64_t sum = 0, hits = 0;

    #pragma omp parallel for num_threads(threads) schedule(static) \
            reduction(max:max_steps) reduction(+:sum) reduction(+:hits)
    for (int64_t i = 1; i <= (int64_t)WORKLOAD_N; i++) {
        uint32_t s = collatz_steps((uint64_t)i);
        if (s > max_steps) max_steps = s;
        sum += s;
        if (s > HIT_THRESHOLD) hits++;
    }
    Result r = { max_steps, sum % MODULUS, hits };
    return r;
}

/* ============ PHASE 4A: FALSE SHARING ================================= */

/* Five counter disciplines are measured. The first two are the variants
   the worksheet prescribes; the third is the padded-struct alternative it
   also permits; the last two are a supplementary isolation experiment
   explained below.
 *
 * IMPORTANT MEASUREMENT CAVEAT (see the written analysis, Q1):
 *   Variant 1 as specified does NOT generate false sharing when compiled
 *   with -O2. OpenMP's memory model lets the compiler assume the program
 *   is free of data races, so GCC is entitled to keep hit_count[tid] in a
 *   register for the whole loop and store it back once at the end.
 *   Inspecting the generated assembly confirms this: the only reference
 *   to hit_count is a single `leaq` that loads its ADDRESS before the
 *   loop begins, and no store instruction appears inside the loop body.
 *   With no store there is no coherence traffic, and the MESI ping-pong
 *   the experiment is designed to provoke never happens.
 *
 *   Variants 4 and 5 restore the effect by declaring the counters
 *   volatile, which forbids register promotion and forces a genuine
 *   load-modify-store to memory on every increment. Comparing those two
 *   against each other -- identical code, identical volatility, differing
 *   only in whether the counters share a cache line -- isolates the cost
 *   of coherence traffic as the single independent variable. */

typedef struct { int count; char pad[60]; } Padded;            /* 64 bytes */
typedef struct { volatile int count; char pad[60]; } VPadded;  /* 64 bytes */

static int           fs_naive_counts[MAX_THREADS];
static Padded        fs_padded_counts[MAX_THREADS];
static volatile int  fs_vol_adjacent[MAX_THREADS];
static VPadded       fs_vol_padded[MAX_THREADS];

typedef enum {
    FS_NAIVE = 0,      /* int hit_count[]; hit_count[omp_get_thread_num()]++ */
    FS_REDUCTION,      /* #pragma omp ... reduction(+:total_hits)            */
    FS_PADDED,         /* struct Padded { int count; char pad[60]; }         */
    FS_VOL_ADJACENT,   /* volatile int[], adjacent  -- store forced          */
    FS_VOL_PADDED,     /* volatile int, 64-byte padded -- store forced       */
    FS_VARIANT_COUNT
} FSVariant;

static const char *FS_NAMES[] = {
    "Variant 1: naive hits[tid]++ (as specified)",
    "Variant 2: OpenMP reduction",
    "Variant 2b: padded struct (64-byte aligned)",
    "Isolation A: volatile adjacent (false sharing)",
    "Isolation B: volatile padded (cache-line separated)"
};

static uint64_t run_false_sharing(FSVariant v, int threads,
                                  uint32_t *max_out, uint64_t *sum_out) {
    uint32_t max_steps = 0;
    uint64_t sum = 0, total_hits = 0;

    memset(fs_naive_counts,  0, sizeof(fs_naive_counts));
    memset(fs_padded_counts, 0, sizeof(fs_padded_counts));
    memset((void *)fs_vol_adjacent, 0, sizeof(fs_vol_adjacent));
    memset((void *)fs_vol_padded,   0, sizeof(fs_vol_padded));

    switch (v) {
    case FS_NAIVE:
        #pragma omp parallel for num_threads(threads) schedule(static) \
                reduction(max:max_steps) reduction(+:sum)
        for (int64_t i = 1; i <= (int64_t)WORKLOAD_N; i++) {
            uint32_t s = collatz_steps((uint64_t)i);
            if (s > max_steps) max_steps = s;
            sum += s;
            if (s > HIT_THRESHOLD) fs_naive_counts[omp_get_thread_num()]++;
        }
        for (int t = 0; t < MAX_THREADS; t++) total_hits += (uint64_t)fs_naive_counts[t];
        break;

    case FS_REDUCTION:
        #pragma omp parallel for num_threads(threads) schedule(static) \
                reduction(max:max_steps) reduction(+:sum) reduction(+:total_hits)
        for (int64_t i = 1; i <= (int64_t)WORKLOAD_N; i++) {
            uint32_t s = collatz_steps((uint64_t)i);
            if (s > max_steps) max_steps = s;
            sum += s;
            if (s > HIT_THRESHOLD) total_hits++;
        }
        break;

    case FS_PADDED:
        #pragma omp parallel for num_threads(threads) schedule(static) \
                reduction(max:max_steps) reduction(+:sum)
        for (int64_t i = 1; i <= (int64_t)WORKLOAD_N; i++) {
            uint32_t s = collatz_steps((uint64_t)i);
            if (s > max_steps) max_steps = s;
            sum += s;
            if (s > HIT_THRESHOLD) fs_padded_counts[omp_get_thread_num()].count++;
        }
        for (int t = 0; t < MAX_THREADS; t++) total_hits += (uint64_t)fs_padded_counts[t].count;
        break;

    case FS_VOL_ADJACENT:
        #pragma omp parallel num_threads(threads) \
                reduction(max:max_steps) reduction(+:sum)
        {
            int tid = omp_get_thread_num();
            #pragma omp for schedule(static)
            for (int64_t i = 1; i <= (int64_t)WORKLOAD_N; i++) {
                uint32_t s = collatz_steps((uint64_t)i);
                if (s > max_steps) max_steps = s;
                sum += s;
                if (s > HIT_THRESHOLD) fs_vol_adjacent[tid]++;
            }
        }
        for (int t = 0; t < MAX_THREADS; t++) total_hits += (uint64_t)fs_vol_adjacent[t];
        break;

    case FS_VOL_PADDED:
        #pragma omp parallel num_threads(threads) \
                reduction(max:max_steps) reduction(+:sum)
        {
            int tid = omp_get_thread_num();
            #pragma omp for schedule(static)
            for (int64_t i = 1; i <= (int64_t)WORKLOAD_N; i++) {
                uint32_t s = collatz_steps((uint64_t)i);
                if (s > max_steps) max_steps = s;
                sum += s;
                if (s > HIT_THRESHOLD) fs_vol_padded[tid].count++;
            }
        }
        for (int t = 0; t < MAX_THREADS; t++) total_hits += (uint64_t)fs_vol_padded[t].count;
        break;

    default: break;
    }

    *max_out = max_steps;
    *sum_out = sum % MODULUS;
    return total_hits;
}

/* ---- Phase 4A-2: pure coherence micro-benchmark ---------------------
 * The Collatz kernel performs on the order of a hundred arithmetic steps
 * per iteration, so a single counter update per iteration is amortised
 * against a large amount of unrelated work and the coherence cost is
 * heavily diluted. This micro-benchmark strips the arithmetic away and
 * measures nothing but the counter update, which exposes the cost of
 * cache-line sharing at full strength. Both loops are byte-for-byte
 * identical apart from the stride between counters. */
static void pure_counter_bench(int threads, int64_t iters,
                               double *t_adjacent, double *t_padded) {
    memset((void *)fs_vol_adjacent, 0, sizeof(fs_vol_adjacent));
    memset((void *)fs_vol_padded,   0, sizeof(fs_vol_padded));

    double t0 = omp_get_wtime();
    #pragma omp parallel num_threads(threads)
    {
        int tid = omp_get_thread_num();
        for (int64_t i = 0; i < iters / threads; i++) fs_vol_adjacent[tid]++;
    }
    *t_adjacent = omp_get_wtime() - t0;

    t0 = omp_get_wtime();
    #pragma omp parallel num_threads(threads)
    {
        int tid = omp_get_thread_num();
        for (int64_t i = 0; i < iters / threads; i++) fs_vol_padded[tid].count++;
    }
    *t_padded = omp_get_wtime() - t0;
}

/* ============ PHASE 4B: LOOP SCHEDULING ============================== */

/* The loop body is identical in all five variants; only the schedule
   clause changes. It is written out five times rather than hidden behind
   schedule(runtime) so that the exact clause under test is visible in the
   source, and so no runtime scheduling indirection is added to any of the
   measurements. */

#define COLLATZ_SCHED_BODY                                   \
    for (int64_t i = 1; i <= (int64_t)WORKLOAD_N; i++) {     \
        uint32_t s = collatz_steps((uint64_t)i);             \
        if (s > max_steps) max_steps = s;                    \
        sum += s;                                            \
        if (s > HIT_THRESHOLD) hits++;                       \
    }

static Result run_schedule(int variant, int threads) {
    uint32_t max_steps = 0;
    uint64_t sum = 0, hits = 0;

    switch (variant) {
    case 0:  /* schedule(static) -- default chunk = N / k */
        #pragma omp parallel for num_threads(threads) schedule(static) \
                reduction(max:max_steps) reduction(+:sum) reduction(+:hits)
        COLLATZ_SCHED_BODY
        break;

    case 1:  /* schedule(static, 1000) -- round-robin 1000-iteration chunks */
        #pragma omp parallel for num_threads(threads) schedule(static, 1000) \
                reduction(max:max_steps) reduction(+:sum) reduction(+:hits)
        COLLATZ_SCHED_BODY
        break;

    case 2:  /* schedule(dynamic, 100) -- fine-grained work queue */
        #pragma omp parallel for num_threads(threads) schedule(dynamic, 100) \
                reduction(max:max_steps) reduction(+:sum) reduction(+:hits)
        COLLATZ_SCHED_BODY
        break;

    case 3:  /* schedule(dynamic, 10000) -- coarse-grained work queue */
        #pragma omp parallel for num_threads(threads) schedule(dynamic, 10000) \
                reduction(max:max_steps) reduction(+:sum) reduction(+:hits)
        COLLATZ_SCHED_BODY
        break;

    case 4:  /* schedule(guided) -- exponentially decaying chunk size */
        #pragma omp parallel for num_threads(threads) schedule(guided) \
                reduction(max:max_steps) reduction(+:sum) reduction(+:hits)
        COLLATZ_SCHED_BODY
        break;
    }

    Result r = { max_steps, sum % MODULUS, hits };
    return r;
}

static const char *SCHEDULE_NAMES[] = {
    "schedule(static)", "schedule(static, 1000)", "schedule(dynamic, 100)",
    "schedule(dynamic, 10000)", "schedule(guided)"
};
static const char *SCHEDULE_CHUNKS[] = {
    "Default (N / k)", "1000", "100", "10000", "Exponential decay"
};

/* ============================ TIMING HARNESS ========================== */

typedef struct {
    double run[TOTAL_RUNS];   /* run[0] is the discarded cold run         */
    double avg;               /* mean of run[1] and run[2]                */
    Result result;
} Timing;

static double mean_of_timed_runs(const double *run) {
    double s = 0.0;
    for (int r = 1; r < TOTAL_RUNS; r++) s += run[r];
    return s / (double)(TOTAL_RUNS - 1);
}

static Timing time_sequential(void) {
    Timing t;
    for (int r = 0; r < TOTAL_RUNS; r++) {
        double t0 = omp_get_wtime();
        t.result = run_sequential();
        t.run[r] = omp_get_wtime() - t0;
    }
    t.avg = mean_of_timed_runs(t.run);
    return t;
}

static Timing time_parallel(int threads) {
    Timing t;
    for (int r = 0; r < TOTAL_RUNS; r++) {
        double t0 = omp_get_wtime();
        t.result = run_parallel(threads);
        t.run[r] = omp_get_wtime() - t0;
    }
    t.avg = mean_of_timed_runs(t.run);
    return t;
}

static Timing time_schedule(int variant, int threads) {
    Timing t;
    for (int r = 0; r < TOTAL_RUNS; r++) {
        double t0 = omp_get_wtime();
        t.result = run_schedule(variant, threads);
        t.run[r] = omp_get_wtime() - t0;
    }
    t.avg = mean_of_timed_runs(t.run);
    return t;
}

/* ============================ MAIN ==================================== */

int main(int argc, char **argv) {
    const int max_threads = omp_get_max_threads();
    int exp_threads = (argc > 1) ? atoi(argv[1]) : max_threads;
    if (exp_threads < 1) exp_threads = max_threads;
    if (exp_threads > MAX_THREADS) exp_threads = MAX_THREADS;

    printf("=======================================================================\n");
    printf(" PRACTICUM: THE AMDAHL REALITY GAP - Collatz Stopping Time / OpenMP\n");
    printf("=======================================================================\n");
    printf(" Student ID           : %" PRIu64 "\n", (uint64_t)STUDENT_ID);
    printf(" Last 4 digits        : %04" PRIu64 "\n", (uint64_t)LAST4);
    printf(" Workload N           : %" PRIu64 "  (10,000,000 + %" PRIu64 " * 1,000)\n",
           (uint64_t)WORKLOAD_N, (uint64_t)LAST4);
    printf(" omp_get_max_threads(): %d\n", max_threads);
    printf(" Phase 4 thread count : %d\n", exp_threads);
    printf(" Timing protocol      : %d runs per configuration, run 1 discarded,\n", TOTAL_RUNS);
    printf("                        reported time = mean(run 2, run 3)\n");
    printf(" Clock                : omp_get_wtime()\n");
    printf("=======================================================================\n\n");

    FILE *csv = fopen("results.csv", "w");
    if (!csv) { fprintf(stderr, "ERROR: cannot open results.csv for writing\n"); return 1; }
    fprintf(csv, "table,configuration,threads,chunk,run1_cold_s,run2_s,run3_s,"
                 "avg_time_s,s_emp,s_theo,delta,throughput_iter_per_s,"
                 "penalty_ratio,max_steps,checksum,hits\n");

    /* ---------------- PHASE 2: sequential baseline -------------------- */
    printf("PHASE 2 - SEQUENTIAL BASELINE (no OpenMP pragma)\n");
    printf("-----------------------------------------------------------------------\n");
    fflush(stdout);

    Timing seq = time_sequential();
    const double T_seq = seq.avg;

    printf("  run 1 (cold, discarded) : %10.4f s\n", seq.run[0]);
    printf("  run 2                   : %10.4f s\n", seq.run[1]);
    printf("  run 3                   : %10.4f s\n", seq.run[2]);
    printf("  T_seq = (run2+run3)/2   : %10.4f s\n", T_seq);
    printf("  max stopping time       : %" PRIu32 "\n", seq.result.max_steps);
    printf("  VERIFICATION CHECKSUM   : %" PRIu64 "\n", seq.result.checksum);
    printf("  values with steps > %d  : %" PRIu64 "\n\n", HIT_THRESHOLD, seq.result.hits);
    fflush(stdout);

    fprintf(csv, "1_scaling,sequential_baseline,0,,%.6f,%.6f,%.6f,%.6f,,,,%.2f,,%" PRIu32
                 ",%" PRIu64 ",%" PRIu64 "\n",
            seq.run[0], seq.run[1], seq.run[2], T_seq,
            (double)WORKLOAD_N / T_seq, seq.result.max_steps,
            seq.result.checksum, seq.result.hits);

    /* ---------------- PHASE 3: scaling sweep -------------------------- */
    printf("PHASE 3 - OPENMP SCALING SWEEP\n");
    printf("-----------------------------------------------------------------------\n");
    fflush(stdout);

    Timing par[N_THREAD_COUNTS];
    double s_emp[N_THREAD_COUNTS];
    int checksum_ok = 1;

    for (int idx = 0; idx < N_THREAD_COUNTS; idx++) {
        int k = THREAD_COUNTS[idx];
        par[idx] = time_parallel(k);
        s_emp[idx] = T_seq / par[idx].avg;
        if (!results_equal(par[idx].result, seq.result)) checksum_ok = 0;
        printf("  k = %2d  runs: %8.4f (cold) %8.4f %8.4f | T_k = %8.4f s | S_emp = %6.3fx\n",
               k, par[idx].run[0], par[idx].run[1], par[idx].run[2],
               par[idx].avg, s_emp[idx]);
        fflush(stdout);
    }

    /* Derive the parallel fraction p from the two-thread speedup:
           S(2)   = 1 / [ (1 - p) + p/2 ]
           1/S(2) = 1 - p + 0.5p = 1 - 0.5p
           0.5p   = 1 - (1 / S(2))
           p      = 2 * [ 1 - (1 / S_emp(2)) ]                              */
    double S2 = s_emp[1];
    double p  = 2.0 * (1.0 - (1.0 / S2));
    if (p < 0.0) p = 0.0;
    if (p > 1.0) p = 1.0;

    printf("\n  DERIVATION OF THE PARALLEL FRACTION p (from k = 2)\n");
    printf("    S_emp(2) = T_seq / T_2 = %.4f / %.4f = %.6f\n", T_seq, par[1].avg, S2);
    printf("    p = 2 * [1 - (1 / S_emp(2))] = 2 * [1 - %.6f] = %.6f\n", 1.0 / S2, p);
    printf("    (1 - p) = %.6f   ->  %.2f%% parallel, %.2f%% serial\n",
           1.0 - p, 100.0 * p, 100.0 * (1.0 - p));
    if (1.0 - p > 1e-9)
        printf("    S_max = 1/(1-p) = %.4fx  (asymptotic ceiling)\n", 1.0 / (1.0 - p));
    printf("\n");

    printf("  %-8s | %10s | %10s | %10s | %10s\n",
           "Threads", "T_k (s)", "S_emp(k)", "S_theo(k)", "Delta(k)");
    printf("  ---------------------------------------------------------------\n");
    for (int idx = 0; idx < N_THREAD_COUNTS; idx++) {
        int k = THREAD_COUNTS[idx];
        double s_theo = 1.0 / ((1.0 - p) + p / (double)k);
        double delta  = s_theo - s_emp[idx];
        printf("  k = %-4d | %10.4f | %9.3fx | %9.3fx | %+10.3f\n",
               k, par[idx].avg, s_emp[idx], s_theo, delta);
        fprintf(csv, "1_scaling,parallel_k%d,%d,,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,"
                     "%.2f,,%" PRIu32 ",%" PRIu64 ",%" PRIu64 "\n",
                k, k, par[idx].run[0], par[idx].run[1], par[idx].run[2],
                par[idx].avg, s_emp[idx], s_theo, delta,
                (double)WORKLOAD_N / par[idx].avg,
                par[idx].result.max_steps, par[idx].result.checksum,
                par[idx].result.hits);
    }
    printf("\n  Derived p = %.6f   Checksum consistent across all k: %s\n\n",
           p, checksum_ok ? "YES" : "NO -- INVESTIGATE");
    fflush(stdout);

    /* ---------------- PHASE 4A: false sharing ------------------------- */
    printf("PHASE 4A - FALSE SHARING PENALTY (%d threads)\n", exp_threads);
    printf("-----------------------------------------------------------------------\n");
    fflush(stdout);

    double fs_time[FS_VARIANT_COUNT];
    double fs_runs[FS_VARIANT_COUNT][TOTAL_RUNS];
    uint64_t fs_hits[FS_VARIANT_COUNT];
    uint32_t fs_max[FS_VARIANT_COUNT];
    uint64_t fs_sum[FS_VARIANT_COUNT];

    for (int v = 0; v < FS_VARIANT_COUNT; v++) {
        for (int r = 0; r < TOTAL_RUNS; r++) {
            double t0 = omp_get_wtime();
            fs_hits[v] = run_false_sharing((FSVariant)v, exp_threads,
                                           &fs_max[v], &fs_sum[v]);
            fs_runs[v][r] = omp_get_wtime() - t0;
        }
        fs_time[v] = mean_of_timed_runs(fs_runs[v]);
    }

    /* The worksheet's Table 2 compares Variant 1 against Variant 2. */
    double penalty = fs_time[FS_NAIVE] / fs_time[FS_REDUCTION];
    /* The isolation pair compares identical volatile code, differing only
       in whether the counters occupy the same cache line.              */
    double iso_penalty = fs_time[FS_VOL_ADJACENT] / fs_time[FS_VOL_PADDED];

    printf("  %-48s | %10s | %14s\n", "Counter discipline", "Time (s)", "iter/sec");
    printf("  -------------------------------------------------------------------------------\n");
    for (int v = 0; v < FS_VARIANT_COUNT; v++) {
        printf("  %-48s | %10.4f | %14.0f\n",
               FS_NAMES[v], fs_time[v], (double)WORKLOAD_N / fs_time[v]);
    }
    printf("  -------------------------------------------------------------------------------\n");
    printf("  PRESCRIBED PENALTY RATIO  (V1 / V2)                 : %.3fx\n", penalty);
    printf("  ISOLATED PENALTY RATIO    (volatile adj / vol pad)  : %.3fx\n", iso_penalty);
    printf("  hits identical across all five variants             : %s\n",
           (fs_hits[0] == fs_hits[1] && fs_hits[1] == fs_hits[2] &&
            fs_hits[2] == fs_hits[3] && fs_hits[3] == fs_hits[4]) ? "YES" : "NO");
    if (penalty < 1.15) {
        printf("\n  NOTE: the prescribed Variant 1 shows no meaningful penalty. Under -O2\n");
        printf("  GCC register-promotes hit_count[tid] and stores it once after the loop,\n");
        printf("  so no coherence traffic is generated. The isolation pair above forces\n");
        printf("  the store with `volatile` and does exhibit the effect. See analysis Q1.\n");
    }
    printf("\n");
    fflush(stdout);

    static const char *FS_CSV_TAGS[] = {
        "variant1_naive_false_sharing", "variant2_openmp_reduction",
        "variant2b_padded_struct", "isolation_volatile_adjacent",
        "isolation_volatile_padded"
    };
    for (int v = 0; v < FS_VARIANT_COUNT; v++) {
        double rel = fs_time[v] / fs_time[FS_REDUCTION];
        fprintf(csv, "2_false_sharing,%s,%d,,%.6f,%.6f,%.6f,%.6f,,,,%.2f,%.4f,"
                     "%" PRIu32 ",%" PRIu64 ",%" PRIu64 "\n",
                FS_CSV_TAGS[v], exp_threads,
                fs_runs[v][0], fs_runs[v][1], fs_runs[v][2], fs_time[v],
                (double)WORKLOAD_N / fs_time[v], rel,
                fs_max[v], fs_sum[v], fs_hits[v]);
    }

    /* ---- Phase 4A-2: pure coherence micro-benchmark ------------------ */
    printf("PHASE 4A-2 - PURE COHERENCE MICRO-BENCHMARK (%d threads)\n", exp_threads);
    printf("-----------------------------------------------------------------------\n");
    printf("  Collatz arithmetic removed; the loop body is the counter update alone.\n");
    fflush(stdout);

    const int64_t MICRO_ITERS = 200000000LL;
    double mt_adj[TOTAL_RUNS], mt_pad[TOTAL_RUNS];
    for (int r = 0; r < TOTAL_RUNS; r++)
        pure_counter_bench(exp_threads, MICRO_ITERS, &mt_adj[r], &mt_pad[r]);

    double T_adj = mean_of_timed_runs(mt_adj);
    double T_pad = mean_of_timed_runs(mt_pad);
    double micro_penalty = T_adj / T_pad;

    printf("  volatile adjacent  (counters 4 bytes apart, same line) : %8.4f s\n", T_adj);
    printf("  volatile padded    (counters 64 bytes apart)           : %8.4f s\n", T_pad);
    printf("  FALSE SHARING PENALTY, ISOLATED                        : %.3fx\n\n",
           micro_penalty);
    fflush(stdout);

    fprintf(csv, "2b_coherence_micro,volatile_adjacent_same_line,%d,,%.6f,%.6f,%.6f,%.6f,"
                 ",,,%.2f,%.4f,,,\n",
            exp_threads, mt_adj[0], mt_adj[1], mt_adj[2], T_adj,
            (double)MICRO_ITERS / T_adj, micro_penalty);
    fprintf(csv, "2b_coherence_micro,volatile_padded_64B,%d,,%.6f,%.6f,%.6f,%.6f,"
                 ",,,%.2f,%.4f,,,\n",
            exp_threads, mt_pad[0], mt_pad[1], mt_pad[2], T_pad,
            (double)MICRO_ITERS / T_pad, 1.0);

    /* ---------------- PHASE 4B: loop scheduling ----------------------- */
    printf("PHASE 4B - LOOP SCHEDULING COMPARISON (%d threads)\n", exp_threads);
    printf("-----------------------------------------------------------------------\n");
    printf("  %-26s | %-18s | %10s | %9s\n",
           "Clause", "Chunk size", "Time (s)", "vs static");
    printf("  ---------------------------------------------------------------------\n");
    fflush(stdout);

    double sched_time[5];
    for (int v = 0; v < 5; v++) {
        Timing t = time_schedule(v, exp_threads);
        sched_time[v] = t.avg;
        double rel = sched_time[v] / sched_time[0];
        printf("  %-26s | %-18s | %10.4f | %8.3fx\n",
               SCHEDULE_NAMES[v], SCHEDULE_CHUNKS[v], t.avg, rel);
        fflush(stdout);
        fprintf(csv, "3_scheduling,%s,%d,%s,%.6f,%.6f,%.6f,%.6f,,,,%.2f,%.4f,"
                     "%" PRIu32 ",%" PRIu64 ",%" PRIu64 "\n",
                SCHEDULE_NAMES[v], exp_threads, SCHEDULE_CHUNKS[v],
                t.run[0], t.run[1], t.run[2], t.avg,
                (double)WORKLOAD_N / t.avg, rel,
                t.result.max_steps, t.result.checksum, t.result.hits);
    }

    int best = 0;
    for (int v = 1; v < 5; v++) if (sched_time[v] < sched_time[best]) best = v;
    printf("\n  Fastest clause: %s (%.4f s)\n\n", SCHEDULE_NAMES[best], sched_time[best]);

    /* ---------------- summary ----------------------------------------- */
    fclose(csv);

    printf("=======================================================================\n");
    printf(" SUMMARY\n");
    printf("=======================================================================\n");
    printf("  Workload N              : %" PRIu64 "\n", (uint64_t)WORKLOAD_N);
    printf("  Max stopping time       : %" PRIu32 "\n", seq.result.max_steps);
    printf("  VERIFICATION CHECKSUM   : %" PRIu64 "\n", seq.result.checksum);
    printf("  Values with steps > %d  : %" PRIu64 "\n", HIT_THRESHOLD, seq.result.hits);
    printf("  T_seq                   : %.4f s\n", T_seq);
    printf("  Derived parallel p      : %.6f\n", p);
    if (1.0 - p > 1e-9)
        printf("  Amdahl ceiling S_max    : %.4fx\n", 1.0 / (1.0 - p));
    printf("  Checksum invariant      : %s\n", checksum_ok ? "YES" : "NO");
    printf("  results.csv written     : yes\n");
    printf("=======================================================================\n");
    return 0;
}
