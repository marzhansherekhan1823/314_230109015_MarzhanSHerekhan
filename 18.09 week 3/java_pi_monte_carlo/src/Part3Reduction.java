/**
 * PART 3: OPENMP-STYLE REDUCTION
 * ==============================
 *
 * Eliminates shared-state locking entirely. Each thread accumulates into a
 * PRIVATE, LOCAL counter; the partial sums are combined exactly once, after
 * the threads join. This is conceptually identical to:
 *
 *     #pragma omp parallel for reduction(+:totalHits)
 *
 * Benchmarks total execution time for T in {1, 2, 4, 8, 16, 32} threads over
 * 100,000,000 iterations, and emits the grid the worksheet asks for plus a CSV
 * for plotting.
 *
 * Run: java Part3Reduction
 */

import java.util.Locale;
import java.io.FileWriter;
import java.io.IOException;
import java.util.concurrent.ThreadLocalRandom;

public class Part3Reduction {

    static final long TOTAL_POINTS = 100_000_000L;
    static final int[] THREAD_COUNTS = { 1, 2, 4, 8, 16, 32 };

    /**
     * Worker holding its own private hit counter.
     *
     * The counter is an instance field of a per-thread object, so no two
     * threads ever touch the same field. It is written by exactly one thread
     * and read by the main thread only after join(), which establishes a
     * happens-before edge - so the read is safe without any synchronisation.
     */
    static class Worker extends Thread {
        private final long pointsToToss;
        private long localHits = 0;          // PRIVATE - no sharing, no lock

        Worker(long pointsToToss) {
            this.pointsToToss = pointsToToss;
        }

        @Override
        public void run() {
            ThreadLocalRandom rng = ThreadLocalRandom.current();
            long hits = 0;                   // accumulate in a stack local
            for (long i = 0; i < pointsToToss; i++) {
                double x = rng.nextDouble();
                double y = rng.nextDouble();
                if (x * x + y * y <= 1.0) hits++;
            }
            this.localHits = hits;           // single write, at the very end
        }

        long getLocalHits() { return localHits; }
    }

    static long[] runWithThreads(int threadCount) throws InterruptedException {
        long base      = TOTAL_POINTS / threadCount;
        long remainder = TOTAL_POINTS - base * threadCount;   // exactness guard

        Worker[] workers = new Worker[threadCount];
        for (int i = 0; i < threadCount; i++) {
            long quota = base + (i == 0 ? remainder : 0);
            workers[i] = new Worker(quota);
        }

        long t0 = System.nanoTime();
        for (Worker w : workers) w.start();
        for (Worker w : workers) w.join();

        // REDUCTION: combine the partial sums once, single-threaded.
        long totalHits = 0;
        for (Worker w : workers) totalHits += w.getLocalHits();

        long millis = (System.nanoTime() - t0) / 1_000_000;
        return new long[] { totalHits, millis };
    }

    public static void main(String[] args) throws InterruptedException, IOException {
        // Neutral locale: keeps "." as the decimal separator and "," as the
        // thousands separator regardless of the host's regional settings,
        // so the transcript is identical on every machine.
        Locale.setDefault(Locale.ROOT);

        System.out.println("=".repeat(86));
        System.out.println("PART 3 - OPENMP-STYLE REDUCTION (private counters, combine once)");
        System.out.println("=".repeat(86));
        System.out.printf("Total points   : %,d%n", TOTAL_POINTS);
        System.out.printf("Available cores: %d%n", Runtime.getRuntime().availableProcessors());
        System.out.printf("JVM            : %s %s%n",
                System.getProperty("java.vm.name"), System.getProperty("java.version"));
        System.out.printf("OS             : %s %s%n%n",
                System.getProperty("os.name"), System.getProperty("os.arch"));

        System.out.println("Warming up JIT (results discarded)...");
        runWithThreads(4);
        runWithThreads(1);
        System.out.println("Warm-up complete.\n");

        System.out.printf("%-10s | %13s | %14s | %14s | %12s%n",
                "Threads T", "Runtime (ms)", "pi estimate", "Speedup T1/TN", "Efficiency");
        System.out.println("-".repeat(86));

        long baselineMs = -1;
        StringBuilder csv = new StringBuilder("threads,runtime_ms,pi,speedup,efficiency_pct\n");

        for (int t : THREAD_COUNTS) {
            long[] r = runWithThreads(t);
            long hits = r[0], ms = r[1];
            double pi = 4.0 * hits / TOTAL_POINTS;

            if (baselineMs < 0) baselineMs = ms;
            double speedup = (double) baselineMs / ms;
            double efficiency = 100.0 * speedup / t;

            System.out.printf("%-10d | %13d | %14.6f | %13.2fx | %11.1f%%%n",
                    t, ms, pi, speedup, efficiency);
            csv.append(String.format("%d,%d,%.6f,%.4f,%.2f%n", t, ms, pi, speedup, efficiency));
        }

        System.out.println("-".repeat(86));
        System.out.printf("True pi = %.6f%n", Math.PI);

        try (FileWriter fw = new FileWriter("part3_results.csv")) {
            fw.write(csv.toString());
        }
        System.out.println("\nWrote part3_results.csv");

        System.out.println("\nNOTE: every row produces a CORRECT value of pi. Correctness here is");
        System.out.println("structural - no two threads share a counter, so there is nothing to");
        System.out.println("race on and nothing to lock.");
    }
}
