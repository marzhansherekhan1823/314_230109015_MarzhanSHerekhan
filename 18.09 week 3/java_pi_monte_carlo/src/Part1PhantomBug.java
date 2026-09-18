/**
 * PART 1: THE PHANTOM BUG
 * =======================
 *
 * Tosses 50,000,000 random (x, y) points into the unit square and approximates
 *
 *     pi  ~=  4 * hits / total
 *
 * where a "hit" is a point falling inside the quarter circle x^2 + y^2 <= 1.
 *
 * The work is split across 4 native Java threads, and every thread updates the
 * SAME shared variable:
 *
 *     static long totalHits = 0;      via  totalHits++;
 *
 * totalHits++ is NOT atomic. It compiles to a read-modify-write sequence
 * (getstatic -> ladd -> putstatic), and Java threads are real OS threads with
 * no global interpreter lock, so two threads genuinely execute that sequence
 * simultaneously on different physical cores. Updates are therefore lost, the
 * hit count is undercounted, and the computed value of pi collapses.
 *
 * Run: java Part1PhantomBug
 */

import java.util.Locale;
import java.util.concurrent.ThreadLocalRandom;

public class Part1PhantomBug {

    static final long TOTAL_POINTS = 50_000_000L;
    static final int  NUM_THREADS  = 4;
    static final int  RUNS         = 5;

    // THE SHARED, UNPROTECTED STATE - this is the bug.
    static long totalHits = 0;

    static class Worker extends Thread {
        private final long pointsToToss;

        Worker(long pointsToToss) {
            this.pointsToToss = pointsToToss;
        }

        @Override
        public void run() {
            ThreadLocalRandom rng = ThreadLocalRandom.current();
            for (long i = 0; i < pointsToToss; i++) {
                double x = rng.nextDouble();
                double y = rng.nextDouble();
                if (x * x + y * y <= 1.0) {
                    totalHits++;          // <-- DATA RACE: read-modify-write, unsynchronised
                }
            }
        }
    }

    static double singleRun() throws InterruptedException {
        totalHits = 0;                                    // reset shared state
        long perThread = TOTAL_POINTS / NUM_THREADS;

        Thread[] threads = new Thread[NUM_THREADS];
        for (int i = 0; i < NUM_THREADS; i++) {
            threads[i] = new Worker(perThread);
        }
        for (Thread t : threads) t.start();
        for (Thread t : threads) t.join();

        return 4.0 * totalHits / TOTAL_POINTS;
    }

    public static void main(String[] args) throws InterruptedException {
        // Neutral locale: keeps "." as the decimal separator and "," as the
        // thousands separator regardless of the host's regional settings,
        // so the transcript is identical on every machine.
        Locale.setDefault(Locale.ROOT);

        System.out.println("=".repeat(72));
        System.out.println("PART 1 - THE PHANTOM BUG (unsynchronised shared counter)");
        System.out.println("=".repeat(72));
        System.out.printf("Points per run : %,d%n", TOTAL_POINTS);
        System.out.printf("Threads        : %d (native java.lang.Thread)%n", NUM_THREADS);
        System.out.printf("Available cores: %d%n", Runtime.getRuntime().availableProcessors());
        System.out.printf("JVM            : %s %s%n%n",
                System.getProperty("java.vm.name"), System.getProperty("java.version"));

        // The statistically expected hit count if nothing were lost:
        // area of quarter circle / area of square = pi/4
        long expectedHits = Math.round(TOTAL_POINTS * Math.PI / 4.0);
        System.out.printf("Expected hits if no updates were lost: ~%,d%n%n", expectedHits);

        System.out.printf("%-6s | %16s | %12s | %14s | %10s%n",
                "Run", "totalHits", "pi estimate", "lost updates", "error");
        System.out.println("-".repeat(72));

        double sum = 0;
        double[] results = new double[RUNS];

        for (int run = 1; run <= RUNS; run++) {
            long t0 = System.nanoTime();
            double pi = singleRun();
            long elapsedMs = (System.nanoTime() - t0) / 1_000_000;

            long lost = expectedHits - totalHits;
            double error = Math.abs(pi - Math.PI) / Math.PI * 100.0;

            results[run - 1] = pi;
            sum += pi;

            System.out.printf("%-6d | %,16d | %12.6f | %,14d | %9.2f%%   (%d ms)%n",
                    run, totalHits, pi, lost, error, elapsedMs);
        }

        double mean = sum / RUNS;
        double min = results[0], max = results[0];
        for (double r : results) { min = Math.min(min, r); max = Math.max(max, r); }

        System.out.println("-".repeat(72));
        System.out.printf("Mean pi over %d runs : %.6f%n", RUNS, mean);
        System.out.printf("Range               : %.6f to %.6f (spread %.6f)%n", min, max, max - min);
        System.out.printf("True pi             : %.6f%n", Math.PI);
        System.out.printf("Mean error          : %.2f%%%n%n", Math.abs(mean - Math.PI) / Math.PI * 100.0);

        System.out.println("DIAGNOSIS");
        System.out.println("-".repeat(72));
        if (Math.abs(mean - Math.PI) / Math.PI > 0.01) {
            System.out.println("The estimate is badly wrong AND non-deterministic across runs.");
            System.out.println("Every run tosses the same number of points and the mathematics is");
            System.out.println("correct, so the defect is not in the algorithm. `totalHits++' is a");
            System.out.println("read-modify-write executed concurrently by 4 real OS threads with no");
            System.out.println("synchronisation, so increments are overwritten and permanently lost.");
        } else {
            System.out.println("No significant corruption observed on this run - re-run, or see the");
            System.out.println("forensics note in the README. Lost-update rate depends on how often");
            System.out.println("threads collide inside the read-modify-write window.");
        }
    }
}
