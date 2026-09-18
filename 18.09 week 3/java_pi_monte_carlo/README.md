# Monte Carlo π — Concurrency, Contention and Reduction

**Student:** Marzhan Sherekhan · **ID:** 230109015 · **Date:** 18 September 2026

Estimating π by Monte Carlo sampling, used as a vehicle for three lessons in
concurrent programming: how a data race destroys a result, why the obvious fix
can be slower than not parallelising at all, and how a reduction recovers both
correctness and speed.

π is approximated by tossing random points into the unit square and counting
those that land inside the quarter circle:

```
pi ~= 4 * hits / total          where a hit satisfies  x^2 + y^2 <= 1
```

---

## Test machine

| | |
|---|---|
| CPU | 12th Gen Intel Core i7-12700H (Alder Lake-H, hybrid) |
| Topology | **14 physical cores = 6 P-cores + 8 E-cores · 20 logical threads** |
| Cache | L1d 48 KB/P-core, 32 KB/E-core · L2 11.5 MB · L3 24 MB shared |
| Memory | 16 GB LPDDR5-6400, 128-bit bus |
| OS | Windows 11 (build 10.0.26200), AMD64 |
| JDK | Java HotSpot(TM) 64-Bit Server VM 17.0.10 |

The hybrid P-core/E-core split matters for every result below. This is **not**
a homogeneous 14-core machine: the 6 Golden Cove P-cores support 2-way
Hyper-Threading (12 logical threads) and reach a much higher clock than the
8 Gracemont E-cores, which have no SMT at all (8 logical threads).
6 + 8 = 14 physical, 12 + 8 = 20 logical.

---

## How to run

```powershell
.\run_all.ps1
```

If PowerShell gives trouble, the plain `cmd.exe` fallback does the same job:

```
run_all.bat
```

or on Linux/macOS:

```bash
bash run_all.sh
```

Each writes a full transcript to `results/benchmark_output.txt` and the Part 3
scaling data to `results/part3_results.csv`.

To run the parts individually:

```powershell
javac -d out src\Part1PhantomBug.java src\Part2SynchronizationTrap.java src\Part3Reduction.java
java -cp out Part1PhantomBug
java -cp out Part2SynchronizationTrap
java -cp out Part3Reduction
```

---

## Part 1 — The Phantom Bug

50,000,000 points, 4 native threads, all incrementing one shared
`static long totalHits` via `totalHits++`.

If no updates were lost, the expected hit count is
`50,000,000 × π/4 ≈ 39,269,908`.

### Results (5 runs)

| Run | totalHits | π estimate | Lost updates | Loss rate | Error |
|---|---|---|---|---|---|
| 1 | 9,945,439 | 0.795635 | 29,324,469 | 74.67% | 74.67% |
| 2 | 9,946,393 | 0.795711 | 29,323,515 | 74.67% | 74.67% |
| 3 | 13,184,123 | 1.054730 | 26,085,785 | 66.43% | 66.43% |
| 4 | 9,905,476 | 0.792438 | 29,364,432 | 74.78% | 74.78% |
| 5 | 9,953,020 | 0.796242 | 29,316,888 | 74.65% | 74.65% |

**Mean π = 0.846951** against a true value of 3.141593 — a **73.04% error**.
Roughly **28.7 million of every 39.3 million increments were destroyed.**
The spread across runs is 0.792438 to 1.054730, and run 3 is a visible outlier
at 1.054730 while the other four cluster near 0.795.

### Why it fails

`totalHits++` looks like one operation but is three, and the JVM bytecode shows
it plainly:

```
getstatic   totalHits      <-- LOAD
ladd                       <-- ADD
putstatic   totalHits      <-- STORE
```

Java threads are real OS threads scheduled onto real cores, with no global
interpreter lock to serialise them. Two threads therefore execute that sequence
genuinely simultaneously:

```
Thread A: LOAD  totalHits -> 1000
Thread B: LOAD  totalHits -> 1000     (reads the same stale value)
Thread A: ADD             -> 1001
Thread B: ADD             -> 1001
Thread A: STORE           -> 1001
Thread B: STORE           -> 1001     (overwrites A)

Two hits counted. Counter advanced by one. One update LOST FOREVER.
```

Generalising: if *n* threads read the same value before any of them writes,
*n − 1* increments are destroyed.

