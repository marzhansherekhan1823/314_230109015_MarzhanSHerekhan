# =====================================================================
#  Monte Carlo Pi - Concurrency Benchmark Suite
#  Compiles and runs Parts 1, 2 and 3, saving a full transcript.
#
#  Usage:   .\run_all.ps1
#
#  If PowerShell refuses to run the script, allow it for this session:
#      Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#
#  If this script misbehaves for any reason, run_all.bat does the same
#  job with plain cmd.exe and no PowerShell semantics involved.
# =====================================================================

# NOTE: deliberately NOT using $ErrorActionPreference = "Stop".
# Native programs such as java and javac write ordinary progress text to
# stderr, and under "Stop" PowerShell promotes that to a terminating error
# and aborts the run. Exit codes are checked explicitly instead.
$ErrorActionPreference = "Continue"

# Normalises native command output to plain strings, so that anything the
# program writes to stderr becomes text rather than a PowerShell ErrorRecord.
function Invoke-Native {
    param([string]$Exe, [string[]]$Arguments)
    & $Exe @Arguments 2>&1 | ForEach-Object { $_.ToString() }
}

$stamp   = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$outFile = "results\benchmark_output.txt"

New-Item -ItemType Directory -Force -Path "out"     | Out-Null
New-Item -ItemType Directory -Force -Path "results" | Out-Null

Write-Host ""
Write-Host "=======================================================================" -ForegroundColor Cyan
Write-Host " Monte Carlo Pi - Concurrency Benchmark Suite" -ForegroundColor Cyan
Write-Host "=======================================================================" -ForegroundColor Cyan
Write-Host ""

# ---- sanity check: is a JDK present? ------------------------------------
$javacFound = $null -ne (Get-Command javac -ErrorAction SilentlyContinue)
if (-not $javacFound) {
    Write-Host "javac was not found on your PATH." -ForegroundColor Red
    Write-Host "A JRE alone is not enough - this needs a full JDK." -ForegroundColor Red
    Write-Host "Check with:  java -version   and   javac -version" -ForegroundColor Yellow
    exit 1
}

# ---- environment banner -------------------------------------------------
$javaVersion = "(unknown)"
try {
    $vLines = Invoke-Native "java" @("-version")
    $real = $vLines | Where-Object { $_ -notmatch "Picked up (JAVA|_JAVA)" } | Select-Object -First 1
    if ($real) { $javaVersion = $real.Trim() }
} catch { }

$cpuName = "(query failed)"; $cpuCores = "(query failed)"
try {
    $cpu = Get-CimInstance Win32_Processor -ErrorAction Stop | Select-Object -First 1
    $cpuName  = $cpu.Name.Trim()
    $cpuCores = "$($cpu.NumberOfCores) physical / $($cpu.NumberOfLogicalProcessors) logical"
} catch { }

$osName = "(query failed)"
try { $osName = (Get-CimInstance Win32_OperatingSystem -ErrorAction Stop).Caption } catch { }

$banner = @(
    "=======================================================================",
    " MONTE CARLO PI - CONCURRENCY BENCHMARK SUITE",
    "=======================================================================",
    " Run timestamp : $stamp",
    " Machine       : $env:COMPUTERNAME",
    " OS            : $osName",
    " CPU           : $cpuName",
    " Cores         : $cpuCores",
    " Java          : $javaVersion",
    "=======================================================================",
    ""
)
$banner | Tee-Object -FilePath $outFile

# ---- compile ------------------------------------------------------------
Write-Host "Compiling..." -ForegroundColor Yellow
$compileOut = Invoke-Native "javac" @("-d", "out", "src\Part1PhantomBug.java",
                                      "src\Part2SynchronizationTrap.java",
                                      "src\Part3Reduction.java")
$compileOut | Where-Object { $_ -notmatch "Picked up (JAVA|_JAVA)" } | ForEach-Object { Write-Host $_ }

if ($LASTEXITCODE -ne 0) {
    Write-Host "COMPILATION FAILED - fix the errors above before continuing." -ForegroundColor Red
    exit 1
}
Write-Host "Compiled OK." -ForegroundColor Green
Write-Host ""

# ---- run each part ------------------------------------------------------
$parts = @(
    @{ Name = "Part1PhantomBug";          Label = "PART 1 - The Phantom Bug" },
    @{ Name = "Part2SynchronizationTrap"; Label = "PART 2 - The Synchronization Trap" },
    @{ Name = "Part3Reduction";           Label = "PART 3 - OpenMP-Style Reduction" }
)

foreach ($p in $parts) {
    Write-Host "Running $($p.Label) ..." -ForegroundColor Yellow

    $header = @(
        "",
        "#######################################################################",
        "# $($p.Label)",
        "# command: java -cp out $($p.Name)",
        "# started: $(Get-Date -Format 'HH:mm:ss')",
        "#######################################################################",
        ""
    )
    $header | Tee-Object -FilePath $outFile -Append

    Invoke-Native "java" @("-cp", "out", $p.Name) |
        Where-Object { $_ -notmatch "Picked up (JAVA|_JAVA)" } |
        Tee-Object -FilePath $outFile -Append

    Write-Host "  done." -ForegroundColor Green
}

# part3_results.csv is written into the working directory; move it to results\
if (Test-Path "part3_results.csv") {
    Move-Item -Force "part3_results.csv" "results\part3_results.csv"
}

$footer = @(
    "",
    "=======================================================================",
    " SUITE COMPLETE - $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')",
    "======================================================================="
)
$footer | Tee-Object -FilePath $outFile -Append

Write-Host ""
Write-Host "All done." -ForegroundColor Cyan
Write-Host "Transcript : $((Resolve-Path $outFile).Path)" -ForegroundColor Cyan
if (Test-Path "results\part3_results.csv") {
    Write-Host "Part 3 CSV : $((Resolve-Path 'results\part3_results.csv').Path)" -ForegroundColor Cyan
}
Write-Host ""
