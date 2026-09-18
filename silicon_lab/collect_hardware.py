"""
Hardware topology collector - auto-fills the worksheet metadata table.

Cross-platform (Linux / macOS / Windows). Read-only: runs only informational
OS queries, never modifies anything. Some cache and memory-speed fields need
elevated privileges (dmidecode on Linux); those simply print as UNAVAILABLE
rather than prompting, and the script tells you the manual command to run.
"""

import os
import sys
import platform
import shutil
import subprocess


def sh(cmd):
    """Run a shell command, return stripped stdout or None."""
    try:
        out = subprocess.run(cmd, shell=True, capture_output=True,
                             text=True, timeout=25)
        val = out.stdout.strip()
        return val if val else None
    except Exception:
        return None


def section(title):
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def main():
    section("WORKSHEET METADATA - HOST DECLARATION")
    print(f"Host OS                  : {platform.platform()}")
    print(f"Machine architecture     : {platform.machine()}")
    print(f"Python runtime           : {platform.python_implementation()} "
          f"{platform.python_version()}")
    print(f"OS reported logical cores: {os.cpu_count()}")

    sysname = platform.system()

    # ---------- physical vs logical core topology ----------
    section("CORE TOPOLOGY (Physical P-cores / E-cores / SMT threads)")
    if sysname == "Linux":
        print(sh("lscpu | grep -E 'Model name|Architecture|^CPU\\(s\\)|"
                 "Thread\\(s\\) per core|Core\\(s\\) per socket|Socket\\(s\\)|"
                 "CPU max MHz|CPU min MHz'") or "lscpu UNAVAILABLE")
        phys = sh("grep -m1 'cpu cores' /proc/cpuinfo")
        if phys:
            print(f"\n/proc/cpuinfo  : {phys}")
        # Heterogeneous (big.LITTLE / P+E) detection via per-core max frequency
        freqs = sh("cat /sys/devices/system/cpu/cpu*/cpufreq/cpuinfo_max_freq "
                   "2>/dev/null | sort -u")
        if freqs and len(freqs.splitlines()) > 1:
            print("\nHETEROGENEOUS TOPOLOGY DETECTED - distinct max frequencies (kHz):")
            print(freqs)
            print("The higher-frequency group are your P-cores, the lower are E-cores.")
        elif freqs:
            print(f"\nUniform core max frequency (kHz): {freqs}  "
                  "-> homogeneous cores, no P/E split.")

    elif sysname == "Darwin":
        print(f"CPU SKU        : {sh('sysctl -n machdep.cpu.brand_string')}")
        print(f"Physical cores : {sh('sysctl -n hw.physicalcpu')}")
        print(f"Logical cores  : {sh('sysctl -n hw.logicalcpu')}")
        nlevels = sh("sysctl -n hw.nperflevels")
        print(f"Perf levels    : {nlevels}")
        if nlevels and nlevels.isdigit() and int(nlevels) > 1:
            print("APPLE SILICON HETEROGENEOUS TOPOLOGY:")
            print(f"  P-cores (perflevel0): {sh('sysctl -n hw.perflevel0.physicalcpu')}")
            print(f"  E-cores (perflevel1): {sh('sysctl -n hw.perflevel1.physicalcpu')}")
            print("  NOTE: Apple Silicon has NO SMT - logical == physical.")
        else:
            print(f"SMT threads/core: "
                  f"{sh('sysctl -n machdep.cpu.thread_count')} threads total")

    elif sysname == "Windows":
        print(sh('powershell -NoProfile -Command "Get-CimInstance Win32_Processor | '
                 'Select-Object Name,NumberOfCores,NumberOfLogicalProcessors,'
                 'MaxClockSpeed | Format-List"') or "WMI UNAVAILABLE")

    # ---------- cache hierarchy ----------
    section("CACHE HIERARCHY (L1 / L2 / L3)")
    if sysname == "Linux":
        print(sh("lscpu -C") or "lscpu -C UNAVAILABLE")
        print("\nPer-core detail from sysfs:")
        print(sh("for c in /sys/devices/system/cpu/cpu0/cache/index*; do "
                 "echo \"  L$(cat $c/level) $(cat $c/type) : $(cat $c/size) \""
                 "\"(line $(cat $c/coherency_line_size)B, \""
                 "\"shared by $(cat $c/shared_cpu_list))\"; done")
              or "sysfs cache UNAVAILABLE")
    elif sysname == "Darwin":
        print(f"L1 data cache   : {sh('sysctl -n hw.l1dcachesize')} bytes")
        print(f"L1 instr cache  : {sh('sysctl -n hw.l1icachesize')} bytes")
        print(f"L2 cache        : {sh('sysctl -n hw.l2cachesize')} bytes")
        l3 = sh("sysctl -n hw.l3cachesize")
        print(f"L3 cache        : {l3 if l3 and l3 != '0' else 'none (unified memory SoC)'}")
        print(f"CACHE LINE SIZE : {sh('sysctl -n hw.cachelinesize')} bytes  <-- Task 2")
    elif sysname == "Windows":
        print(sh('powershell -NoProfile -Command "Get-CimInstance Win32_CacheMemory | '
                 'Select-Object Purpose,MaxCacheSize,BlockSize | Format-Table"')
              or "WMI UNAVAILABLE")

    if sysname == "Linux":
        line = sh("cat /sys/devices/system/cpu/cpu0/cache/index0/coherency_line_size")
        print(f"\nCACHE LINE SIZE : {line} bytes  <-- Task 2 padding arithmetic")

    # ---------- memory bus (Q4.2) ----------
    section("MEMORY BUS SPECIFICATION (needed for Q4.2 bandwidth calculation)")
    if sysname == "Linux":
        print(f"Total RAM: {sh('free -h | head -2')}")
        dmi = sh("dmidecode --type memory 2>/dev/null | "
                 "grep -E 'Speed|Type:|Locator|Size' | head -40")
        if dmi:
            print(dmi)
        else:
            print("Module speed/type needs root. Run manually:")
            print("  sudo dmidecode --type memory | grep -E 'Speed|Type:|Size'")
    elif sysname == "Darwin":
        print(sh("system_profiler SPMemoryDataType 2>/dev/null | head -25")
              or "system_profiler UNAVAILABLE")
        print(f"\nTotal RAM bytes: {sh('sysctl -n hw.memsize')}")
        print("Apple Silicon: unified LPDDR on-package. Look up your chip's")
        print("published bandwidth (e.g. M2 Pro = 200 GB/s) for Q4.2.")
    elif sysname == "Windows":
        print(sh('powershell -NoProfile -Command "Get-CimInstance Win32_PhysicalMemory | '
                 'Select-Object Speed,Capacity,DeviceLocator,SMBIOSMemoryType | '
                 'Format-Table"') or "WMI UNAVAILABLE")

    # ---------- bandwidth formula helper ----------
    section("Q4.2 THEORETICAL PEAK BANDWIDTH FORMULA")
    print("  Peak GB/s = (MT/s) x (bus width bits / 8) x (number of channels) / 1000")
    print("\n  Worked reference values:")
    print("    DDR4-3200, 64-bit, dual-channel : 3200 x 8 x 2 / 1000 =  51.2 GB/s")
    print("    DDR4-3200, 64-bit, single-chan  : 3200 x 8 x 1 / 1000 =  25.6 GB/s")
    print("    DDR5-4800, 2x32-bit subch, dual : 4800 x 8 x 2 / 1000 =  76.8 GB/s")
    print("    LPDDR5-6400, 128-bit  (M2)      : 6400 x 16    / 1000 = 102.4 GB/s")
    print("    LPDDR5-6400, 256-bit  (M2 Pro)  : 6400 x 32    / 1000 = 204.8 GB/s")
    print("\n  Substitute YOUR module speed and channel count from the section above.")

    section("APPENDIX COMMANDS FOR YOUR OS (run these to paste raw proof)")
    if sysname == "Linux":
        print("  lscpu")
        print("  grep -E 'model name|cpu cores' /proc/cpuinfo")
        print("  lscpu -C")
        print("  sudo dmidecode --type memory | grep Speed")
    elif sysname == "Darwin":
        print("  sysctl -n machdep.cpu.brand_string")
        print("  sysctl hw.perflevel0.physicalcpu hw.perflevel1.physicalcpu")
        print("  sysctl hw.l1dcachesize hw.l2cachesize")
        print("  system_profiler SPMemoryDataType")
    elif sysname == "Windows":
        print("  Get-CimInstance Win32_Processor | Select Name,NumberOfCores")
        print("  wmic cpu get name,NumberOfCores,NumberOfLogicalProcessors")
        print("  Get-CimInstance Win32_CacheMemory")
        print("  wmic memorychip get speed,capacity,devicelocator")


if __name__ == "__main__":
    main()