Because lost updates only ever *reduce* the count, `totalHits` is systematically
undercounted, and since π is computed as `4 × hits / total`, the estimate is
biased **downward** — not merely noisy. The result also differs on every run,
because the interleaving depends on scheduling that no one controls.

This is the signature of a data race: **wrong, and wrong differently each time,
while the arithmetic itself is perfectly correct.**

> **Why the corruption here is so severe.** A 73% loss rate is worse than the
> 40–45% (π ≈ 1.8–2.4) that a typical 4-core machine produces. That is a direct
> consequence of the hardware: with 20 logical processors available, all four
> threads get their own physical core and run in genuine lockstep parallelism
> for the whole duration. There is no time-slicing to accidentally serialise
> them, so collisions inside the read-modify-write window are close to
> continuous. **More parallelism makes an unsynchronised counter worse, not
> better** — a useful reminder that code which "works on my machine" with two
> cores can fail catastrophically on a bigger one.

---

## Part 2 — The Synchronization Trap

The race is fixed two ways, both measured against a plain single-threaded loop
over the same 50,000,000 points.

### Results

| Implementation | π estimate | Time (ms) | vs single-threaded |
|---|---|---|---|
| Single-threaded plain loop | 3.141524 | **199** | 1.00× (baseline) |
| `synchronized` (4 threads) | 3.141698 | **2155** | **10.83× SLOWER** |
| `AtomicLong.incrementAndGet()` (4 threads) | 3.141627 | **606** | **3.05× SLOWER** |

Both fixes produce a correct π. **Both are slower than using one thread and no
synchronisation at all.** `AtomicLong` is 3.56× faster than `synchronized`, but
still three times slower than not sharing state in the first place.

Dividing the extra time by the ~39.3 million increments gives the marginal cost
of each coordinated update:

```
synchronized : (2155 - 199) ms / 39,269,908 increments = 49.8 ns per increment
AtomicLong   : ( 606 - 199) ms / 39,269,908 increments = 10.4 ns per increment
```

For comparison, an L1 cache hit costs roughly 1 ns. The analysis is in
Question 2.

> **Note on methodology:** the benchmark performs a JIT warm-up pass before
> timing. Without it the first measurement runs in interpreted mode and the
> baseline is inflated several-fold, which would invalidate every comparison
> drawn from it.

---

## Part 3 — OpenMP-Style Reduction

Shared state is removed entirely. Each thread accumulates into a **private local
counter**; the partials are summed once, after `join()`. This is the manual
equivalent of:

```c
#pragma omp parallel for reduction(+:totalHits)
```

```java
public void run() {
    long hits = 0;                    // private to this thread's stack
    for (long i = 0; i < pointsToToss; i++) {
        double x = rng.nextDouble(), y = rng.nextDouble();
        if (x * x + y * y <= 1.0) hits++;
    }
    this.localHits = hits;            // ONE write, at the very end
}
// ... after all joins, single-threaded:
for (Worker w : workers) totalHits += w.getLocalHits();
```

**Why it is correct without any lock:** no two threads ever touch the same
variable. Each worker writes its own field exactly once, and `Thread.join()`
establishes a happens-before edge, so the main thread is guaranteed to observe
every partial result when it performs the reduction. There is nothing to race
on, so there is nothing to protect.

### The grid — 100,000,000 iterations

| Threads (T) | Runtime (ms) | Speedup vs 1 Thread (T1/TN) | Efficiency (Speedup/T) |
|---|---|---|---|
| 1 | 388 *(baseline)* | 1.00× | 100.0% |
| 2 | 200 | 1.94× | 97.0% |
| 4 | 128 | 3.03× | 75.8% |
| 8 | **87** | **4.46×** | 55.7% |
| 16 | **86** | **4.51×** | 28.2% |
| 32 † | 85 | 4.56× | 14.3% |

† T = 32 is measured as the Part 3 specification requires; the worksheet grid
asks only for rows through T = 16.

Every row produces a correct π (3.14129 – 3.14170). Correctness here is
*structural*, not enforced — there is no counter to corrupt.

**Aggregate throughput plateaus hard at T = 8:**

```
T =  1:    258,000 points/ms
T =  2:    500,000 points/ms
T =  4:    781,000 points/ms
T =  8:  1,149,000 points/ms   <-- ceiling reached
T = 16:  1,163,000 points/ms   (+1.2%)
T = 32:  1,176,000 points/ms   (+2.4%)
```

---

## Questions

