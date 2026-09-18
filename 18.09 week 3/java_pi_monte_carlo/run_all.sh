#!/usr/bin/env bash
# =====================================================================
#  Monte Carlo Pi - Concurrency Benchmark Suite  (Linux / macOS)
#  Usage:  bash run_all.sh
# =====================================================================
set -euo pipefail

mkdir -p out results
OUT="results/benchmark_output.txt"

{
  echo "======================================================================="
  echo " MONTE CARLO PI - CONCURRENCY BENCHMARK SUITE"
  echo "======================================================================="
  echo " Run timestamp : $(date '+%Y-%m-%d %H:%M:%S')"
  echo " Machine       : $(hostname)"
  echo " OS            : $(uname -sr)"
  if command -v lscpu >/dev/null 2>&1; then
    echo " CPU           : $(lscpu | grep 'Model name' | sed 's/Model name: *//')"
    echo " Cores         : $(nproc) logical"
  fi
  echo " Java          : $(java -version 2>&1 | head -1)"
  echo "======================================================================="
  echo
} | tee "$OUT"

echo "Compiling..."
javac -d out src/*.java
echo "Compiled OK."
echo

for part in "Part1PhantomBug:PART 1 - The Phantom Bug" \
            "Part2SynchronizationTrap:PART 2 - The Synchronization Trap" \
            "Part3Reduction:PART 3 - OpenMP-Style Reduction"; do
  cls="${part%%:*}"
  label="${part#*:}"

  echo "Running ${label} ..."
  {
    echo
    echo "#######################################################################"
    echo "# ${label}"
    echo "# command: java -cp out ${cls}"
    echo "# started: $(date '+%H:%M:%S')"
    echo "#######################################################################"
    echo
  } | tee -a "$OUT"

  java -cp out "$cls" 2>&1 | tee -a "$OUT"
  echo "  done."
done

[ -f part3_results.csv ] && mv -f part3_results.csv results/part3_results.csv

{
  echo
  echo "======================================================================="
  echo " SUITE COMPLETE - $(date '+%Y-%m-%d %H:%M:%S')"
  echo "======================================================================="
} | tee -a "$OUT"

echo
echo "Transcript : $(pwd)/$OUT"
