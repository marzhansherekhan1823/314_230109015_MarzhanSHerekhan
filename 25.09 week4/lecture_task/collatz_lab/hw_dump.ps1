# =====================================================================
#  Phase 1, Step 1.1 - Hardware Specification Capture
#  Writes hw_info.txt, the verbatim system output the worksheet requires.
#
#  Usage:  .\hw_dump.ps1
#  If PowerShell blocks it:
#      Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
# =====================================================================

$ErrorActionPreference = "Continue"
$out = "hw_info.txt"

function Section($title) {
    ""
    "======================================================================="
    " $title"
    "======================================================================="
}

$lines = @()

$lines += "======================================================================="
$lines += " HARDWARE SPECIFICATION DUMP"
$lines += " Captured: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
$lines += " Machine : $env:COMPUTERNAME"
$lines += "======================================================================="

# ---- the exact command the worksheet specifies ----------------------
$lines += Section "Win32_Processor (worksheet-specified command)"
$lines += (Get-CimInstance Win32_Processor |
           Select-Object Name, NumberOfCores, NumberOfLogicalProcessors |
           Format-List | Out-String).TrimEnd()

# ---- fuller processor detail ----------------------------------------
$lines += Section "Processor detail"
$lines += (Get-CimInstance Win32_Processor |
           Select-Object Name, Manufacturer, Description, Architecture,
                         NumberOfCores, NumberOfLogicalProcessors,
                         MaxClockSpeed, CurrentClockSpeed, L2CacheSize,
                         L3CacheSize, SocketDesignation, VirtualizationFirmwareEnabled |
           Format-List | Out-String).TrimEnd()

# ---- cache hierarchy -------------------------------------------------
$lines += Section "Cache hierarchy (Win32_CacheMemory)"
$lines += (Get-CimInstance Win32_CacheMemory |
           Select-Object Purpose, InstalledSize, MaxCacheSize, BlockSize, Level, Associativity |
           Format-Table -AutoSize | Out-String).TrimEnd()
$lines += ""
$lines += "NOTE: the BlockSize field reported by WMI is not a reliable cache-line"
$lines += "size on this platform. The architectural coherency line size for x86-64"
$lines += "(Intel Alder Lake included) is 64 bytes, which is the value used in the"
$lines += "padding arithmetic of the false-sharing experiment."

# ---- memory ----------------------------------------------------------
$lines += Section "Physical memory"
$lines += (Get-CimInstance Win32_PhysicalMemory |
           Select-Object Manufacturer, Capacity, Speed, ConfiguredClockSpeed,
                         DeviceLocator, SMBIOSMemoryType, DataWidth, TotalWidth |
           Format-Table -AutoSize | Out-String).TrimEnd()

$total = (Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory
$lines += "Total physical memory: $([math]::Round($total / 1GB, 2)) GB"

# ---- operating system -------------------------------------------------
$lines += Section "Operating system"
$lines += (Get-CimInstance Win32_OperatingSystem |
           Select-Object Caption, Version, BuildNumber, OSArchitecture, LastBootUpTime |
           Format-List | Out-String).TrimEnd()

# ---- toolchain ---------------------------------------------------------
$lines += Section "Toolchain"
try {
    $lines += "gcc --version:"
    $lines += (gcc --version 2>&1 | Out-String).TrimEnd()
} catch { $lines += "  gcc not found on PATH" }

$lines += ""
$lines += "OpenMP runtime threads (omp_get_max_threads) is reported by the"
$lines += "collatz binary itself at the top of its output."

# ---- environment -------------------------------------------------------
$lines += Section "Relevant environment variables"
$lines += "OMP_NUM_THREADS   = $($env:OMP_NUM_THREADS)"
$lines += "NUMBER_OF_PROCESSORS = $($env:NUMBER_OF_PROCESSORS)"
$lines += "PROCESSOR_IDENTIFIER = $($env:PROCESSOR_IDENTIFIER)"

$lines | Out-File -FilePath $out -Encoding utf8

Write-Host ""
Write-Host "Wrote $((Resolve-Path $out).Path)" -ForegroundColor Green
Write-Host ""
Write-Host "--- summary for the worksheet metadata table ---" -ForegroundColor Cyan
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
Write-Host ("  CPU model          : {0}" -f $cpu.Name.Trim())
Write-Host ("  Physical cores     : {0}" -f $cpu.NumberOfCores)
Write-Host ("  Logical processors : {0}" -f $cpu.NumberOfLogicalProcessors)
Write-Host ("  Cache line size    : 64 bytes (x86-64 architectural)")
Write-Host ("  Total RAM          : {0} GB" -f [math]::Round($total / 1GB, 2))
Write-Host ""