### 1. Look at your row for 16 threads. Why didn't the CPU run twice as fast as with 8 threads?

**Measured: T = 8 took 87 ms and T = 16 took 86 ms — a 1.2% improvement for
double the threads.** Doubling the thread count bought essentially nothing.

First, a correction to the premise: this machine is not an 8-core CPU. It is an
i7-12700H with **14 physical cores (6 P + 8 E) and 20 logical threads**. But
the answer is the same shape, and arguably sharper, because the machine had
already run out of useful capacity well before T = 16.

Four mechanisms combine to produce the plateau:

**1. Threads are not execution units.** A thread is a scheduling abstraction; a
core is the thing that actually executes instructions. Once T exceeds the number
of cores that can usefully run the workload, additional threads do not add
capacity — the OS simply time-slices the same silicon among more runnable
entities. Speedup is bounded by `min(T, usable cores)`, never by T. Past that
point every extra thread divides the same pie into smaller pieces.

**2. The efficiency column shows the saturation directly.** Efficiency is
speedup ÷ T, i.e. how much of each thread is actually converted into useful
throughput:

```
T =  2 : 97.0%    near-perfect
T =  4 : 75.8%    first sign of strain
T =  8 : 55.7%    half of each thread is wasted
T = 16 : 28.2%    halved again
T = 32 : 14.3%    halved again
```

Each doubling past T = 8 halves efficiency while runtime stays flat — the exact
signature of a saturated resource. The work is not going faster; it is merely
being divided among more threads.

**3. The hybrid topology caps the useful thread count well below 14.** Peak
speedup is only 4.56×, far short of the 14 the physical core count suggests.
Three hardware reasons:

- **E-cores are much slower than P-cores.** 8 of the 14 cores are Gracemont
  E-cores with substantially lower IPC and a lower clock ceiling. The work is
  partitioned into *equal* chunks (`100,000,000 / T` per thread), but the
  elapsed time of the whole run is set by the **slowest** thread, not the
  average. Once threads spill onto E-cores, those chunks become the critical
  path and everyone waits for them. Equal partitioning is the wrong policy on a
  heterogeneous CPU — chunk sizes should be weighted by core class.

- **All-core turbo is far below single-core turbo.** At T = 1 the single active
  thread runs on one P-core boosting to its maximum. With every core loaded, the
  package hits its power and thermal limits and the all-core clock drops
  substantially. The T = 1 baseline is therefore measured under the most
  favourable conditions the chip ever offers, which systematically depresses
  every speedup ratio computed against it. Per-core throughput falls from
  258,000 points/ms at T = 1 to 144,000 at T = 8 — only 56% of the rate a single
  unencumbered core achieves. This is a laptop, and sustained all-core
  performance is power-limited by design.

- **SMT threads share execution resources rather than adding them.**
  Hyper-Threading duplicates architectural state — registers, program counter —
  but not the execution back-end. The Monte Carlo kernel is a tight loop of
  register-resident floating-point arithmetic with no memory stalls and no
  branch mispredictions, so a single thread already saturates its core's
  pipelines. Its sibling hyperthread finds no idle issue slots to exploit. SMT
  pays off when threads stall frequently; here it contributes close to nothing.

**4. Beyond saturation, more threads add pure cost.** Because total work is
fixed at 100,000,000 points, per-thread work shrinks as 1/T while per-thread
overhead accumulates as O(T): thread creation and stack allocation, scheduler
pressure, and a longer reduction loop. More significantly, once T exceeds the
core count the scheduler must preempt threads, and each involuntary context
switch costs 1–10 µs directly plus a far larger indirect penalty — the evicted
thread loses its L1/L2 working set and TLB entries and must fault them back in.
At T = 32 the machine is running 32 threads on 14 cores to no benefit whatsoever.

**Conclusion.** The optimal configuration here is **T = 8**, not 16, not 20, and
certainly not 32. Matching thread count to the logical processor count is a
common and costly mistake: the right number depends on the ratio of per-thread
work to per-thread overhead, and on a hybrid, power-limited mobile CPU the
optimum sits well below the nominal thread count.

---

### 2. Why was the synchronized version in Part 2 slower than running on one single core?

**Measured: 2155 ms with 4 synchronized threads versus 199 ms single-threaded —
10.83× slower.** Four cores did the work of one and took eleven times longer.

