/**
 * PART 2: THE SYNCHRONIZATION TRAP
 * ================================
 *
 * Fixes the Part 1 data race two ways and measures what the fix costs:
 *
 *   (a) synchronized  - a monitor lock taken around every single increment
 *   (b) AtomicLong    - lock-free CAS via incrementAndGet()
 *
 * Both are compared against a plain SINGLE-THREADED loop with no
 * synchronisation at all, which is the reference the question asks about.
 *
 * Expected finding: the answer becomes correct (pi ~= 3.1415) but the
 * multi-threaded synchronised version is SLOWER than one plain thread,
 * because every increment must take exclusive ownership of the same cache
 * line and the cores spend their cycles waiting on the coherence protocol
 * rather than computing.
 *
 * Run: java Part2SynchronizationTrap
 */

import java.util.Locale;
import java.util.concurrent.ThreadLocalRandom;
import java.util.concurrent.atomic.AtomicLong;

public class Part2SynchronizationTrap {

    static final long TOTAL_POINTS = 50_000_000L;
    static final int  NUM_THREADS  = 4;

    // ---- (a) synchronized ----
    static long syncHits = 0;

    static synchronized void incrementSync() {
        syncHits++;                      // monitor held for the whole RMW
    }

    // ---- (b) AtomicLong ----
    static final AtomicLong atomicHits = new AtomicLong(0);

    // ---------------------------------------------------------------- runners

    /** Baseline: one thread, no sharing, no synchronisation. */
    static Result singleThreaded() {
        long t0 = System.nanoTime();
        long hits = 0;
        ThreadLocalRandom rng = ThreadLocalRandom.current();
        for (long i = 0; i < TOTAL_POINTS; i++) {
            double x = rng.nextDouble();
            double y = rng.nextDouble();
            if (x * x + y * y <= 1.0) hits++;
        }
        long ms = (System.nanoTime() - t0) / 1_000_000;
        return new Result("Single-threaded plain loop", hits, ms);
    }

    static Result synchronizedVersion() throws InterruptedException {
        syncHits = 0;
        long perThread = TOTAL_POINTS / NUM_THREADS;
        Thread[] threads = new Thread[NUM_THREADS];
        for (int i = 0; i < NUM_THREADS; i++) {
            threads[i] = new Thread(() -> {
                ThreadLocalRandom rng = ThreadLocalRandom.current();
                for (long j = 0; j < perThread; j++) {
                    double x = rng.nextDouble();
                    double y = rng.nextDouble();
                    if (x * x + y * y <= 1.0) incrementSync();
                }
            });
        }
        long t0 = System.nanoTime();
        for (Thread t : threads) t.start();
        for (Thread t : threads) t.join();
        long ms = (System.nanoTime() - t0) / 1_000_000;
        return new Result("synchronized (" + NUM_THREADS + " threads)", syncHits, ms);
    }

    static Result atomicVersion() throws InterruptedException {
        atomicHits.set(0);
        long perThread = TOTAL_POINTS / NUM_THREADS;
        Thread[] threads = new Thread[NUM_THREADS];
        for (int i = 0; i < NUM_THREADS; i++) {
            threads[i] = new Thread(() -> {
                ThreadLocalRandom rng = ThreadLocalRandom.current();
                for (long j = 0; j < perThread; j++) {
                    double x = rng.nextDouble();
                    double y = rng.nextDouble();
                    if (x * x + y * y <= 1.0) atomicHits.incrementAndGet();
                }
            });
        }
        long t0 = System.nanoTime();
        for (Thread t : threads) t.start();
        for (Thread t : threads) t.join();
        long ms = (System.nanoTime() - t0) / 1_000_000;
        return new Result("AtomicLong.incrementAndGet (" + NUM_THREADS + " threads)",
                          atomicHits.get(), ms);
    }

    record Result(String label, long hits, long millis) {
        double pi() { return 4.0 * hits / TOTAL_POINTS; }
    }

    // ------------------------------------------------------------------ main

    public static void main(String[] args) throws InterruptedException {
        // Neutral locale: keeps "." as the decimal separator and "," as the
        // thousands separator regardless of the host's regional settings,
        // so the transcript is identical on every machine.
        Locale.setDefault(Locale.ROOT);

        System.out.println("=".repeat(78));
        System.out.println("PART 2 - THE SYNCHRONIZATION TRAP");
        System.out.println("=".repeat(78));
        System.out.printf("Points         : %,d%n", TOTAL_POINTS);
        System.out.printf("Threads        : %d%n", NUM_THREADS);
        System.out.printf("Available cores: %d%n", Runtime.getRuntime().availableProcessors());
        System.out.printf("JVM            : %s %s%n%n",
                System.getProperty("java.vm.name"), System.getProperty("java.version"));

        // Warm up the JIT so the first measurement is not penalised by
        // interpreted-mode execution. This matters: without it the baseline
        // is inflated and every comparison against it is wrong.
        System.out.println("Warming up JIT (results discarded)...");
        warmup();
        System.out.println("Warm-up complete.\n");

        Result baseline = singleThreaded();
        Result sync     = synchronizedVersion();
        Result atomic   = atomicVersion();

        System.out.printf("%-42s | %12s | %10s | %12s%n",
                "Implementation", "pi estimate", "Time (ms)", "vs baseline");
        System.out.println("-".repeat(78));
        report(baseline, baseline);
        report(sync, baseline);
        report(atomic, baseline);
        System.out.println("-".repeat(78));

        System.out.printf("%nTrue pi = %.6f%n%n", Math.PI);

        System.out.println("ANALYSIS");
        System.out.println("-".repeat(78));
        System.out.printf("Correctness  : synchronized -> %.6f, atomic -> %.6f (both correct)%n",
                sync.pi(), atomic.pi());
        System.out.printf("Sync penalty : %.2fx SLOWER than a single plain thread%n",
                (double) sync.millis() / baseline.millis());
        System.out.printf("Atomic penalty: %.2fx vs the same baseline%n",
                (double) atomic.millis() / baseline.millis());
        System.out.printf("Atomic vs synchronized: %.2fx faster%n",
                (double) sync.millis() / atomic.millis());
        System.out.println();
        System.out.println("4 cores were used to do the work of 1, and it took LONGER.");
        System.out.println("The arithmetic is trivial; the cost is entirely in making every");
        System.out.println("thread agree on one memory location, one increment at a time.");
    }

    static void report(Result r, Result baseline) {
        String rel = (r == baseline)
                ? "1.00x [base]"
                : String.format("%.2fx %s", (double) r.millis() / baseline.millis(),
                        r.millis() > baseline.millis() ? "SLOWER" : "faster");
        System.out.printf("%-42s | %12.6f | %10d | %12s%n", r.label(), r.pi(), r.millis(), rel);
    }

    /** Short run of each variant to trigger JIT compilation before timing. */
    static void warmup() throws InterruptedException {
        long saveTotal = 2_000_000L;
        ThreadLocalRandom rng = ThreadLocalRandom.current();
        long h = 0;
        for (long i = 0; i < saveTotal; i++) {
            double x = rng.nextDouble(), y = rng.nextDouble();
            if (x * x + y * y <= 1.0) h++;
        }
        if (h < 0) System.out.println("unreachable");   // stop dead-code elimination

        syncHits = 0;
        Thread a = new Thread(() -> { for (int i = 0; i < 500_000; i++) incrementSync(); });
        a.start(); a.join();

        atomicHits.set(0);
        Thread b = new Thread(() -> { for (int i = 0; i < 500_000; i++) atomicHits.incrementAndGet(); });
        b.start(); b.join();
    }
}