**The lock serialises the part that matters.** Every hit calls
`incrementSync()`, which holds a monitor for the whole read-modify-write. Only
one thread can be inside at a time, so all ~39.3 million increments happen
strictly one after another regardless of how many threads exist. In Amdahl's
terms the parallelisable fraction of the counting is effectively zero — but the
program still pays every cost of being parallel. The threads have become an
elaborate queue.

That explains why it is *not faster*. It does not yet explain why it is
*slower*. The answer is that multithreading adds four costs the single-threaded
version never pays:

**1. Lock acquisition and release, ~39 million times.** Even uncontended, a
monitor enter/exit is a compare-and-swap on the object header. Under real
contention HotSpot *inflates* the lock into a heavyweight monitor backed by OS
primitives, so losing threads `park()` — a kernel transition — and the winner
must `unpark()` a waiter on exit. The measured marginal cost is **49.8 ns per
increment**, against roughly 1 ns for an L1 cache hit.

**2. Cache-line ping-pong between cores.** This is the dominant hardware cost.
`syncHits` and the monitor word live in a 64-byte cache line that must be held
in **Modified** state by whichever core is currently incrementing. When the next
thread on a different core acquires the lock, that line must be invalidated in
the first core's L1 and transferred across the interconnect. On the MESI
protocol each handover costs tens of cycles, versus about 4 for an L1 hit — and
with 4 threads the line never settles anywhere. The single-threaded version
keeps its counter in a **CPU register** for the entire loop: zero memory traffic,
zero coherence traffic, nothing to transfer.

**3. Convoying and scheduler churn.** Threads pile up behind the monitor. If the
OS deschedules the lock holder, every waiter stalls until it is rescheduled, and
the resulting bursts of park/unpark traffic generate context switches that
evict useful cache lines.

**4. The critical section is tiny relative to its overhead.** The protected work
is a single `++`. The machinery guarding it costs far more than the operation
itself — the classic anti-pattern of a lock whose overhead dwarfs its payload.

**Why `AtomicLong` is better but still not good.** At 606 ms it is 3.56× faster
than `synchronized`, because a CAS loop stays in user space and avoids monitor
inflation, parking and kernel transitions entirely — 10.4 ns per increment
instead of 49.8. But it cannot avoid point 2: every `incrementAndGet` must still
take exclusive ownership of that one cache line, so the line still ping-pongs
between cores. That irreducible coherence cost is why it remains 3.05× slower
than not sharing at all. **No lock implementation, however clever, can beat the
interconnect.**

**The resolution is Part 3.** Removing the shared variable rather than guarding
it more cleverly gives 100,000,000 points in 87 ms with 8 threads — equivalent
to **43.5 ms per 50,000,000 points, roughly 50× faster than the synchronized
version** and 4.6× faster than the single-threaded baseline. Optimising a lock
changes a constant factor; eliminating the shared state changes what the program
is asymptotically capable of.

---

## Repository layout

```
.
├── README.md                          this file
├── .gitignore
├── run_all.ps1                        Windows runner (PowerShell)
├── run_all.bat                        Windows runner (cmd.exe fallback)
├── run_all.sh                         Linux/macOS runner
├── src/
│   ├── Part1PhantomBug.java           racy shared counter
│   ├── Part2SynchronizationTrap.java  synchronized + AtomicLong vs serial
│   └── Part3Reduction.java            private counters + single reduction
└── results/
    ├── benchmark_output.txt           full transcript
    └── part3_results.csv              scaling data
```

---

## Summary of the three lessons

| | Correct? | Fast? | Measured | Why |
|---|---|---|---|---|
| **Part 1** unsynchronised | ❌ π = 0.85 | ✅ ~170 ms | 73% of updates lost | Shared read-modify-write, updates overwritten |
| **Part 2** `synchronized` | ✅ π = 3.1417 | ❌ 2155 ms | 10.83× slower than serial | Every increment serialises on one memory location |
| **Part 2** `AtomicLong` | ✅ π = 3.1416 | ❌ 606 ms | 3.05× slower than serial | CAS avoids the kernel but not the cache line |
| **Part 3** reduction | ✅ π = 3.1416 | ✅ 87 ms | 4.46× faster than serial | No shared state, so nothing to serialise |

The progression is the point. Both failures came from four threads sharing one
variable. Part 2 guards that variable and pays for the privilege on every single
operation; Part 3 removes the sharing and the problem disappears with it.
Correctness and speed turned out not to be a trade-off at all — the same
architectural change delivered both.
